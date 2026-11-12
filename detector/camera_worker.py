"""One worker thread per camera: capture -> YOLO pose tracking -> analyzers -> alerts + evidence."""
import logging
import os
import tempfile
import threading
import time
from collections import deque
from concurrent.futures import Executor, Future

import numpy as np
from ultralytics import YOLO

from analyzers import Detection
from analyzers.fall import FallAnalyzer
from analyzers.fire_smoke import FireSmokeAnalyzer
from analyzers.intrusion import IntrusionAnalyzer
from analyzers.water import WaterDistressAnalyzer
from annotate import draw_detection, draw_header, draw_persons, draw_zones
from api_client import BackendClient
from config import Settings
from geometry import GeoMapper, Person, build_zones
from stream_server import StreamHub
from video import FrameReader, encode_jpeg, no_signal_frame, resize_max, write_clip

log = logging.getLogger("worker")


class _ClipJob:
    """Evidence clip: frames from before the alert plus a fixed number of seconds after it."""

    def __init__(self, pre: list[tuple[float, bytes]], end_time: float, incident: Future, det_type: str):
        self.items = list(pre)
        self.end_time = end_time
        self.incident = incident
        self.type = det_type

    def add(self, t: float, jpeg: bytes) -> bool:
        self.items.append((t, jpeg))
        return t >= self.end_time

    @property
    def frames(self) -> list[bytes]:
        return [j for _, j in self.items]

    @property
    def fps(self) -> float:
        # Play back at the rate frames were actually analysed, so the clip runs in real time
        span = self.items[-1][0] - self.items[0][0] if len(self.items) > 1 else 0
        return max(1.0, min(30.0, (len(self.items) - 1) / span)) if span > 0 else 5.0


class CameraWorker(threading.Thread):
    def __init__(self, cfg: dict, api: BackendClient, hub: StreamHub, settings: Settings, executor: Executor):
        super().__init__(daemon=True, name=f"camera-{cfg['id']}")
        self.cfg = cfg
        self.api = api
        self.hub = hub
        self.s = settings
        self.executor = executor
        self._stop_evt = threading.Event()
        self._lock = threading.Lock()
        self.camera_id = cfg["id"]

    # ------------------------------------------------------------ control
    def update_config(self, cfg: dict):
        with self._lock:
            self.cfg = cfg

    def stop(self):
        self._stop_evt.set()

    # --------------------------------------------------------------- loop
    def run(self):
        s = self.s
        log.info("[cam %s] starting '%s' (%s)", self.camera_id, self.cfg["name"], self.cfg["stream_url"])
        model = YOLO(s.pose_model)
        fire_smoke = FireSmokeAnalyzer(s.fire_smoke_model, s.fire_smoke_conf, s.device, s.fire_smoke_imgsz)
        fall, intrusion, water = FallAnalyzer(), IntrusionAnalyzer(), WaterDistressAnalyzer()

        reader = FrameReader(self.cfg["stream_url"], str(self.camera_id))
        reader.start()

        interval = 1.0 / max(s.process_fps, 1)
        buffer: deque = deque()  # (time, jpeg) for the last clip_pre_seconds
        clips: list[_ClipJob] = []
        cooldown: dict[str, float] = {}
        recent: list[tuple[float, Detection]] = []
        seq, last_proc, frame_no, last_fire = 0, 0.0, 0, 0.0
        fps_ema = s.process_fps
        status, last_hb = None, 0.0
        geom_key, zones, mapper = None, [], GeoMapper(None, 1, 1)

        while not self._stop_evt.is_set():
            frame, seq = reader.read(seq, timeout=5)
            now = time.time()

            # ---- camera health / heartbeat
            new_status = "online" if reader.connected and frame is not None else "offline"
            if new_status != status or now - last_hb > 30:
                status, last_hb = new_status, now
                self.executor.submit(self.api.heartbeat, self.camera_id, status, reader.error)
                self.hub.set_status(self.camera_id, name=self.cfg["name"], status=status, error=reader.error)
            if frame is None:
                self.hub.publish(self.camera_id, no_signal_frame(reader.error or "Waiting for stream"))
                continue

            if now - last_proc < interval:
                continue
            dt = now - last_proc if last_proc else interval
            last_proc = now
            fps_ema = 0.9 * fps_ema + 0.1 * (1.0 / max(dt, 1e-3))
            frame_no += 1

            with self._lock:
                cfg = self.cfg
            frame = resize_max(frame, s.max_frame_width)
            h, w = frame.shape[:2]
            enabled = set(cfg.get("detections") or [])

            key = (w, h, repr(cfg.get("zones")), repr(cfg.get("calibration")))
            if key != geom_key:
                geom_key = key
                zones = build_zones(cfg.get("zones") or [], w, h)
                mapper = GeoMapper(cfg.get("calibration"), w, h)

            # Only run the models a camera actually needs (CPU budget is shared by all cameras)
            needs_pose = bool(enabled & {"fall", "intrusion", "water_distress"})
            persons = self._detect_persons(model, frame) if needs_pose else []
            dets: list[Detection] = []
            if "fall" in enabled:
                dets += fall.update(persons, now)
            if "intrusion" in enabled:
                dets += intrusion.update(persons, zones, now)
            if "water_distress" in enabled:
                dets += water.update(persons, zones, now, frame.shape)
            if now - last_fire >= 0.33:  # fire/smoke evolve slowly: ~3 checks per second is plenty
                last_fire = now
                dets += fire_smoke.update(frame, persons, enabled)

            # ---- annotate
            raw_jpeg = encode_jpeg(frame, 85) if frame_no % 5 == 1 else None
            vis = frame.copy()
            draw_zones(vis, zones)
            tags = {}
            for tid, st in fall.states().items():
                if st == "lying":
                    tags[tid] = "DOWN"
            for tid in intrusion.intruders():
                tags[tid] = "INTRUDER"
            for tid, sc in water.scores().items():
                if sc > 0.3:
                    tags[tid] = f"WATER {sc:.2f}"
            draw_persons(vis, persons, tags)
            recent = [(t, d) for t, d in recent if now - t < 4] + [(now, d) for d in dets]
            for _, d in recent:
                draw_detection(vis, d)
            draw_header(vis, cfg["name"], fps_ema, [d for _, d in recent])
            jpeg = encode_jpeg(vis, 80)
            self.hub.publish(self.camera_id, jpeg, raw_jpeg)
            self.hub.set_status(self.camera_id, fps=round(fps_ema, 1), persons=len(persons))

            # ---- evidence buffers
            for job in list(clips):
                if job.add(now, jpeg):
                    clips.remove(job)
                    self.executor.submit(self._finish_clip, job, job.fps)
            buffer.append((now, jpeg))
            while buffer and now - buffer[0][0] > s.clip_pre_seconds:
                buffer.popleft()

            # ---- raise alerts
            for d in dets:
                if now - cooldown.get(d.type, 0) < s.cooldown_seconds:
                    continue
                cooldown[d.type] = now
                latlon = mapper.to_latlon(d.point)
                log.warning("[cam %s] %s detected (%.0f%%) %s", self.camera_id, d.type, d.confidence * 100, d.details)
                future = self.executor.submit(
                    self.api.create_incident, self.camera_id, d.type, d.confidence,
                    {**d.details, "persons_in_view": len(persons)}, latlon, jpeg,
                )
                clips.append(_ClipJob(list(buffer), now + s.clip_post_seconds, future, d.type))

        reader.stop()
        self.hub.remove(self.camera_id)
        log.info("[cam %s] stopped", self.camera_id)

    # ---------------------------------------------------------- helpers
    def _detect_persons(self, model: YOLO, frame) -> list[Person]:
        kw = {"persist": True, "conf": self.s.person_conf, "classes": [0], "verbose": False, "imgsz": self.s.pose_imgsz,
              "tracker": "bytetrack.yaml"}
        if self.s.device:
            kw["device"] = self.s.device
        res = model.track(frame, **kw)[0]
        if res.boxes is None or len(res.boxes) == 0:
            return []
        boxes = res.boxes.xyxy.cpu().numpy()
        confs = res.boxes.conf.cpu().numpy()
        ids = res.boxes.id.int().cpu().numpy() if res.boxes.id is not None else -np.arange(1, len(boxes) + 1)
        kpts = res.keypoints.data.cpu().numpy() if res.keypoints is not None else None
        return [
            Person(int(ids[i]), tuple(float(v) for v in boxes[i]), float(confs[i]),
                   kpts[i] if kpts is not None and len(kpts) > i else None)
            for i in range(len(boxes))
        ]

    def _finish_clip(self, job: _ClipJob, fps: float):
        try:
            incident = job.incident.result(timeout=120)
        except Exception as e:
            log.error("[cam %s] incident upload failed, clip discarded: %s", self.camera_id, e)
            return
        if incident.get("merged") and incident.get("clip_url"):
            return  # existing incident already has evidence
        fd, path = tempfile.mkstemp(suffix=".mp4", prefix=f"cam{self.camera_id}_")
        os.close(fd)
        try:
            write_clip(job.frames, fps, path)
            self.api.upload_clip(incident["id"], path)
            log.info("[cam %s] evidence clip uploaded for incident #%s", self.camera_id, incident["id"])
        except Exception as e:
            log.error("[cam %s] clip upload failed: %s", self.camera_id, e)
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

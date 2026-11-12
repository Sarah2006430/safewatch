"""Run the detection pipeline offline over recorded footage and report what it finds.

Uses exactly the same YOLO pose tracking + analyzers as the live camera worker,
but drives time from the video's own frame clock, so results are reproducible.

    python evaluate_video.py datasets/demo/lobby_falls.mp4 --detect fall
    python evaluate_video.py datasets/demo/fire.mp4 --detect fire smoke
    python evaluate_video.py clip.mp4 --detect intrusion --zone 0.55,0 1,0 1,1 0.55,1
"""
import argparse
import sys

import cv2
from ultralytics import YOLO

from analyzers.fall import FallAnalyzer
from analyzers.fire_smoke import FireSmokeAnalyzer
from analyzers.intrusion import IntrusionAnalyzer
from analyzers.water import WaterDistressAnalyzer
from config import settings
from geometry import Person, build_zones
from video import resize_max


def persons_from(res) -> list[Person]:
    if res.boxes is None or len(res.boxes) == 0:
        return []
    boxes = res.boxes.xyxy.cpu().numpy()
    confs = res.boxes.conf.cpu().numpy()
    ids = res.boxes.id.int().cpu().numpy() if res.boxes.id is not None else [-(i + 1) for i in range(len(boxes))]
    kpts = res.keypoints.data.cpu().numpy() if res.keypoints is not None else None
    return [Person(int(ids[i]), tuple(float(v) for v in boxes[i]), float(confs[i]),
                   kpts[i] if kpts is not None else None) for i in range(len(boxes))]


def evaluate(path: str, detect: list[str], zone_pts=None, zone_kind="restricted", fps=10.0, quiet=False):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        sys.exit(f"Cannot open {path}")
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 25
    step = max(1, round(src_fps / fps))
    model = YOLO(settings.pose_model)
    fall, intrusion, water = FallAnalyzer(), IntrusionAnalyzer(), WaterDistressAnalyzer()
    fire_smoke = FireSmokeAnalyzer(settings.fire_smoke_model, settings.fire_smoke_conf, settings.device, settings.fire_smoke_imgsz)
    zones_cfg = [{"id": 1, "name": "Zone", "kind": zone_kind, "dwell_seconds": 2.0, "roi": zone_pts}] if zone_pts else []
    zones, found, idx = None, [], 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        idx += 1
        if idx % step:
            continue
        t = idx / src_fps
        frame = resize_max(frame, settings.max_frame_width)
        if zones is None:
            zones = build_zones(zones_cfg, frame.shape[1], frame.shape[0])
        persons = []
        if {"fall", "intrusion", "water_distress"} & set(detect):
            res = model.track(frame, persist=True, conf=settings.person_conf, classes=[0], imgsz=settings.pose_imgsz,
                              verbose=False, tracker="bytetrack.yaml")[0]
            persons = persons_from(res)
        dets = []
        if "fall" in detect:
            dets += fall.update(persons, t)
        if "intrusion" in detect:
            dets += intrusion.update(persons, zones, t)
        if "water_distress" in detect:
            dets += water.update(persons, zones, t, frame.shape)
        dets += fire_smoke.update(frame, persons, set(detect))
        for d in dets:
            found.append((t, d))
            if not quiet:
                print(f"  {t:7.1f}s  {d.type:15s} {d.confidence:.0%}  {d.details}")
    cap.release()
    return found


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--detect", nargs="+", default=["fall", "fire", "smoke"],
                    choices=["fall", "fire", "smoke", "intrusion", "water_distress"])
    ap.add_argument("--zone", nargs="+", help="normalised polygon points x,y ... (for intrusion / water)")
    ap.add_argument("--zone-kind", default="restricted", choices=["restricted", "water"])
    ap.add_argument("--fps", type=float, default=10.0)
    a = ap.parse_args()
    pts = [[float(v) for v in p.split(",")] for p in a.zone] if a.zone else None
    print(f"{a.video}  detecting: {', '.join(a.detect)}")
    res = evaluate(a.video, a.detect, pts, a.zone_kind, a.fps)
    print(f"{len(res)} detection(s)")

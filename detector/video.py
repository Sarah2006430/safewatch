"""Camera capture (RTSP / HTTP / file / webcam) with auto-reconnect and evidence clip writing."""
import logging
import os
import threading
import time

import cv2
import numpy as np

log = logging.getLogger("video")


class FrameReader(threading.Thread):
    """Continuously reads frames in the background and keeps only the latest one.

    Reading on a dedicated thread avoids the RTSP buffer filling up (which causes
    seconds of lag) when inference is slower than the camera frame rate.
    """

    def __init__(self, source: str, name: str = ""):
        super().__init__(daemon=True, name=f"reader-{name}")
        self.source = source.strip()
        self.is_file = os.path.isfile(self.source)
        self._stop_evt = threading.Event()
        self._cond = threading.Condition()
        self.frame = None
        self.seq = 0
        self.error = ""
        self.connected = False

    def _open(self):
        if self.source.isdigit():
            backend = cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY
            cap = cv2.VideoCapture(int(self.source), backend)
        elif self.is_file:
            cap = cv2.VideoCapture(self.source)
        else:
            cap = cv2.VideoCapture(self.source, cv2.CAP_FFMPEG)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return cap

    def run(self):
        backoff = 2
        cap = None
        slow_reads = 0
        while not self._stop_evt.is_set():
            if cap is None or not cap.isOpened():
                cap = self._open()
                if not cap.isOpened():
                    self.connected = False
                    self.error = f"Cannot open stream (retry in {backoff}s)"
                    log.warning("[%s] %s", self.source, self.error)
                    self._stop_evt.wait(backoff)
                    backoff = min(backoff * 2, 30)
                    cap = None
                    continue
                backoff = 2
                self.error = ""
                log.info("[%s] stream opened", self.source)
                fps = cap.get(cv2.CAP_PROP_FPS) or 25
                delay = 1.0 / fps if self.is_file and fps > 0 else 0

            t_read = time.time()
            ok, frame = cap.read()
            if self.source.isdigit() and ok:
                # A stuck webcam driver keeps returning ok=True about once a second with an
                # uninitialised buffer (black, or leftover frames from other cameras).
                # Several slow reads in a row means the device is stuck: reconnect it.
                slow_reads = slow_reads + 1 if time.time() - t_read > 0.7 else 0
                if slow_reads >= 3:
                    slow_reads = 0
                    self.connected = False
                    self.error = "Webcam stalled, reconnecting"
                    log.warning("[webcam %s] %s", self.source, self.error)
                    cap.release()
                    cap = None
                    self._stop_evt.wait(1)
                    continue
            if not ok or frame is None:
                if self.is_file:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # loop demo videos
                    continue
                self.connected = False
                self.error = "Stream interrupted, reconnecting"
                log.warning("[%s] %s", self.source, self.error)
                cap.release()
                cap = None
                continue

            self.connected = True
            with self._cond:
                self.frame = frame
                self.seq += 1
                self._cond.notify_all()
            if delay:
                time.sleep(delay)
        if cap is not None:
            cap.release()

    def read(self, last_seq: int, timeout: float = 5.0):
        with self._cond:
            self._cond.wait_for(lambda: self.seq != last_seq or self._stop_evt.is_set(), timeout=timeout)
            if self.seq == last_seq:
                return None, last_seq
            return self.frame, self.seq

    def stop(self):
        self._stop_evt.set()
        with self._cond:
            self._cond.notify_all()


def resize_max(frame, max_width: int):
    h, w = frame.shape[:2]
    if w <= max_width:
        return frame
    s = max_width / w
    return cv2.resize(frame, (max_width, int(h * s)), interpolation=cv2.INTER_AREA)


def encode_jpeg(frame, quality: int = 80) -> bytes:
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return buf.tobytes() if ok else b""


def no_signal_frame(text: str, width: int = 960, height: int = 540) -> bytes:
    img = np.full((height, width, 3), 25, np.uint8)
    cv2.putText(img, "NO SIGNAL", (width // 2 - 150, height // 2 - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 1.6, (80, 80, 255), 3, cv2.LINE_AA)
    cv2.putText(img, text[:70], (30, height // 2 + 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                (200, 200, 200), 1, cv2.LINE_AA)
    return encode_jpeg(img)


def write_clip(jpegs: list[bytes], fps: float, path: str) -> str:
    """Encodes buffered JPEG frames to a browser-playable H.264 MP4."""
    frames = [cv2.imdecode(np.frombuffer(j, np.uint8), cv2.IMREAD_COLOR) for j in jpegs if j]
    frames = [f for f in frames if f is not None]
    if not frames:
        raise ValueError("no frames to write")
    h, w = frames[0].shape[:2]
    w2, h2 = w - w % 2, h - h % 2
    fps = max(1.0, min(30.0, fps))
    try:
        import imageio_ffmpeg

        writer = imageio_ffmpeg.write_frames(
            path, (w2, h2), fps=fps, codec="libx264", pix_fmt_in="rgb24", pix_fmt_out="yuv420p",
            quality=None, macro_block_size=1,
            output_params=["-preset", "veryfast", "-crf", "26", "-movflags", "+faststart"],
        )
        writer.send(None)
        for f in frames:
            if f.shape[:2] != (h, w):
                f = cv2.resize(f, (w, h))
            writer.send(np.ascontiguousarray(cv2.cvtColor(f[:h2, :w2], cv2.COLOR_BGR2RGB)))
        writer.close()
    except Exception as e:  # fall back to OpenCV writer
        log.warning("imageio-ffmpeg failed (%s), falling back to OpenCV mp4v", e)
        vw = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w2, h2))
        for f in frames:
            vw.write(cv2.resize(f, (w2, h2)))
        vw.release()
    return path

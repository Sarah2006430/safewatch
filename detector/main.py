"""AI detection service entrypoint.

Pulls the camera list (with zones) from the backend, runs one worker per
active camera and keeps them in sync as operators add / edit cameras.
"""
import logging
import os

# Prefer TCP for RTSP (far fewer corrupted frames over Wi-Fi / WAN) - must be set before cv2 loads
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp|stimeout;5000000")

import time  # noqa: E402
from concurrent.futures import ThreadPoolExecutor  # noqa: E402

from api_client import BackendClient  # noqa: E402
from camera_worker import CameraWorker  # noqa: E402
from config import settings  # noqa: E402
from stream_server import StreamHub, start_stream_server  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("detector")


def _already_running(port: int) -> bool:
    """True if another detector already serves the live-video port (two detectors would fight)."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def main():
    if _already_running(settings.stream_port):
        log.error("Another detector is already running (port %d is in use). Close the other "
                  "'SafeWatch detector' window first - only one detector may run at a time.", settings.stream_port)
        raise SystemExit(1)
    api = BackendClient(settings.backend_url, settings.api_key)
    hub = StreamHub()
    start_stream_server(hub, settings.stream_port)
    executor = ThreadPoolExecutor(max_workers=6, thread_name_prefix="io")
    workers: dict[int, CameraWorker] = {}
    log.info("Detector started. Backend: %s", settings.backend_url)

    # Each camera runs in its own thread; letting every PyTorch call use all cores makes the
    # threads fight over the CPU. A small intra-op pool per call gives far higher total FPS.
    import torch
    torch.set_num_threads(settings.torch_threads)
    log.info("PyTorch threads per inference: %d", settings.torch_threads)

    # Download / load weights once up-front so camera threads don't race to fetch them
    from ultralytics import YOLO
    YOLO(settings.pose_model)

    try:
        while True:
            try:
                cams = api.get_cameras()
            except Exception as e:
                log.error("Cannot reach backend (%s) - retrying", e)
                time.sleep(5)
                continue

            if settings.camera_ids:
                cams = [c for c in cams if c["id"] in settings.camera_ids]
            wanted = {c["id"]: c for c in cams if c.get("is_active")}

            for cid, cfg in wanted.items():
                w = workers.get(cid)
                if w and (not w.is_alive() or w.cfg["stream_url"] != cfg["stream_url"]):
                    w.stop()
                    w.join(timeout=5)
                    w = None
                if w is None:
                    workers[cid] = CameraWorker(cfg, api, hub, settings, executor)
                    workers[cid].start()
                else:
                    w.update_config(cfg)

            for cid in [cid for cid in workers if cid not in wanted]:
                log.info("Camera %s removed/disabled - stopping worker", cid)
                workers.pop(cid).stop()

            time.sleep(settings.camera_refresh_seconds)
    except KeyboardInterrupt:
        log.info("Shutting down")
        for w in workers.values():
            w.stop()


if __name__ == "__main__":
    main()

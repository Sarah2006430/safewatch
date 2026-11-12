"""Sends a fake incident (with a synthetic snapshot and clip) to the backend.

Useful to demo the dashboard without a camera:
    python simulate_incident.py --type fire --camera 1
"""
import argparse
import os
import tempfile

import cv2
import numpy as np

from api_client import BackendClient
from config import settings
from video import encode_jpeg, write_clip

TEXT = {"fall": "FALL DETECTED", "fire": "FIRE DETECTED", "smoke": "SMOKE DETECTED",
        "intrusion": "INTRUSION", "water_distress": "WATER DISTRESS"}


def frame(kind: str, i: int):
    img = np.full((540, 960, 3), 40, np.uint8)
    cv2.rectangle(img, (0, 380), (960, 540), (60, 70, 60), -1)
    if kind == "fire":
        for k in range(12):
            x = 420 + int(15 * np.sin(i / 2 + k)) + k * 10
            cv2.circle(img, (x, 360 - (k % 4) * 25), 30 + (i + k) % 15, (0, 120 + k * 8, 255), -1)
    elif kind == "smoke":
        for k in range(8):
            cv2.circle(img, (450 + k * 12, 300 - k * 20 - i), 50 + k * 4, (150, 150, 150), -1)
    elif kind == "fall":
        cv2.rectangle(img, (380, 330), (600, 380), (90, 220, 90), 3)
    elif kind == "intrusion":
        cv2.rectangle(img, (650, 40), (940, 520), (40, 40, 230), 2)
        cv2.rectangle(img, (720, 200 - i), (800, 470 - i), (60, 20, 220), 3)
    else:
        cv2.rectangle(img, (0, 300), (960, 540), (160, 110, 30), -1)
        cv2.circle(img, (480, 330 + int(10 * np.sin(i / 2))), 25, (200, 200, 230), -1)
    cv2.rectangle(img, (0, 500), (960, 540), (0, 0, 200), -1)
    cv2.putText(img, f"SIMULATED  ALERT: {TEXT[kind]}", (12, 528), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                (255, 255, 255), 2, cv2.LINE_AA)
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--type", choices=list(TEXT), default="fire")
    ap.add_argument("--camera", type=int, default=1)
    ap.add_argument("--confidence", type=float, default=0.87)
    args = ap.parse_args()

    api = BackendClient(settings.backend_url, settings.api_key)
    frames = [encode_jpeg(frame(args.type, i)) for i in range(60)]
    inc = api.create_incident(args.camera, args.type, args.confidence, {"simulated": True}, None, frames[30])
    print(f"Incident #{inc['id']} created (merged={inc.get('merged', False)})")

    fd, path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    write_clip(frames, 10, path)
    api.upload_clip(inc["id"], path)
    os.remove(path)
    print("Evidence clip uploaded")


if __name__ == "__main__":
    main()

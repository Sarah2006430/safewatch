"""Draws detections, zones and skeletons on frames for the live view and evidence."""
import time

import cv2

from analyzers import Detection
from geometry import Person, ZoneGeom

# BGR colours
COLORS = {
    "fall": (0, 0, 255),
    "fire": (0, 90, 255),
    "smoke": (170, 170, 170),
    "intrusion": (60, 20, 220),
    "water_distress": (255, 140, 0),
    "person": (90, 220, 90),
}
LABELS = {
    "fall": "FALL DETECTED",
    "fire": "FIRE DETECTED",
    "smoke": "SMOKE DETECTED",
    "intrusion": "INTRUSION",
    "water_distress": "WATER DISTRESS",
}
SKELETON = [(5, 6), (5, 7), (7, 9), (6, 8), (8, 10), (5, 11), (6, 12), (11, 12),
            (11, 13), (13, 15), (12, 14), (14, 16), (0, 5), (0, 6)]


def _label(img, text, x, y, color, scale=0.5):
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
    y = max(y, th + 6)
    cv2.rectangle(img, (x, y - th - 6), (x + tw + 6, y), color, -1)
    cv2.putText(img, text, (x + 3, y - 4), cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255), 1, cv2.LINE_AA)


def draw_zones(img, zones: list[ZoneGeom]):
    overlay = img.copy()
    for z in zones:
        color = (40, 40, 230) if z.kind == "restricted" else (230, 160, 30)
        cv2.fillPoly(overlay, [z.polygon], color)
    cv2.addWeighted(overlay, 0.18, img, 0.82, 0, img)
    for z in zones:
        color = (40, 40, 230) if z.kind == "restricted" else (230, 160, 30)
        cv2.polylines(img, [z.polygon], True, color, 2, cv2.LINE_AA)
        x, y = z.polygon[0]
        _label(img, f"{'RESTRICTED' if z.kind == 'restricted' else 'WATER'}: {z.name}", int(x) + 4, int(y) + 22, color, 0.45)


def draw_persons(img, persons: list[Person], tags: dict[int, str]):
    for p in persons:
        tag = tags.get(p.track_id, "")
        color = COLORS["person"]
        if tag.startswith("FALL") or tag.startswith("DOWN"):
            color = COLORS["fall"]
        elif tag.startswith("INTRUDER"):
            color = COLORS["intrusion"]
        elif tag.startswith("WATER"):
            color = COLORS["water_distress"]
        x1, y1, x2, y2 = map(int, p.box)
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        if p.kpts is not None:
            for a, b in SKELETON:
                if p.kpts[a][2] > 0.3 and p.kpts[b][2] > 0.3:
                    cv2.line(img, tuple(map(int, p.kpts[a][:2])), tuple(map(int, p.kpts[b][:2])), color, 1, cv2.LINE_AA)
        _label(img, f"#{p.track_id} {tag}".strip(), x1, y1 - 2, color, 0.45)


def draw_detection(img, d: Detection, thick: int = 3):
    color = COLORS.get(d.type, (0, 0, 255))
    if d.box:
        x1, y1, x2, y2 = map(int, d.box)
        cv2.rectangle(img, (x1, y1), (x2, y2), color, thick)
        _label(img, f"{LABELS.get(d.type, d.type)} {d.confidence:.0%}", x1, y1 - 4, color, 0.6)


def draw_header(img, camera_name: str, fps: float, alerts: list[Detection]):
    h, w = img.shape[:2]
    cv2.rectangle(img, (0, 0), (w, 28), (20, 20, 20), -1)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    cv2.putText(img, f"{camera_name}  |  {ts}  |  {fps:.1f} fps", (8, 19),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (230, 230, 230), 1, cv2.LINE_AA)
    if alerts:
        text = " / ".join(sorted({LABELS.get(a.type, a.type) for a in alerts}))
        cv2.rectangle(img, (0, h - 34), (w, h), (0, 0, 200), -1)
        cv2.putText(img, f"ALERT: {text}", (10, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (255, 255, 255), 2, cv2.LINE_AA)

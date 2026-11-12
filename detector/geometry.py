"""Person / zone geometry helpers and pixel -> GPS mapping."""
from dataclasses import dataclass

import cv2
import numpy as np

# COCO-17 keypoint indices
NOSE, L_EYE, R_EYE = 0, 1, 2
L_SHOULDER, R_SHOULDER = 5, 6
L_WRIST, R_WRIST = 9, 10
L_HIP, R_HIP = 11, 12
L_KNEE, R_KNEE = 13, 14
L_ANKLE, R_ANKLE = 15, 16
KP_CONF = 0.3


@dataclass
class Person:
    track_id: int
    box: tuple  # x1, y1, x2, y2 in pixels
    conf: float
    kpts: np.ndarray | None = None  # (17, 3): x, y, confidence

    @property
    def width(self) -> float:
        return self.box[2] - self.box[0]

    @property
    def height(self) -> float:
        return self.box[3] - self.box[1]

    @property
    def center(self) -> tuple:
        return ((self.box[0] + self.box[2]) / 2, (self.box[1] + self.box[3]) / 2)

    @property
    def foot(self) -> tuple:
        """Ground contact point: midpoint of ankles if visible, else bottom-centre of box."""
        k = self.kpts
        if k is not None:
            ankles = [k[i] for i in (L_ANKLE, R_ANKLE) if k[i][2] > KP_CONF]
            if ankles:
                return (float(np.mean([a[0] for a in ankles])), float(np.mean([a[1] for a in ankles])))
        return ((self.box[0] + self.box[2]) / 2, self.box[3])

    def kp(self, idx: int):
        if self.kpts is None or self.kpts[idx][2] < KP_CONF:
            return None
        return self.kpts[idx][:2]


def mean_point(points):
    pts = [p for p in points if p is not None]
    if not pts:
        return None
    return np.mean(pts, axis=0)


def torso_angle(p: Person) -> float | None:
    """Angle of the shoulder->hip line from vertical in degrees (0 = upright, 90 = horizontal)."""
    sh = mean_point([p.kp(L_SHOULDER), p.kp(R_SHOULDER)])
    hp = mean_point([p.kp(L_HIP), p.kp(R_HIP)])
    if sh is None or hp is None:
        return None
    dx, dy = hp[0] - sh[0], hp[1] - sh[1]
    if abs(dx) + abs(dy) < 1:
        return None
    return float(np.degrees(np.arctan2(abs(dx), abs(dy))))


@dataclass
class ZoneGeom:
    id: int
    name: str
    kind: str
    dwell_seconds: float
    polygon: np.ndarray  # int32 pixel polygon (N, 2)

    def contains(self, pt) -> bool:
        return cv2.pointPolygonTest(self.polygon, (float(pt[0]), float(pt[1])), False) >= 0


def build_zones(zones: list[dict], width: int, height: int) -> list[ZoneGeom]:
    out = []
    for z in zones:
        roi = z.get("roi") or []
        if len(roi) < 3:
            continue
        poly = np.array([[x * width, y * height] for x, y in roi], dtype=np.int32)
        out.append(ZoneGeom(z["id"], z["name"], z["kind"], float(z.get("dwell_seconds") or 2.0), poly))
    return out


class GeoMapper:
    """Maps image pixels to lat/lon using a 4-point ground-plane homography."""

    def __init__(self, calibration: dict | None, width: int, height: int):
        self.H = None
        if calibration and len(calibration.get("image", [])) == 4 and len(calibration.get("geo", [])) == 4:
            src = np.float32([[x * width, y * height] for x, y in calibration["image"]])
            dst = np.float32([[lon, lat] for lat, lon in calibration["geo"]])
            self.H = cv2.getPerspectiveTransform(src, dst)

    def to_latlon(self, pt) -> tuple | None:
        if self.H is None or pt is None:
            return None
        res = cv2.perspectiveTransform(np.float32([[pt]]), self.H)[0][0]
        return float(res[1]), float(res[0])

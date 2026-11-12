"""Fire and smoke detection.

Two modes:
  1. YOLO model trained for fire/smoke (recommended - see train_fire_smoke.py).
  2. Fallback OpenCV heuristic when no model is configured:
     * fire  = bright red/orange/yellow pixels (HSV + RGB + YCrCb colour rules)
               that flicker (change between frames)
     * smoke = moving low-saturation grey regions that blur the background
Both modes require temporal persistence across several frames before alerting,
which removes most single-frame false positives.
"""
import logging
import os
from collections import deque

import cv2
import numpy as np

from geometry import Person

from . import Detection, clamp

log = logging.getLogger("fire_smoke")


# Minimum mean confidence of a sustained detection before the YOLO model raises an alert.
# Chosen on the FIRESENSE benchmark (benchmark_datasets.py): keeps every detected fire while
# removing most false alarms from the deliberately confusing negative videos.
MODEL_MIN_ALERT = {"fire": 0.45, "smoke": 0.35}


class FireSmokeAnalyzer:
    def __init__(self, model_path: str = "", conf: float = 0.35, device: str = "", imgsz: int = 320):
        self.conf = conf
        self.device = device
        self.model = None
        self.imgsz = imgsz
        if model_path and os.path.exists(model_path):
            from ultralytics import YOLO

            self.model = YOLO(model_path)
            log.info("Fire/smoke YOLO model loaded: %s (%s)", model_path, self.model.names)
        elif model_path:
            log.warning("FIRE_SMOKE_MODEL '%s' not found - using OpenCV heuristic", model_path)

        self.fire_hist: deque = deque(maxlen=15)
        self.smoke_hist: deque = deque(maxlen=30)
        self.bg = cv2.createBackgroundSubtractorMOG2(history=300, varThreshold=25, detectShadows=False)
        self.prev_fire = None
        self.frames = 0

    @property
    def method(self) -> str:
        return "yolo" if self.model else "heuristic"

    # ------------------------------------------------------------ model
    def _model_scores(self, frame):
        kw = {"conf": self.conf, "verbose": False, "imgsz": self.imgsz}
        if self.device:
            kw["device"] = self.device
        res = self.model.predict(frame, **kw)[0]
        best = {"fire": (0.0, None), "smoke": (0.0, None)}
        for box in res.boxes:
            name = str(self.model.names[int(box.cls)]).lower()
            kind = "fire" if ("fire" in name or "flame" in name) else "smoke" if "smoke" in name else None
            c = float(box.conf)
            if kind and c > best[kind][0]:
                best[kind] = (c, tuple(float(v) for v in box.xyxy[0].tolist()))
        return best

    # -------------------------------------------------------- heuristic
    def _heuristic_scores(self, frame, persons: list[Person]):
        h, w = frame.shape[:2]
        scale = 320 / w
        small = cv2.resize(frame, (320, int(h * scale)))
        sh, sw = small.shape[:2]
        total = sh * sw

        fg = self.bg.apply(small)
        self.frames += 1
        best = {"fire": (0.0, None), "smoke": (0.0, None)}
        if self.frames < 30:  # background model warming up
            return best
        if cv2.countNonZero(fg) / total > 0.6:  # camera moved / lighting jump
            return best

        person_mask = np.zeros((sh, sw), np.uint8)
        for p in persons:
            x1, y1, x2, y2 = [int(v * scale) for v in p.box]
            cv2.rectangle(person_mask, (x1, y1), (x2, y2), 255, -1)
        not_person = cv2.bitwise_not(person_mask)

        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
        ycc = cv2.cvtColor(small, cv2.COLOR_BGR2YCrCb)
        b, g, r = cv2.split(small.astype(np.int16))
        y, cr, cb = cv2.split(ycc.astype(np.int16))

        # ---- fire
        hsv_rule = cv2.inRange(hsv, (0, 70, 170), (35, 255, 255)) > 0
        rgb_rule = (r > 180) & (r >= g) & (g > b) & ((r - b) > 60)
        ycc_rule = (y > cb) & (cr > cb) & (y > y.mean())
        fire = ((hsv_rule & rgb_rule & ycc_rule).astype(np.uint8) * 255) & not_person
        fire = cv2.morphologyEx(fire, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        fire_ratio = cv2.countNonZero(fire) / total
        flicker = 0.0
        if self.prev_fire is not None and fire_ratio > 0:
            union = cv2.countNonZero(cv2.bitwise_or(fire, self.prev_fire))
            flicker = cv2.countNonZero(cv2.bitwise_xor(fire, self.prev_fire)) / max(union, 1)
        self.prev_fire = fire
        moving_fire = cv2.countNonZero(cv2.bitwise_and(fire, cv2.dilate(fg, np.ones((5, 5), np.uint8))))
        moving_frac = moving_fire / max(cv2.countNonZero(fire), 1)
        if fire_ratio > 0.002 and (flicker > 0.12 or moving_frac > 0.2):
            score = clamp(0.4 + fire_ratio * 15 + 0.4 * flicker, 0, 0.92)
            best["fire"] = (score, self._largest_box(fire, scale))

        # ---- smoke
        grey = cv2.inRange(hsv, (0, 0, 90), (180, 55, 230))
        smoke = cv2.bitwise_and(grey, fg)
        smoke = cv2.bitwise_and(smoke, not_person)
        smoke = cv2.morphologyEx(smoke, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
        smoke = cv2.morphologyEx(smoke, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        smoke_ratio = cv2.countNonZero(smoke) / total
        if smoke_ratio > 0.01:
            gray_img = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            lap = cv2.Laplacian(gray_img, cv2.CV_64F)
            region_sharp = lap[smoke > 0].var() if np.any(smoke) else 0
            global_sharp = lap.var() + 1e-6
            blur = clamp(1 - region_sharp / global_sharp)
            if blur > 0.35:
                score = clamp(0.35 + smoke_ratio * 4 + 0.3 * blur, 0, 0.85)
                best["smoke"] = (score, self._largest_box(smoke, scale))
        return best

    @staticmethod
    def _largest_box(mask, scale):
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        x, y, w, h = cv2.boundingRect(max(contours, key=cv2.contourArea))
        return (x / scale, y / scale, (x + w) / scale, (y + h) / scale)

    # ----------------------------------------------------------- public
    def update(self, frame, persons: list[Person], enabled: set) -> list[Detection]:
        if not ({"fire", "smoke"} & enabled):
            return []
        best = self._model_scores(frame) if self.model else self._heuristic_scores(frame, persons)
        out = []
        for kind, hist, need in (("fire", self.fire_hist, 0.6), ("smoke", self.smoke_hist, 0.7)):
            score, box = best[kind]
            hist.append((score, box))
            if kind not in enabled or len(hist) < hist.maxlen // 2:
                continue
            positives = [(s, b) for s, b in hist if s > 0]
            if len(positives) / len(hist) >= need:
                conf = float(np.mean([s for s, _ in positives]))
                if self.model and conf < MODEL_MIN_ALERT[kind]:
                    continue  # weak, flickering hits: typical of orange lights / sunsets, not flames
                last_box = next((b for s, b in reversed(positives) if b is not None), None)
                point = ((last_box[0] + last_box[2]) / 2, last_box[3]) if last_box else None
                out.append(Detection(kind, conf, box=last_box, point=point,
                                     details={"method": self.method,
                                              "persistence": round(len(positives) / len(hist), 2)}))
                hist.clear()
        return out

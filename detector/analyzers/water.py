"""Signs of distress near / in water.

For each tracked person inside a water zone we combine behavioural cues that
lifeguard research associates with drowning / distress:
  * arms raised above the shoulders (waving / instinctive drowning response)
  * body submerged: head visible but hips/knees not visible
  * vertical bobbing of the head with little horizontal progress
and additionally flag a person who disappears from view while in the water
(possible submersion).
"""
from collections import deque
from dataclasses import dataclass, field

import numpy as np

from geometry import (L_EYE, L_HIP, L_KNEE, L_SHOULDER, L_WRIST, NOSE, R_EYE, R_HIP, R_KNEE,
                      R_SHOULDER, R_WRIST, Person, ZoneGeom)

from . import Detection, clamp

WINDOW = 4.0  # seconds of history used for scoring


@dataclass
class _Track:
    entered: float
    last_seen: float
    zone: ZoneGeom
    last_pos: tuple = (0, 0)
    last_box: tuple | None = None
    hist: deque = field(default_factory=lambda: deque(maxlen=80))  # (t, head_y, cx, arms, submerged)
    high_since: float | None = None
    reported: bool = False
    reported_missing: bool = False
    score: float = 0.0


def _kp_vis(p: Person, idx: int, thr: float = 0.3) -> bool:
    return p.kpts is not None and p.kpts[idx][2] >= thr


def arms_raised(p: Person) -> bool:
    if p.kpts is None:
        return False
    shoulders = [p.kpts[i][1] for i in (L_SHOULDER, R_SHOULDER) if _kp_vis(p, i)]
    ref = min(shoulders) if shoulders else (p.kpts[NOSE][1] if _kp_vis(p, NOSE) else None)
    if ref is None:
        return False
    margin = 0.08 * p.height
    return any(_kp_vis(p, w) and p.kpts[w][1] < ref - margin for w in (L_WRIST, R_WRIST))


def submerged(p: Person) -> bool:
    if p.kpts is None:
        return False
    head = any(_kp_vis(p, i, 0.4) for i in (NOSE, L_EYE, R_EYE))
    lower = any(_kp_vis(p, i, 0.25) for i in (L_HIP, R_HIP, L_KNEE, R_KNEE))
    return head and not lower


def head_y(p: Person) -> float:
    if p.kpts is not None:
        pts = [p.kpts[i][1] for i in (NOSE, L_EYE, R_EYE) if _kp_vis(p, i)]
        if pts:
            return float(np.mean(pts))
    return float(p.box[1])


class WaterDistressAnalyzer:
    def __init__(self, missing_seconds: float = 3.0, sustain_seconds: float = 1.5, threshold: float = 0.55):
        self.missing_seconds = missing_seconds
        self.sustain_seconds = sustain_seconds
        self.threshold = threshold
        self.tracks: dict[int, _Track] = {}

    def scores(self) -> dict[int, float]:
        return {tid: tr.score for tid, tr in self.tracks.items()}

    def update(self, persons: list[Person], zones: list[ZoneGeom], t: float, frame_shape) -> list[Detection]:
        h, w = frame_shape[:2]
        water = [z for z in zones if z.kind == "water"]
        out: list[Detection] = []
        if not water:
            self.tracks.clear()
            return out

        seen = set()
        for p in persons:
            if p.track_id < 0:
                continue  # not yet a confirmed track (one-off detection) - too noisy for water logic
            zone = next((z for z in water if z.contains(p.center) or z.contains(p.foot)), None)
            if zone is None:
                self.tracks.pop(p.track_id, None)
                continue
            seen.add(p.track_id)
            tr = self.tracks.get(p.track_id) or _Track(entered=t, last_seen=t, zone=zone)
            self.tracks[p.track_id] = tr
            tr.last_seen, tr.zone, tr.last_pos, tr.last_box = t, zone, p.center, p.box
            tr.hist.append((t, head_y(p) / h, p.center[0] / w, arms_raised(p), submerged(p)))
            while tr.hist and t - tr.hist[0][0] > WINDOW:
                tr.hist.popleft()

            if len(tr.hist) < 5:
                continue
            arr = np.array([(hy, cx, a, s) for _, hy, cx, a, s in tr.hist], dtype=float)
            arms_ratio = arr[:, 2].mean()
            sub_ratio = arr[:, 3].mean()
            rel_h = max(p.height / h, 0.02)
            bob = clamp(arr[:, 0].std() / rel_h / 0.15)
            stationary = 1.0 if (arr[:, 1].max() - arr[:, 1].min()) < 0.05 else 0.0
            score = 0.35 * arms_ratio + 0.30 * sub_ratio + 0.20 * bob + 0.15 * stationary * (sub_ratio > 0.4)
            tr.score = float(score)

            if t - tr.entered < zone.dwell_seconds or score < self.threshold:
                tr.high_since = None
                continue
            tr.high_since = tr.high_since or t
            if not tr.reported and t - tr.high_since >= self.sustain_seconds:
                tr.reported = True
                out.append(Detection(
                    "water_distress", clamp(0.5 + 0.5 * score), box=p.box, point=p.center,
                    details={"zone": zone.name, "zone_id": zone.id, "track_id": p.track_id,
                             "arms_raised_ratio": round(arms_ratio, 2), "submerged_ratio": round(sub_ratio, 2),
                             "bobbing": round(bob, 2), "seconds_in_water": round(t - tr.entered, 1),
                             "kind": "distress_behaviour"},
                ))

        # People who vanished while in the water -> possible submersion
        for tid, tr in list(self.tracks.items()):
            if tid in seen:
                continue
            gone = t - tr.last_seen
            x, y = tr.last_pos
            near_edge = x < 0.05 * w or x > 0.95 * w or y < 0.05 * h or y > 0.95 * h
            if (not tr.reported_missing and self.missing_seconds <= gone < 12
                    and tr.last_seen - tr.entered >= 2.0 and len(tr.hist) >= 10 and not near_edge):
                tr.reported_missing = True
                sub = float(np.mean([s for *_, s in tr.hist])) if tr.hist else 0.0
                out.append(Detection(
                    "water_distress", clamp(0.65 + 0.25 * sub), box=tr.last_box, point=tr.last_pos,
                    details={"zone": tr.zone.name, "zone_id": tr.zone.id, "track_id": tid,
                             "kind": "possible_submersion", "missing_seconds": round(gone, 1)},
                ))
            if gone > 15:
                del self.tracks[tid]
        return out

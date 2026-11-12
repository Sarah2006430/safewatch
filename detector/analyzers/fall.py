"""Fall detection from YOLO pose keypoints + tracking.

A fall is reported when a tracked person goes from an upright posture to a
lying posture within a short window (optionally with a rapid downward drop of
the body centre) and stays down for a confirmation period. A person found
lying for a long time without an observed transition is reported as a
lower-confidence "person down".
"""
from collections import deque
from dataclasses import dataclass, field

from geometry import Person, torso_angle

from . import Detection, clamp


@dataclass
class _Track:
    history: deque = field(default_factory=lambda: deque(maxlen=60))  # (t, cy, h, upright)
    lying_since: float | None = None
    reported: bool = False
    last_seen: float = 0.0
    state: str = "unknown"
    box: tuple | None = None
    drop_t: float | None = None   # time a rapid drop from upright was last observed
    drop_score: float = 0.0


class FallAnalyzer:
    def __init__(self, confirm_seconds: float = 1.0, transition_window: float = 2.5,
                 person_down_seconds: float = 8.0, lost_seconds: float = 1.5):
        self.confirm_seconds = confirm_seconds
        self.transition_window = transition_window
        self.person_down_seconds = person_down_seconds
        self.lost_seconds = lost_seconds
        self.tracks: dict[int, _Track] = {}

    @staticmethod
    def posture(p: Person) -> tuple[str, float | None, float]:
        angle = torso_angle(p)
        aspect = p.width / max(p.height, 1.0)
        if (angle is not None and angle >= 60 and aspect >= 0.8) or aspect >= 1.4:
            return "lying", angle, aspect
        if (angle is not None and angle <= 35 and aspect < 0.9) or (angle is None and aspect < 0.7):
            return "upright", angle, aspect
        return "unknown", angle, aspect

    def states(self) -> dict[int, str]:
        return {tid: tr.state for tid, tr in self.tracks.items()}

    def _associate(self, persons: list[Person], t: float) -> None:
        """Re-attach a person to their old track when the tracker switched IDs.

        When someone falls, the detector's confidence for them usually drops and
        the shape changes abruptly, so ByteTrack often loses the track and starts
        a new one (or returns no ID at all). Without this, the "upright" history
        would be lost exactly at the moment of the fall.
        """
        current = {p.track_id for p in persons}
        lost = {tid: tr for tid, tr in self.tracks.items()
                if tid not in current and tr.box is not None and t - tr.last_seen <= self.transition_window}
        for p in persons:
            if p.track_id in self.tracks or not lost:
                continue
            px, py = p.center
            best, best_d = None, 1e9
            for tid, tr in lost.items():
                x1, y1, x2, y2 = tr.box
                size = max(x2 - x1, y2 - y1, 1.0)
                d = ((px - (x1 + x2) / 2) ** 2 + (py - (y1 + y2) / 2) ** 2) ** 0.5 / size
                if d < best_d:
                    best, best_d = tid, d
            if best is not None and best_d <= 1.0:
                self.tracks[p.track_id] = self.tracks.pop(best)
                del lost[best]

    def update(self, persons: list[Person], t: float) -> list[Detection]:
        out: list[Detection] = []
        self._associate(persons, t)
        for p in persons:
            tr = self.tracks.setdefault(p.track_id, _Track())
            tr.last_seen = t
            tr.box = p.box
            state, angle, aspect = self.posture(p)
            tr.state = state
            cy = p.center[1]
            tr.history.append((t, cy, p.height, state == "upright"))

            # Rapid drop from an upright posture (used when the person is then lost on the floor)
            if state != "upright":
                recent_up = [(ht, hcy, hh) for ht, hcy, hh, up in tr.history if up and t - ht <= 1.5]
                if recent_up:
                    _, ucy, uh = recent_up[-1]
                    drop = (cy - ucy) / max(uh, 1.0)
                    if drop >= 0.33:
                        tr.drop_t, tr.drop_score = t, max(tr.drop_score, clamp(drop / 0.5))
            else:
                tr.drop_t, tr.drop_score = None, 0.0

            if state != "lying":
                if state == "upright":
                    tr.lying_since = None
                    tr.reported = False
                continue

            tr.lying_since = tr.lying_since or t
            down_for = t - tr.lying_since
            if tr.reported:
                continue

            # Was the person upright shortly before lying down?
            window_start = tr.lying_since - self.transition_window
            upright_before = [(ht, hcy, hh) for ht, hcy, hh, up in tr.history
                              if up and window_start <= ht <= tr.lying_since]
            descent = 0.0
            if upright_before:
                _, ucy, uh = upright_before[-1]
                descent = clamp((cy - ucy) / max(uh, 1.0) / 0.4)

            if upright_before and down_for >= self.confirm_seconds:
                conf = clamp(0.55 + 0.25 * descent + 0.2 * p.conf)
                out.append(Detection(
                    "fall", conf, box=p.box, point=p.center,
                    details={"track_id": p.track_id, "torso_angle": angle and round(angle, 1),
                             "aspect_ratio": round(aspect, 2), "descent_score": round(descent, 2),
                             "down_seconds": round(down_for, 1), "kind": "fall"},
                ))
                tr.reported = True
            elif down_for >= self.person_down_seconds:
                out.append(Detection(
                    "fall", clamp(0.45 + 0.2 * p.conf), box=p.box, point=p.center,
                    details={"track_id": p.track_id, "kind": "person_down",
                             "down_seconds": round(down_for, 1), "aspect_ratio": round(aspect, 2)},
                ))
                tr.reported = True

        # Person dropped fast and then vanished (detectors often miss people curled on the
        # floor or partly out of frame). Lower confidence - the operator verifies it.
        seen = {p.track_id for p in persons}
        for tid, tr in self.tracks.items():
            if (tid not in seen and not tr.reported and tr.drop_t is not None and tr.box is not None
                    and t - tr.last_seen >= self.lost_seconds and tr.last_seen - tr.drop_t <= 0.6):
                x1, y1, x2, y2 = tr.box
                out.append(Detection(
                    "fall", clamp(0.5 + 0.25 * tr.drop_score), box=tr.box, point=((x1 + x2) / 2, y2),
                    details={"track_id": tid, "kind": "fall_then_lost", "descent_score": round(tr.drop_score, 2),
                             "lost_seconds": round(t - tr.last_seen, 1)},
                ))
                tr.reported = True

        for tid in [tid for tid, tr in self.tracks.items() if t - tr.last_seen > 10]:
            del self.tracks[tid]
        return out

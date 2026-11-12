"""Restricted-area intrusion: a person's ground point stays inside a restricted
zone polygon for longer than the zone's dwell time."""
from geometry import Person, ZoneGeom

from . import Detection, clamp


class IntrusionAnalyzer:
    def __init__(self, exit_grace: float = 2.0):
        self.exit_grace = exit_grace
        self.state: dict[tuple, dict] = {}  # (track_id, zone_id) -> {enter, last, reported}

    def intruders(self) -> set[int]:
        return {tid for (tid, _), s in self.state.items() if s["reported"]}

    def update(self, persons: list[Person], zones: list[ZoneGeom], t: float) -> list[Detection]:
        out: list[Detection] = []
        restricted = [z for z in zones if z.kind == "restricted"]
        for p in persons:
            foot = p.foot
            for z in restricted:
                if not z.contains(foot):
                    continue
                s = self.state.setdefault((p.track_id, z.id), {"enter": t, "last": t, "reported": False})
                s["last"] = t
                dwell = t - s["enter"]
                if not s["reported"] and dwell >= z.dwell_seconds:
                    s["reported"] = True
                    out.append(Detection(
                        "intrusion", clamp(0.6 + 0.4 * p.conf), box=p.box, point=foot,
                        details={"zone_id": z.id, "zone": z.name, "track_id": p.track_id,
                                 "dwell_seconds": round(dwell, 1)},
                    ))
        for key in [k for k, s in self.state.items() if t - s["last"] > self.exit_grace]:
            del self.state[key]
        return out

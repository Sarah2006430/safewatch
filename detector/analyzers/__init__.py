from dataclasses import dataclass, field


@dataclass
class Detection:
    type: str  # fall | smoke | fire | intrusion | water_distress
    confidence: float
    box: tuple | None = None  # pixel box to highlight on evidence
    point: tuple | None = None  # pixel ground point used for geo-tagging
    details: dict = field(default_factory=dict)


def clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))

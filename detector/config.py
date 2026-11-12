import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _f(name: str, default: float) -> float:
    return float(os.getenv(name, default))


@dataclass
class Settings:
    backend_url: str = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
    api_key: str = os.getenv("DETECTOR_API_KEY", "detector-secret-key")

    pose_model: str = os.getenv("POSE_MODEL", "yolo11n-pose.pt")
    fire_smoke_model: str = os.getenv("FIRE_SMOKE_MODEL", "")
    device: str = os.getenv("DEVICE", "")

    person_conf: float = _f("PERSON_CONF", 0.15)
    torch_threads: int = int(os.getenv("TORCH_THREADS", "2"))
    pose_imgsz: int = int(os.getenv("POSE_IMGSZ", "480"))
    fire_smoke_imgsz: int = int(os.getenv("FIRE_SMOKE_IMGSZ", "320"))
    fire_smoke_conf: float = _f("FIRE_SMOKE_CONF", 0.35)
    process_fps: float = _f("PROCESS_FPS", 10)
    max_frame_width: int = int(_f("MAX_FRAME_WIDTH", 960))

    clip_pre_seconds: float = _f("CLIP_PRE_SECONDS", 5)
    clip_post_seconds: float = _f("CLIP_POST_SECONDS", 6)
    cooldown_seconds: float = _f("COOLDOWN_SECONDS", 60)

    stream_port: int = int(_f("STREAM_PORT", 8100))
    camera_refresh_seconds: float = _f("CAMERA_REFRESH_SECONDS", 15)
    camera_ids: set = field(
        default_factory=lambda: {int(x) for x in os.getenv("CAMERA_IDS", "").split(",") if x.strip()}
    )


settings = Settings()

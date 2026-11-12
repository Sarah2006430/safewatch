"""Seeds default users, response units and a demo camera on first start."""
import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import SessionLocal
from .geo import make_point
from .models import Camera, ResponseUnit, User, Zone
from .security import hash_password

log = logging.getLogger("seed")


async def _ensure_admin(db: AsyncSession) -> None:
    exists = (await db.execute(select(User).where(User.username == settings.admin_username))).scalar_one_or_none()
    if not exists:
        db.add(User(
            username=settings.admin_username, full_name="Administrator", role="admin",
            password_hash=hash_password(settings.admin_password),
        ))
        log.info("Created admin user '%s'", settings.admin_username)


async def _seed_demo(db: AsyncSession) -> None:
    if (await db.execute(select(func.count()).select_from(ResponseUnit))).scalar():
        return
    lat0, lon0 = settings.default_lat, settings.default_lon

    def near(dlat, dlon):
        return make_point(lat0 + dlat, lon0 + dlon)

    units = [
        ResponseUnit(name="Police Patrol 101", agency="police", location=near(0.012, -0.008), contact="100"),
        ResponseUnit(name="Police Patrol 102", agency="police", location=near(-0.018, 0.015), contact="100"),
        ResponseUnit(name="Police Patrol 103", agency="police", location=near(0.025, 0.022), contact="100"),
        ResponseUnit(name="Ambulance A1", agency="medical", location=near(-0.006, -0.014), contact="108"),
        ResponseUnit(name="Ambulance A2", agency="medical", location=near(0.019, 0.004), contact="108"),
        ResponseUnit(name="Ambulance A3", agency="medical", location=near(-0.027, -0.021), contact="108"),
        ResponseUnit(name="Fire Engine F1", agency="fire", location=near(0.008, 0.019), contact="101"),
        ResponseUnit(name="Fire Engine F2", agency="fire", location=near(-0.022, 0.006), contact="101"),
        ResponseUnit(name="Water Rescue R1", agency="rescue", location=near(0.003, 0.027), contact="112"),
        ResponseUnit(name="Disaster Rescue R2", agency="rescue", location=near(-0.014, -0.029), contact="112"),
    ]
    db.add_all(units)
    await db.flush()

    db.add_all([
        User(username="operator", full_name="Control Room Operator", role="operator",
             password_hash=hash_password("operator123")),
        User(username="ambulance1", full_name="Ambulance A1 Crew", role="responder",
             unit_id=units[3].id, password_hash=hash_password("responder123")),
        User(username="police1", full_name="Patrol 101 Officer", role="responder",
             unit_id=units[0].id, password_hash=hash_password("responder123")),
    ])

    webcam = Camera(
        name="Demo Webcam (Main Gate)", stream_url="0", location=near(0.0, 0.0),
        address="Main Gate, Demo Campus", heading=90.0,
    )
    lake = Camera(
        name="Lakeside IP Camera", stream_url="rtsp://admin:password@192.168.1.64:554/Streaming/Channels/101",
        location=near(0.004, 0.024), address="Lake Promenade", is_active=False,
        detections=["fall", "water_distress", "intrusion"],
    )
    db.add_all([webcam, lake])
    await db.flush()
    db.add_all([
        Zone(camera_id=webcam.id, name="Server Room Door", kind="restricted",
             roi=[[0.70, 0.05], [0.98, 0.05], [0.98, 0.98], [0.70, 0.98]], dwell_seconds=2.0),
        Zone(camera_id=lake.id, name="Lake (no swimming)", kind="water",
             roi=[[0.0, 0.55], [1.0, 0.45], [1.0, 1.0], [0.0, 1.0]], dwell_seconds=3.0),
    ])
    log.info("Seeded demo response units, users and cameras")


async def seed() -> None:
    async with SessionLocal() as db:
        await _ensure_admin(db)
        if settings.seed_demo_data:
            await _seed_demo(db)
        await db.commit()

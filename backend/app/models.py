"""Database models (PostgreSQL + PostGIS).

All locations are stored as PostGIS GEOGRAPHY (WGS84 / SRID 4326) so that
distance queries (ST_Distance) return metres directly and spatial GiST
indexes make nearest-responder lookups fast.
"""
from datetime import datetime, timezone

from geoalchemy2 import Geography
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base

def utcnow() -> datetime:
    return datetime.now(timezone.utc)


ALL_DETECTIONS = ["fall", "smoke", "fire", "intrusion", "water_distress"]


class ResponseUnit(Base):
    """A police car, ambulance, fire engine or rescue team."""

    __tablename__ = "response_units"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    agency: Mapped[str] = mapped_column(String(16), index=True)  # police|medical|fire|rescue
    location = mapped_column(Geography(geometry_type="POINT", srid=4326, spatial_index=True))
    status: Mapped[str] = mapped_column(String(16), default="available", index=True)
    contact: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    full_name: Mapped[str] = mapped_column(String(128), default="")
    password_hash: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(16), default="operator")  # admin|operator|responder
    unit_id: Mapped[int | None] = mapped_column(
        ForeignKey("response_units.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    # rtsp://user:pass@ip:554/stream, http://.../video, a file path, or a webcam index like "0"
    stream_url: Mapped[str] = mapped_column(String(1024))
    location = mapped_column(Geography(geometry_type="POINT", srid=4326, spatial_index=True))
    address: Mapped[str] = mapped_column(String(256), default="")
    heading: Mapped[float | None] = mapped_column(Float, nullable=True)  # compass direction camera faces
    detections: Mapped[list] = mapped_column(JSONB, default=lambda: list(ALL_DETECTIONS))
    # Optional ground-plane homography: {"image": [[x,y]*4 normalised], "geo": [[lat,lon]*4]}
    calibration: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(16), default="unknown")  # unknown|online|offline|error
    status_message: Mapped[str] = mapped_column(String(256), default="")
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Zone(Base):
    """A region inside a camera's view: restricted area or water body."""

    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    kind: Mapped[str] = mapped_column(String(16))  # restricted|water
    # Polygon in image space, normalised 0..1: [[x, y], ...]
    roi: Mapped[list] = mapped_column(JSONB)
    # Optional real-world footprint shown on the map
    area = mapped_column(Geography(geometry_type="POLYGON", srid=4326), nullable=True)
    dwell_seconds: Mapped[float] = mapped_column(Float, default=2.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(32), index=True)  # fall|smoke|fire|intrusion|water_distress
    severity: Mapped[str] = mapped_column(String(16), default="high")  # low|medium|high|critical
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    # pending -> verified -> dispatched -> resolved   (or pending -> false_alarm)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    camera_id: Mapped[int | None] = mapped_column(
        ForeignKey("cameras.id", ondelete="SET NULL"), nullable=True, index=True
    )
    location = mapped_column(Geography(geometry_type="POINT", srid=4326, spatial_index=True))
    snapshot_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    clip_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    detection_count: Mapped[int] = mapped_column(default=1)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    last_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    verified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")


Index("ix_incidents_camera_type_status", Incident.camera_id, Incident.type, Incident.status)


class Dispatch(Base):
    __tablename__ = "dispatches"

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("response_units.id", ondelete="CASCADE"), index=True)
    # assigned|acknowledged|en_route|on_scene|completed|cancelled
    status: Mapped[str] = mapped_column(String(16), default="assigned")
    distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    eta_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    dispatched_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class IncidentEvent(Base):
    """Audit timeline of everything that happened to an incident."""

    __tablename__ = "incident_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(32))
    actor: Mapped[str] = mapped_column(String(64), default="system")
    message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SessionEvent(Base):
    """Sign-up / login / logout history (kept across restarts)."""
    __tablename__ = "session_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    username: Mapped[str] = mapped_column(String(255), default="")
    kind: Mapped[str] = mapped_column(String(16))  # signup | login | logout | failed
    ip: Mapped[str] = mapped_column(String(64), default="")
    user_agent: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

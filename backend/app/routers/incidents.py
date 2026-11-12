import json
import os
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..geo import make_point, point_latlon
from ..models import Camera, Dispatch, Incident, IncidentEvent, ResponseUnit, User
from ..realtime import manager
from ..schemas import DispatchIn, NoteIn
from ..security import any_principal, require_detector, staff
from ..serializers import dispatch_dict, event_dict, incident_dict, unit_dict
from ..services.dispatch import (
    AGENCIES_FOR,
    SEVERITY_FOR,
    estimate_eta,
    log_event,
    nearest_units,
    suggestions,
    unit_distance,
)

router = APIRouter(prefix="/api/incidents", tags=["incidents"])

OPEN_STATUSES = ("pending", "verified", "dispatched")
ACTIVE_DISPATCH = ("assigned", "acknowledged", "en_route", "on_scene")
LABELS = {
    "fall": "Person fall",
    "smoke": "Smoke",
    "fire": "Fire",
    "intrusion": "Restricted-area intrusion",
    "water_distress": "Distress near water",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _save_media(rel_path: str, data: bytes) -> None:
    full = os.path.join(settings.media_dir, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "wb") as f:
        f.write(data)


async def _get(db: AsyncSession, incident_id: int) -> Incident:
    inc = await db.get(Incident, incident_id)
    if not inc:
        raise HTTPException(404, "Incident not found")
    return inc


async def _camera(db: AsyncSession, inc: Incident) -> Camera | None:
    return await db.get(Camera, inc.camera_id) if inc.camera_id else None


async def _summary(db: AsyncSession, inc: Incident) -> dict:
    return incident_dict(inc, await _camera(db, inc))


async def _full(db: AsyncSession, inc: Incident) -> dict:
    data = await _summary(db, inc)
    rows = (
        await db.execute(
            select(Dispatch, ResponseUnit)
            .join(ResponseUnit, ResponseUnit.id == Dispatch.unit_id)
            .where(Dispatch.incident_id == inc.id)
            .order_by(Dispatch.id)
        )
    ).all()
    events = (
        await db.execute(
            select(IncidentEvent).where(IncidentEvent.incident_id == inc.id).order_by(IncidentEvent.id)
        )
    ).scalars()
    data["dispatches"] = [dispatch_dict(d, u) for d, u in rows]
    data["events"] = [event_dict(e) for e in events]
    data["recommended_agencies"] = AGENCIES_FOR.get(inc.type, [])
    data["suggestions"] = await suggestions(db, inc) if inc.status in OPEN_STATUSES else []
    return data


def _actor(user: User) -> str:
    return user.full_name or user.username


# ------------------------------------------------------------------ read
@router.get("/stats")
async def stats(db: AsyncSession = Depends(get_db), _=Depends(staff)):
    now = _now()
    since = now - timedelta(hours=24)
    week = now - timedelta(days=7)

    open_by_status = dict(
        (await db.execute(
            select(Incident.status, func.count()).where(Incident.status.in_(OPEN_STATUSES)).group_by(Incident.status)
        )).all()
    )
    by_type = dict(
        (await db.execute(
            select(Incident.type, func.count()).where(Incident.detected_at >= since).group_by(Incident.type)
        )).all()
    )
    false_alarms = (await db.execute(
        select(func.count()).where(Incident.status == "false_alarm", Incident.detected_at >= since)
    )).scalar() or 0

    avg_verify = (await db.execute(
        select(func.avg(func.extract("epoch", Incident.verified_at - Incident.detected_at)))
        .where(Incident.verified_at.isnot(None), Incident.detected_at >= week)
    )).scalar()
    avg_dispatch = (await db.execute(
        select(func.avg(func.extract("epoch", Incident.dispatched_at - Incident.detected_at)))
        .where(Incident.dispatched_at.isnot(None), Incident.detected_at >= week)
    )).scalar()

    hour = func.date_trunc("hour", Incident.detected_at)
    hourly = (await db.execute(
        select(hour, func.count()).where(Incident.detected_at >= since).group_by(hour).order_by(hour)
    )).all()

    units = (await db.execute(
        select(ResponseUnit.agency, ResponseUnit.status, func.count()).group_by(ResponseUnit.agency, ResponseUnit.status)
    )).all()
    unit_summary: dict = {}
    for agency, status, count in units:
        unit_summary.setdefault(agency, {})[status] = count

    cams = dict((await db.execute(select(Camera.status, func.count()).group_by(Camera.status))).all())

    total_24h = sum(by_type.values())
    return {
        "open": open_by_status,
        "open_total": sum(open_by_status.values()),
        "last_24h": {"total": total_24h, "by_type": by_type, "false_alarms": false_alarms},
        "false_alarm_rate": round(false_alarms / total_24h, 3) if total_24h else 0,
        "avg_seconds_to_verify": round(float(avg_verify), 1) if avg_verify else None,
        "avg_seconds_to_dispatch": round(float(avg_dispatch), 1) if avg_dispatch else None,
        "hourly": [{"hour": h.isoformat(), "count": c} for h, c in hourly],
        "units": unit_summary,
        "cameras": cams,
    }


@router.get("")
async def list_incidents(
    status: str | None = None,
    type: str | None = None,
    camera_id: int | None = None,
    open_only: bool = False,
    since_hours: float | None = None,
    limit: int = 200,
    db: AsyncSession = Depends(get_db),
    _=Depends(any_principal),
):
    stmt = select(Incident, Camera).outerjoin(Camera, Camera.id == Incident.camera_id)
    if open_only:
        stmt = stmt.where(Incident.status.in_(OPEN_STATUSES))
    if status:
        stmt = stmt.where(Incident.status.in_(status.split(",")))
    if type:
        stmt = stmt.where(Incident.type.in_(type.split(",")))
    if camera_id:
        stmt = stmt.where(Incident.camera_id == camera_id)
    if since_hours:
        stmt = stmt.where(Incident.detected_at >= _now() - timedelta(hours=since_hours))
    stmt = stmt.order_by(desc(Incident.detected_at)).limit(min(limit, 1000))
    rows = (await db.execute(stmt)).all()
    return [incident_dict(i, c) for i, c in rows]


@router.get("/{incident_id}")
async def get_incident(incident_id: int, db: AsyncSession = Depends(get_db), _=Depends(any_principal)):
    return await _full(db, await _get(db, incident_id))


@router.get("/{incident_id}/nearby-units")
async def nearby_units(
    incident_id: int,
    agency: str | None = None,
    limit: int = 10,
    include_busy: bool = False,
    db: AsyncSession = Depends(get_db),
    _=Depends(staff),
):
    await _get(db, incident_id)
    agencies = agency.split(",") if agency else None
    rows = await nearest_units(db, incident_id, agencies, limit=limit, only_available=not include_busy)
    return [
        {**unit_dict(u), "distance_m": d, "eta_minutes": estimate_eta(d, u.agency) if d is not None else None}
        for u, d in rows
    ]


# ------------------------------------------------------------- detector
@router.post("", status_code=201)
async def create_incident(
    camera_id: Annotated[int, Form()],
    type: Annotated[str, Form()],
    confidence: Annotated[float, Form()],
    details: Annotated[str, Form()] = "{}",
    lat: Annotated[float | None, Form()] = None,
    lon: Annotated[float | None, Form()] = None,
    snapshot: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_detector),
):
    """Called by the AI detection service when it detects an emergency."""
    if type not in AGENCIES_FOR:
        raise HTTPException(422, f"Unknown incident type '{type}'")
    cam = await db.get(Camera, camera_id)
    if not cam:
        raise HTTPException(404, "Camera not found")
    try:
        detail_data = json.loads(details) if details else {}
    except json.JSONDecodeError:
        detail_data = {}
    now = _now()

    # Merge repeated detections of the same emergency into one open incident
    existing = (await db.execute(
        select(Incident)
        .where(
            Incident.camera_id == camera_id,
            Incident.type == type,
            Incident.status.in_(OPEN_STATUSES),
            Incident.last_detected_at >= now - timedelta(seconds=settings.dedup_window_seconds),
        )
        .order_by(desc(Incident.id))
        .limit(1)
    )).scalar_one_or_none()
    if existing:
        existing.detection_count += 1
        existing.last_detected_at = now
        existing.confidence = max(existing.confidence, confidence)
        await db.commit()
        data = await _summary(db, existing)
        await manager.broadcast("incident_updated", data)
        return {**data, "merged": True}

    if lat is not None and lon is not None:
        location = make_point(lat, lon)
        detail_data["geo_source"] = "calibrated"
    else:
        cam_loc = point_latlon(cam.location)
        location = make_point(cam_loc["lat"], cam_loc["lon"]) if cam_loc else None
        detail_data["geo_source"] = "camera"

    inc = Incident(
        type=type,
        severity=SEVERITY_FOR.get(type, "high"),
        confidence=confidence,
        camera_id=cam.id,
        location=location,
        details=detail_data,
        detected_at=now,
        last_detected_at=now,
    )
    db.add(inc)
    await db.flush()

    if snapshot is not None:
        rel = f"incidents/{inc.id}/snapshot.jpg"
        _save_media(rel, await snapshot.read())
        inc.snapshot_path = rel

    log_event(db, inc.id, "detected", "AI detector",
              f"{LABELS[type]} detected on '{cam.name}' (confidence {confidence:.0%})")
    await db.commit()

    data = await _full(db, inc)
    await manager.broadcast("incident_created", data)
    return data


@router.post("/{incident_id}/clip")
async def upload_clip(
    incident_id: int,
    clip: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_detector),
):
    inc = await _get(db, incident_id)
    ext = os.path.splitext(clip.filename or "")[1].lower() or ".mp4"
    rel = f"incidents/{inc.id}/clip_{int(_now().timestamp())}{ext}"
    _save_media(rel, await clip.read())
    inc.clip_path = rel
    log_event(db, inc.id, "evidence", "AI detector", "Video evidence clip attached")
    await db.commit()
    data = await _summary(db, inc)
    await manager.broadcast("incident_updated", data)
    return data


# ------------------------------------------------------------- operator
@router.post("/{incident_id}/verify")
async def verify(incident_id: int, body: NoteIn, db: AsyncSession = Depends(get_db), user: User = Depends(staff)):
    inc = await _get(db, incident_id)
    if inc.status != "pending":
        raise HTTPException(409, f"Incident is already {inc.status}")
    inc.status = "verified"
    inc.verified_by = user.id
    inc.verified_at = _now()
    if body.notes:
        inc.notes = (inc.notes + "\n" + body.notes).strip()
    log_event(db, inc.id, "verified", _actor(user), body.notes or "Confirmed as a real emergency from video evidence")
    await db.commit()
    data = await _full(db, inc)
    await manager.broadcast("incident_updated", data)
    return data


@router.post("/{incident_id}/false-alarm")
async def false_alarm(incident_id: int, body: NoteIn, db: AsyncSession = Depends(get_db), user: User = Depends(staff)):
    inc = await _get(db, incident_id)
    if inc.status not in ("pending", "verified"):
        raise HTTPException(409, f"Cannot mark a {inc.status} incident as false alarm")
    inc.status = "false_alarm"
    inc.verified_by = user.id
    inc.verified_at = inc.verified_at or _now()
    inc.resolved_at = _now()
    if body.notes:
        inc.notes = (inc.notes + "\n" + body.notes).strip()
    log_event(db, inc.id, "false_alarm", _actor(user), body.notes or "Dismissed as false alarm")
    await db.commit()
    data = await _full(db, inc)
    await manager.broadcast("incident_updated", data)
    return data


@router.post("/{incident_id}/dispatch")
async def dispatch(incident_id: int, body: DispatchIn, db: AsyncSession = Depends(get_db), user: User = Depends(staff)):
    inc = await _get(db, incident_id)
    if inc.status not in OPEN_STATUSES:
        raise HTTPException(409, f"Cannot dispatch to a {inc.status} incident")
    now = _now()
    if inc.status == "pending":
        # Dispatching implies the operator has reviewed the evidence
        inc.verified_by = user.id
        inc.verified_at = now
        log_event(db, inc.id, "verified", _actor(user), "Verified during dispatch")

    already = set((await db.execute(
        select(Dispatch.unit_id).where(Dispatch.incident_id == inc.id, Dispatch.status.in_(ACTIVE_DISPATCH))
    )).scalars())

    created: list[tuple[Dispatch, ResponseUnit]] = []
    for unit_id in dict.fromkeys(body.unit_ids):
        unit = await db.get(ResponseUnit, unit_id)
        if not unit:
            raise HTTPException(404, f"Unit {unit_id} not found")
        if unit.status == "offline":
            raise HTTPException(409, f"Unit '{unit.name}' is offline")
        if unit_id in already:
            continue
        dist = await unit_distance(db, inc.id, unit_id)
        eta = estimate_eta(dist, unit.agency) if dist is not None else None
        d = Dispatch(
            incident_id=inc.id, unit_id=unit_id, distance_m=dist, eta_minutes=eta,
            notes=body.notes, dispatched_by=user.id,
        )
        db.add(d)
        unit.status = "dispatched"
        dist_txt = f" - {dist / 1000:.1f} km, ETA ~{eta:.0f} min" if dist is not None else ""
        log_event(db, inc.id, "dispatched", _actor(user), f"{unit.name} ({unit.agency}) dispatched{dist_txt}")
        created.append((d, unit))

    if not created:
        raise HTTPException(409, "Selected units are already assigned to this incident")

    inc.status = "dispatched"
    inc.dispatched_at = inc.dispatched_at or now
    await db.commit()

    data = await _full(db, inc)
    await manager.broadcast("incident_updated", data)
    for d, unit in created:
        await manager.broadcast("unit_updated", unit_dict(unit))
        await manager.broadcast("dispatch_created", {**dispatch_dict(d, unit), "incident": data})
    return data


@router.post("/{incident_id}/resolve")
async def resolve(incident_id: int, body: NoteIn, db: AsyncSession = Depends(get_db), user: User = Depends(staff)):
    inc = await _get(db, incident_id)
    if inc.status not in OPEN_STATUSES:
        raise HTTPException(409, f"Incident is already {inc.status}")
    inc.status = "resolved"
    inc.resolved_at = _now()
    if body.notes:
        inc.notes = (inc.notes + "\n" + body.notes).strip()

    rows = (await db.execute(
        select(Dispatch, ResponseUnit)
        .join(ResponseUnit, ResponseUnit.id == Dispatch.unit_id)
        .where(Dispatch.incident_id == inc.id, Dispatch.status.in_(ACTIVE_DISPATCH))
    )).all()
    for d, unit in rows:
        d.status = "completed"
        unit.status = "available"
    log_event(db, inc.id, "resolved", _actor(user), body.notes or "Incident resolved")
    await db.commit()

    data = await _full(db, inc)
    await manager.broadcast("incident_updated", data)
    for d, unit in rows:
        await manager.broadcast("unit_updated", unit_dict(unit))
        await manager.broadcast("dispatch_updated", dispatch_dict(d, unit))
    return data


@router.post("/{incident_id}/notes")
async def add_note(incident_id: int, body: NoteIn, db: AsyncSession = Depends(get_db), user: User = Depends(staff)):
    inc = await _get(db, incident_id)
    if not body.notes.strip():
        raise HTTPException(422, "Note is empty")
    inc.notes = (inc.notes + "\n" + body.notes).strip()
    log_event(db, inc.id, "note", _actor(user), body.notes)
    await db.commit()
    data = await _full(db, inc)
    await manager.broadcast("incident_updated", data)
    return data

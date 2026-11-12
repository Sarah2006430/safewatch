from .geo import point_latlon, polygon_coords
from .models import Camera, Dispatch, Incident, IncidentEvent, ResponseUnit, User, Zone


def iso(dt):
    return dt.isoformat() if dt else None


def media_url(path: str | None) -> str | None:
    return f"/media/{path}" if path else None


def zone_dict(z: Zone) -> dict:
    return {
        "id": z.id,
        "camera_id": z.camera_id,
        "name": z.name,
        "kind": z.kind,
        "roi": z.roi,
        "area": polygon_coords(z.area),
        "dwell_seconds": z.dwell_seconds,
    }


def camera_dict(c: Camera, zones: list[Zone] | None = None) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "stream_url": c.stream_url,
        "location": point_latlon(c.location),
        "address": c.address,
        "heading": c.heading,
        "detections": c.detections or [],
        "calibration": c.calibration,
        "is_active": c.is_active,
        "status": c.status,
        "status_message": c.status_message,
        "last_seen": iso(c.last_seen),
        "zones": [zone_dict(z) for z in (zones or [])],
    }


def unit_dict(u: ResponseUnit) -> dict:
    return {
        "id": u.id,
        "name": u.name,
        "agency": u.agency,
        "location": point_latlon(u.location),
        "status": u.status,
        "contact": u.contact,
        "updated_at": iso(u.updated_at),
    }


def incident_dict(i: Incident, camera: Camera | None = None) -> dict:
    return {
        "id": i.id,
        "type": i.type,
        "severity": i.severity,
        "confidence": round(i.confidence or 0, 3),
        "status": i.status,
        "camera_id": i.camera_id,
        "camera_name": camera.name if camera else None,
        "camera_address": camera.address if camera else None,
        "location": point_latlon(i.location),
        "snapshot_url": media_url(i.snapshot_path),
        "clip_url": media_url(i.clip_path),
        "details": i.details or {},
        "detection_count": i.detection_count,
        "detected_at": iso(i.detected_at),
        "last_detected_at": iso(i.last_detected_at),
        "verified_by": i.verified_by,
        "verified_at": iso(i.verified_at),
        "dispatched_at": iso(i.dispatched_at),
        "resolved_at": iso(i.resolved_at),
        "notes": i.notes,
    }


def dispatch_dict(d: Dispatch, unit: ResponseUnit | None = None) -> dict:
    return {
        "id": d.id,
        "incident_id": d.incident_id,
        "unit_id": d.unit_id,
        "unit": unit_dict(unit) if unit else None,
        "status": d.status,
        "distance_m": d.distance_m,
        "eta_minutes": d.eta_minutes,
        "notes": d.notes,
        "created_at": iso(d.created_at),
        "updated_at": iso(d.updated_at),
    }


def event_dict(e: IncidentEvent) -> dict:
    return {
        "id": e.id,
        "incident_id": e.incident_id,
        "action": e.action,
        "actor": e.actor,
        "message": e.message,
        "created_at": iso(e.created_at),
    }


def user_dict(u: User) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "email": u.email,
        "full_name": u.full_name,
        "role": u.role,
        "unit_id": u.unit_id,
    }


def session_dict(e) -> dict:
    return {"id": e.id, "user_id": e.user_id, "username": e.username, "kind": e.kind,
            "ip": e.ip, "user_agent": e.user_agent, "created_at": e.created_at.isoformat()}

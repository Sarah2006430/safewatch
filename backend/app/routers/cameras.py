import asyncio
import os
import re
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..geo import make_point, make_polygon
from ..models import Camera, Zone
from ..realtime import manager
from ..schemas import CameraIn, CameraUpdate, HeartbeatIn, ZoneIn
from ..security import any_principal, require_detector, staff
from ..serializers import camera_dict, zone_dict

router = APIRouter(prefix="/api", tags=["cameras"])


async def _zones_for(db: AsyncSession, camera_ids: list[int]) -> dict[int, list[Zone]]:
    by_cam: dict[int, list[Zone]] = defaultdict(list)
    if camera_ids:
        zones = (await db.execute(select(Zone).where(Zone.camera_id.in_(camera_ids)).order_by(Zone.id))).scalars()
        for z in zones:
            by_cam[z.camera_id].append(z)
    return by_cam


async def _camera_full(db: AsyncSession, cam: Camera) -> dict:
    zones = await _zones_for(db, [cam.id])
    return camera_dict(cam, zones[cam.id])


async def _get_camera(db: AsyncSession, camera_id: int) -> Camera:
    cam = await db.get(Camera, camera_id)
    if not cam:
        raise HTTPException(404, "Camera not found")
    return cam


@router.get("/cameras")
async def list_cameras(active_only: bool = False, db: AsyncSession = Depends(get_db), _=Depends(any_principal)):
    stmt = select(Camera).order_by(Camera.id)
    if active_only:
        stmt = stmt.where(Camera.is_active.is_(True))
    cams = (await db.execute(stmt)).scalars().all()
    zones = await _zones_for(db, [c.id for c in cams])
    return [camera_dict(c, zones[c.id]) for c in cams]


@router.get("/cameras/{camera_id}")
async def get_camera(camera_id: int, db: AsyncSession = Depends(get_db), _=Depends(any_principal)):
    return await _camera_full(db, await _get_camera(db, camera_id))


@router.post("/cameras", status_code=201)
async def create_camera(body: CameraIn, db: AsyncSession = Depends(get_db), _=Depends(staff)):
    cam = Camera(
        name=body.name,
        stream_url=body.stream_url,
        location=make_point(body.lat, body.lon),
        address=body.address,
        heading=body.heading,
        detections=list(body.detections),
        calibration=body.calibration.model_dump() if body.calibration else None,
        is_active=body.is_active,
    )
    db.add(cam)
    await db.commit()
    await db.refresh(cam)
    data = await _camera_full(db, cam)
    await manager.broadcast("camera_updated", data)
    return data


VIDEO_EXT = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".mpg", ".mpeg", ".m4v"}
ALL_DETECTIONS = ["fall", "smoke", "fire", "intrusion", "water_distress"]


@router.post("/cameras/import", status_code=201)
async def import_recording(
    file: UploadFile = File(...),
    name: str = Form(...),
    lat: float = Form(settings.default_lat),
    lon: float = Form(settings.default_lon),
    address: str = Form(""),
    detections: str = Form(",".join(ALL_DETECTIONS)),
    db: AsyncSession = Depends(get_db),
    _=Depends(staff),
):
    """Upload recorded CCTV footage; it becomes a camera that the detector analyses live (looping)."""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in VIDEO_EXT:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Use one of: {', '.join(sorted(VIDEO_EXT))}")
    dets = [d for d in (x.strip() for x in detections.split(",")) if d in ALL_DETECTIONS] or ALL_DETECTIONS
    folder = os.path.abspath(os.path.join(settings.media_dir, "recordings"))
    os.makedirs(folder, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", os.path.splitext(file.filename)[0])[:60]
    path = os.path.join(folder, f"{uuid.uuid4().hex[:8]}_{safe}{ext}")
    size = 0
    with open(path, "wb") as out:
        while chunk := await file.read(1 << 20):
            size += len(chunk)
            if size > 1024 * 1024 * 1024:
                out.close()
                os.remove(path)
                raise HTTPException(413, "File larger than 1 GB")
            out.write(chunk)
    cam = Camera(name=name.strip()[:128] or safe, stream_url=path, location=make_point(lat, lon),
                 address=address or f"Imported recording: {file.filename}", detections=dets, is_active=True)
    db.add(cam)
    await db.commit()
    await db.refresh(cam)
    data = await _camera_full(db, cam)
    await manager.broadcast("camera_updated", data)
    return data


@router.patch("/cameras/{camera_id}")
async def update_camera(camera_id: int, body: CameraUpdate, db: AsyncSession = Depends(get_db), _=Depends(staff)):
    cam = await _get_camera(db, camera_id)
    fields = body.model_dump(exclude_unset=True)
    for key in ("name", "stream_url", "address", "heading", "is_active"):
        if key in fields:
            setattr(cam, key, fields[key])
    if body.detections is not None:
        cam.detections = list(body.detections)
    if body.calibration is not None:
        cam.calibration = body.calibration.model_dump()
    if body.clear_calibration:
        cam.calibration = None
    if body.lat is not None and body.lon is not None:
        cam.location = make_point(body.lat, body.lon)
    await db.commit()
    await db.refresh(cam)
    data = await _camera_full(db, cam)
    await manager.broadcast("camera_updated", data)
    return data


@router.delete("/cameras/{camera_id}", status_code=204)
async def delete_camera(camera_id: int, db: AsyncSession = Depends(get_db), _=Depends(staff)):
    cam = await _get_camera(db, camera_id)
    path = cam.stream_url
    await db.delete(cam)
    await db.commit()
    await manager.broadcast("camera_deleted", {"id": camera_id})
    recordings = os.path.abspath(os.path.join(settings.media_dir, "recordings"))
    if os.path.abspath(path).startswith(recordings + os.sep):
        asyncio.create_task(_remove_later(path))  # imported recording: delete its file too
    return Response(status_code=204)


async def _remove_later(path: str) -> None:
    # The detector may still hold the file open (Windows) until its next camera refresh.
    for _ in range(12):
        try:
            os.remove(path)
            return
        except FileNotFoundError:
            return
        except OSError:
            await asyncio.sleep(5)


@router.post("/cameras/{camera_id}/heartbeat")
async def heartbeat(camera_id: int, body: HeartbeatIn, db: AsyncSession = Depends(get_db), _=Depends(require_detector)):
    cam = await _get_camera(db, camera_id)
    cam.status = body.status
    cam.status_message = body.message[:256]
    if body.status == "online":
        cam.last_seen = datetime.now(timezone.utc)
    await db.commit()
    # Broadcast every heartbeat (about every 30 s per camera) so "Last frame" stays current on screen.
    await manager.broadcast("camera_updated", await _camera_full(db, cam))
    return {"ok": True}


# ---------------------------------------------------------------- zones
@router.post("/cameras/{camera_id}/zones", status_code=201)
async def create_zone(camera_id: int, body: ZoneIn, db: AsyncSession = Depends(get_db), _=Depends(staff)):
    cam = await _get_camera(db, camera_id)
    zone = Zone(
        camera_id=cam.id,
        name=body.name,
        kind=body.kind,
        roi=[list(p) for p in body.roi],
        area=make_polygon(body.area),
        dwell_seconds=body.dwell_seconds,
    )
    db.add(zone)
    await db.commit()
    await db.refresh(zone)
    await manager.broadcast("camera_updated", await _camera_full(db, cam))
    return zone_dict(zone)


@router.put("/zones/{zone_id}")
async def update_zone(zone_id: int, body: ZoneIn, db: AsyncSession = Depends(get_db), _=Depends(staff)):
    zone = await db.get(Zone, zone_id)
    if not zone:
        raise HTTPException(404, "Zone not found")
    zone.name = body.name
    zone.kind = body.kind
    zone.roi = [list(p) for p in body.roi]
    zone.area = make_polygon(body.area)
    zone.dwell_seconds = body.dwell_seconds
    await db.commit()
    await db.refresh(zone)
    cam = await _get_camera(db, zone.camera_id)
    await manager.broadcast("camera_updated", await _camera_full(db, cam))
    return zone_dict(zone)


@router.delete("/zones/{zone_id}", status_code=204)
async def delete_zone(zone_id: int, db: AsyncSession = Depends(get_db), _=Depends(staff)):
    zone = await db.get(Zone, zone_id)
    if not zone:
        raise HTTPException(404, "Zone not found")
    camera_id = zone.camera_id
    await db.delete(zone)
    await db.commit()
    cam = await _get_camera(db, camera_id)
    await manager.broadcast("camera_updated", await _camera_full(db, cam))
    return Response(status_code=204)

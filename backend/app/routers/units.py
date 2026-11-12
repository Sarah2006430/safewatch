from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..geo import make_point
from ..models import Camera, Dispatch, Incident, ResponseUnit, User
from ..realtime import manager
from ..schemas import DispatchStatusIn, UnitIn, UnitUpdate
from ..security import current_user, staff
from ..serializers import dispatch_dict, incident_dict, unit_dict
from ..services.dispatch import log_event

router = APIRouter(prefix="/api", tags=["response units"])

# Unit status that follows from a dispatch status update
UNIT_STATUS_FOR = {
    "acknowledged": "dispatched",
    "en_route": "en_route",
    "on_scene": "on_scene",
    "completed": "available",
    "cancelled": "available",
}


def _can_edit_unit(user: User, unit_id: int) -> bool:
    return user.role in ("admin", "operator") or (user.role == "responder" and user.unit_id == unit_id)


@router.get("/units")
async def list_units(agency: str | None = None, db: AsyncSession = Depends(get_db), _: User = Depends(current_user)):
    stmt = select(ResponseUnit).order_by(ResponseUnit.agency, ResponseUnit.name)
    if agency:
        stmt = stmt.where(ResponseUnit.agency.in_(agency.split(",")))
    return [unit_dict(u) for u in (await db.execute(stmt)).scalars()]


@router.post("/units", status_code=201)
async def create_unit(body: UnitIn, db: AsyncSession = Depends(get_db), _: User = Depends(staff)):
    unit = ResponseUnit(
        name=body.name, agency=body.agency, location=make_point(body.lat, body.lon),
        status=body.status, contact=body.contact,
    )
    db.add(unit)
    await db.commit()
    await db.refresh(unit)
    data = unit_dict(unit)
    await manager.broadcast("unit_updated", data)
    return data


@router.patch("/units/{unit_id}")
async def update_unit(unit_id: int, body: UnitUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(current_user)):
    if not _can_edit_unit(user, unit_id):
        raise HTTPException(403, "You can only update your own unit")
    unit = await db.get(ResponseUnit, unit_id)
    if not unit:
        raise HTTPException(404, "Unit not found")
    fields = body.model_dump(exclude_unset=True)
    for key in ("name", "agency", "status", "contact"):
        if fields.get(key) is not None:
            setattr(unit, key, fields[key])
    if body.lat is not None and body.lon is not None:
        unit.location = make_point(body.lat, body.lon)
    await db.commit()
    await db.refresh(unit)
    data = unit_dict(unit)
    await manager.broadcast("unit_updated", data)
    return data


@router.delete("/units/{unit_id}", status_code=204)
async def delete_unit(unit_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(staff)):
    unit = await db.get(ResponseUnit, unit_id)
    if not unit:
        raise HTTPException(404, "Unit not found")
    await db.delete(unit)
    await db.commit()
    await manager.broadcast("unit_deleted", {"id": unit_id})
    return Response(status_code=204)


# ------------------------------------------------------------ dispatches
@router.get("/dispatches/mine")
async def my_dispatches(db: AsyncSession = Depends(get_db), user: User = Depends(current_user)):
    """Dispatches assigned to the logged-in responder's unit."""
    if not user.unit_id:
        return {"unit": None, "dispatches": []}
    unit = await db.get(ResponseUnit, user.unit_id)
    rows = (await db.execute(
        select(Dispatch, Incident, Camera)
        .join(Incident, Incident.id == Dispatch.incident_id)
        .outerjoin(Camera, Camera.id == Incident.camera_id)
        .where(Dispatch.unit_id == user.unit_id)
        .order_by(Dispatch.id.desc())
        .limit(50)
    )).all()
    return {
        "unit": unit_dict(unit) if unit else None,
        "dispatches": [{**dispatch_dict(d, unit), "incident": incident_dict(i, c)} for d, i, c in rows],
    }


@router.post("/dispatches/{dispatch_id}/status")
async def update_dispatch_status(
    dispatch_id: int, body: DispatchStatusIn, db: AsyncSession = Depends(get_db), user: User = Depends(current_user)
):
    d = await db.get(Dispatch, dispatch_id)
    if not d:
        raise HTTPException(404, "Dispatch not found")
    if not _can_edit_unit(user, d.unit_id):
        raise HTTPException(403, "Not your dispatch")
    unit = await db.get(ResponseUnit, d.unit_id)
    d.status = body.status
    if body.notes:
        d.notes = (d.notes + "\n" + body.notes).strip()
    unit.status = UNIT_STATUS_FOR.get(body.status, unit.status)
    msg = f"{unit.name}: {body.status.replace('_', ' ')}" + (f" - {body.notes}" if body.notes else "")
    log_event(db, d.incident_id, f"unit_{body.status}", user.full_name or user.username, msg)
    await db.commit()

    inc = await db.get(Incident, d.incident_id)
    cam = await db.get(Camera, inc.camera_id) if inc.camera_id else None
    payload = {**dispatch_dict(d, unit), "incident": incident_dict(inc, cam)}
    await manager.broadcast("dispatch_updated", payload)
    await manager.broadcast("unit_updated", unit_dict(unit))
    await manager.broadcast("incident_updated", incident_dict(inc, cam))
    return payload

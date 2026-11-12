"""Response coordination logic: which agencies handle what, and who is nearest."""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Incident, IncidentEvent, ResponseUnit

# Which agencies should respond to each emergency type (first = primary)
AGENCIES_FOR = {
    "fall": ["medical"],
    "fire": ["fire", "medical", "police"],
    "smoke": ["fire"],
    "intrusion": ["police"],
    "water_distress": ["rescue", "medical"],
}

SEVERITY_FOR = {
    "fall": "high",
    "fire": "critical",
    "smoke": "high",
    "intrusion": "medium",
    "water_distress": "critical",
}

# Average urban response speed (km/h) used for ETA estimates
AVG_SPEED_KMH = {"police": 40, "medical": 35, "fire": 30, "rescue": 30}
ROAD_FACTOR = 1.35  # straight-line -> road distance approximation


def estimate_eta(distance_m: float, agency: str) -> float:
    speed = AVG_SPEED_KMH.get(agency, 30)
    return round((distance_m * ROAD_FACTOR / 1000) / speed * 60, 1)


async def nearest_units(
    db: AsyncSession,
    incident_id: int,
    agencies: list[str] | None = None,
    limit: int = 5,
    only_available: bool = True,
) -> list[tuple[ResponseUnit, float]]:
    """Nearest response units to the incident, using PostGIS ST_Distance (metres)."""
    incident_loc = select(Incident.location).where(Incident.id == incident_id).scalar_subquery()
    dist = func.ST_Distance(ResponseUnit.location, incident_loc)
    stmt = select(ResponseUnit, dist.label("distance_m")).where(ResponseUnit.location.isnot(None))
    if agencies:
        stmt = stmt.where(ResponseUnit.agency.in_(agencies))
    if only_available:
        stmt = stmt.where(ResponseUnit.status == "available")
    stmt = stmt.order_by(dist).limit(limit)
    rows = (await db.execute(stmt)).all()
    return [(u, float(d) if d is not None else None) for u, d in rows]


async def unit_distance(db: AsyncSession, incident_id: int, unit_id: int) -> float | None:
    incident_loc = select(Incident.location).where(Incident.id == incident_id).scalar_subquery()
    stmt = select(func.ST_Distance(ResponseUnit.location, incident_loc)).where(ResponseUnit.id == unit_id)
    d = (await db.execute(stmt)).scalar()
    return float(d) if d is not None else None


async def suggestions(db: AsyncSession, incident: Incident) -> list[dict]:
    """Recommended units per agency for the dispatch panel."""
    from ..serializers import unit_dict

    out = []
    for agency in AGENCIES_FOR.get(incident.type, ["police"]):
        units = await nearest_units(db, incident.id, [agency], limit=3)
        out.append(
            {
                "agency": agency,
                "units": [
                    {**unit_dict(u), "distance_m": d, "eta_minutes": estimate_eta(d, u.agency) if d else None}
                    for u, d in units
                ],
            }
        )
    return out


def log_event(db: AsyncSession, incident_id: int, action: str, actor: str = "system", message: str = "") -> IncidentEvent:
    ev = IncidentEvent(incident_id=incident_id, action=action, actor=actor, message=message)
    db.add(ev)
    return ev

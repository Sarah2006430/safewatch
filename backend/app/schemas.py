from typing import Literal

from pydantic import BaseModel, Field

IncidentType = Literal["fall", "smoke", "fire", "intrusion", "water_distress"]
Agency = Literal["police", "medical", "fire", "rescue"]
UnitStatus = Literal["available", "dispatched", "en_route", "on_scene", "offline"]
DispatchStatus = Literal["assigned", "acknowledged", "en_route", "on_scene", "completed", "cancelled"]
Role = Literal["admin", "operator", "responder"]

Lat = Field(ge=-90, le=90)
Lon = Field(ge=-180, le=180)


class LoginIn(BaseModel):
    username: str  # username or e-mail
    password: str


class SignupIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=128)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=255)
    password: str = Field(min_length=8, max_length=128)


class UserIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6)
    full_name: str = ""
    role: Role = "operator"
    unit_id: int | None = None


class Calibration(BaseModel):
    image: list[tuple[float, float]] = Field(min_length=4, max_length=4)
    geo: list[tuple[float, float]] = Field(min_length=4, max_length=4)


class CameraIn(BaseModel):
    name: str
    stream_url: str
    lat: float = Lat
    lon: float = Lon
    address: str = ""
    heading: float | None = None
    detections: list[IncidentType] = ["fall", "smoke", "fire", "intrusion", "water_distress"]
    calibration: Calibration | None = None
    is_active: bool = True


class CameraUpdate(BaseModel):
    name: str | None = None
    stream_url: str | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    address: str | None = None
    heading: float | None = None
    detections: list[IncidentType] | None = None
    calibration: Calibration | None = None
    clear_calibration: bool = False
    is_active: bool | None = None


class HeartbeatIn(BaseModel):
    status: Literal["online", "offline", "error"]
    message: str = ""


class ZoneIn(BaseModel):
    name: str
    kind: Literal["restricted", "water"]
    roi: list[tuple[float, float]] = Field(min_length=3)
    area: list[tuple[float, float]] | None = None  # [[lat, lon], ...]
    dwell_seconds: float = Field(default=2.0, ge=0, le=600)


class UnitIn(BaseModel):
    name: str
    agency: Agency
    lat: float = Lat
    lon: float = Lon
    status: UnitStatus = "available"
    contact: str = ""


class UnitUpdate(BaseModel):
    name: str | None = None
    agency: Agency | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    status: UnitStatus | None = None
    contact: str | None = None


class NoteIn(BaseModel):
    notes: str = ""


class DispatchIn(BaseModel):
    unit_ids: list[int] = Field(min_length=1)
    notes: str = ""


class DispatchStatusIn(BaseModel):
    status: DispatchStatus
    notes: str = ""

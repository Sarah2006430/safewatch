"""HTTP client for the FastAPI backend."""
import json
import logging
import time

import requests

log = logging.getLogger("api")


class BackendClient:
    def __init__(self, base_url: str, api_key: str):
        self.base = base_url
        self.session = requests.Session()
        self.session.headers["X-API-Key"] = api_key

    def _request(self, method: str, path: str, retries: int = 3, **kw):
        kw.setdefault("timeout", 15)
        last = None
        for attempt in range(retries):
            try:
                r = self.session.request(method, self.base + path, **kw)
                r.raise_for_status()
                return r.json() if r.content else None
            except requests.RequestException as e:
                last = e
                if getattr(e, "response", None) is not None and 400 <= e.response.status_code < 500:
                    break  # client errors will not succeed on retry
                time.sleep(1.5 * (attempt + 1))
        raise last

    def get_cameras(self) -> list[dict]:
        return self._request("GET", "/api/cameras", params={"active_only": "true"}, retries=1)

    def heartbeat(self, camera_id: int, status: str, message: str = "") -> None:
        try:
            self._request("POST", f"/api/cameras/{camera_id}/heartbeat",
                          json={"status": status, "message": message[:250]}, retries=1, timeout=5)
        except requests.RequestException as e:
            log.debug("heartbeat failed: %s", e)

    def create_incident(self, camera_id: int, type_: str, confidence: float, details: dict,
                        latlon: tuple | None, snapshot_jpeg: bytes | None) -> dict:
        data = {
            "camera_id": str(camera_id),
            "type": type_,
            "confidence": f"{confidence:.4f}",
            "details": json.dumps(details),
        }
        if latlon:
            data["lat"], data["lon"] = f"{latlon[0]:.7f}", f"{latlon[1]:.7f}"
        files = {"snapshot": ("snapshot.jpg", snapshot_jpeg, "image/jpeg")} if snapshot_jpeg else None
        return self._request("POST", "/api/incidents", data=data, files=files)

    def upload_clip(self, incident_id: int, path: str) -> dict:
        with open(path, "rb") as f:
            return self._request("POST", f"/api/incidents/{incident_id}/clip",
                                 files={"clip": ("clip.mp4", f.read(), "video/mp4")}, timeout=60)

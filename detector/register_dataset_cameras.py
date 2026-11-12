"""Register the dataset feeds (../demo-recordings/feeds/*.mp4) as cameras in the backend, with zones.

Safe to run repeatedly: cameras are matched by name and updated in place.

    python register_dataset_cameras.py --user admin --password admin123
"""
import argparse
import os

import requests

from config import settings

HERE = os.path.dirname(os.path.abspath(__file__))
LAT, LON = 12.9716, 77.5946  # matches the backend's DEFAULT_LAT / DEFAULT_LON

FEEDS = [
    {
        "file": "falls_ur_room.mp4",
        "name": "Care Home · Ward 3",
        "address": "Elder care residence, Jayanagar",
        "offset": (-0.0262, -0.0105),
        "detections": ["fall"],
        "zones": [],
    },
    {
        "file": "restricted_ur_room.mp4",
        "name": "Data Centre · Server Hall Door",
        "address": "Data centre, Whitefield Road",
        "offset": (0.0062, 0.0291),
        "detections": ["intrusion", "fall"],
        "zones": [{"name": "Server hall doorway", "kind": "restricted", "dwell_seconds": 2.0,
                   "roi": [[0.45, 0.5], [0.9, 0.5], [0.9, 1.0], [0.45, 1.0]]}],
    },
    {
        "file": "fire_firesense.mp4",
        "name": "Industrial Yard · North",
        "address": "Peenya industrial area, Gate 4",
        "offset": (0.0301, -0.0182),
        "detections": ["fire", "smoke"],
        "zones": [],
    },
    {
        "file": "smoke_firesense.mp4",
        "name": "Hillside Watchtower",
        "address": "Turahalli forest edge",
        "offset": (-0.0118, -0.0314),
        "detections": ["smoke", "fire"],
        "zones": [],
    },
    {
        "file": "water_swimmers.mp4",
        "name": "Lakeside Promenade",
        "address": "Sankey Tank promenade",
        "offset": (0.0225, -0.0042),
        "detections": ["water_distress"],
        "zones": [{"name": "Open water", "kind": "water", "dwell_seconds": 3.0,
                   "roi": [[0.1, 0.05], [0.9, 0.05], [0.9, 0.9], [0.1, 0.9]]}],
    },
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default=settings.backend_url)
    ap.add_argument("--user", default="admin")
    ap.add_argument("--password", default="admin123")
    a = ap.parse_args()

    s = requests.Session()
    r = s.post(f"{a.backend}/api/auth/login", json={"username": a.user, "password": a.password}, timeout=10)
    r.raise_for_status()
    s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    existing = {c["name"]: c for c in s.get(f"{a.backend}/api/cameras", timeout=10).json()}

    for feed in FEEDS:
        path = os.path.abspath(os.path.join(HERE, "..", "demo-recordings", "feeds", feed["file"]))
        if not os.path.exists(path):
            print(f"skip  {feed['name']}: {feed['file']} not built (run prepare_demo_videos.py)")
            continue
        body = {
            "name": feed["name"], "stream_url": path, "address": feed["address"],
            "lat": LAT + feed["offset"][0], "lon": LON + feed["offset"][1],
            "detections": feed["detections"], "is_active": True,
        }
        cam = existing.get(feed["name"])
        if cam:
            cam = s.patch(f"{a.backend}/api/cameras/{cam['id']}", json=body, timeout=10).json()
            for z in cam.get("zones", []):
                s.delete(f"{a.backend}/api/zones/{z['id']}", timeout=10)
            action = "update"
        else:
            r = s.post(f"{a.backend}/api/cameras", json=body, timeout=10)
            r.raise_for_status()
            cam = r.json()
            action = "add  "
        for z in feed["zones"]:
            s.post(f"{a.backend}/api/cameras/{cam['id']}/zones", json=z, timeout=10).raise_for_status()
        print(f"{action} CAM{cam['id']:02d} {feed['name']}  <- {feed['file']}")

    # Live webcam: add a water zone on the left so distress can be shown live
    # (sit close so only head + shoulders are visible, then raise and wave both arms).
    for cam in existing.values():
        if cam["stream_url"].strip() == "0" and not any(z["kind"] == "water" for z in cam.get("zones", [])):
            s.post(f"{a.backend}/api/cameras/{cam['id']}/zones", json={
                "name": "Pool edge (live demo)", "kind": "water", "dwell_seconds": 1.0,
                "roi": [[0.0, 0.0], [0.6, 0.0], [0.6, 1.0], [0.0, 1.0]]}, timeout=10).raise_for_status()
            print(f"zone  CAM{cam['id']:02d} {cam['name']}: added live water zone")


if __name__ == "__main__":
    main()

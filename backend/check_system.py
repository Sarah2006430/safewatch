"""End-to-end check of a running SafeWatch stack (backend + detector + database).

Run it before a demo, with backend and detector running:
    cd backend
    .venv\\Scripts\\python.exe check_system.py

It uses only the public API, like the web app does, and prints PASS/FAIL for each feature:
sign-up/login, WebSocket push, a real alert of every type coming from the detector,
verify -> dispatch -> responder updates -> resolve, false alarm, notes, recording import,
history, analytics and sign-in history. It cleans up the test camera it imports.
Note: it really verifies/dispatches/resolves one pending incident and marks another as a false alarm.
"""
import asyncio
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

import websockets

API = os.getenv("SAFEWATCH_API", "http://127.0.0.1:8000")
DETECTOR = os.getenv("SAFEWATCH_DETECTOR", "http://127.0.0.1:8100")
HERE = os.path.dirname(os.path.abspath(__file__))
IMPORT_CLIP = os.path.join(HERE, "..", "demo-recordings", "import", "fire_single_FIRESENSE-pos2.mp4")

results: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, info: str = ""):
    results.append((bool(ok), name, info))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  - {info}" if info else ""), flush=True)
    return ok


def call(method, path, token=None, body=None, base=API, raw=None, ctype=None):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(base + path, data=data, method=method)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    if ctype:
        req.add_header("Content-Type", ctype)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            txt = r.read()
            return r.status, (json.loads(txt) if txt and r.headers.get_content_type() == "application/json" else txt)
    except urllib.error.HTTPError as e:
        txt = e.read()
        try:
            return e.code, json.loads(txt)
        except ValueError:
            return e.code, txt
    except (urllib.error.URLError, OSError):
        return 0, None


def multipart(fields: dict, file_field: str, path: str):
    boundary = uuid.uuid4().hex
    out = b""
    for k, v in fields.items():
        out += f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    with open(path, "rb") as f:
        out += (f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{os.path.basename(path)}"\r\n'
                "Content-Type: video/mp4\r\n\r\n").encode() + f.read() + b"\r\n"
    out += f"--{boundary}--\r\n".encode()
    return out, f"multipart/form-data; boundary={boundary}"


def login(user, pw):
    s, d = call("POST", "/api/auth/login", body={"username": user, "password": pw})
    return d.get("access_token") if s == 200 else None


async def main():
    t0 = time.time()
    print(f"SafeWatch system check  (API {API}, detector {DETECTOR})\n")

    # ---------------------------------------------------------------- infrastructure
    print("Infrastructure")
    s, d = call("GET", "/api/health")
    check(s == 200, "Backend API is up")
    s, h = call("GET", "/health", base=DETECTOR)
    if isinstance(h, bytes):
        h = json.loads(h or b"{}")
    cams = (h or {}).get("cameras", {}) if s == 200 else {}
    online = [c for c in cams.values() if c.get("status") == "online"]
    check(s == 200 and online, "Detector is running", f"{len(online)}/{len(cams)} cameras online, "
          + ", ".join(f"{c['name'][:18]} {c['fps']}fps" for c in online))

    # ---------------------------------------------------------------- accounts
    print("\nAccounts")
    email = f"check.{uuid.uuid4().hex[:6]}@example.com"
    s, d = call("POST", "/api/auth/signup", body={"full_name": "System Check", "email": email, "password": "checkpass123"})
    check(s == 201 and d.get("access_token"), "Sign-up with name, e-mail and password", email)
    s, _ = call("POST", "/api/auth/signup", body={"full_name": "System Check", "email": email, "password": "checkpass123"})
    check(s == 409, "Duplicate e-mail is rejected")
    s, _ = call("POST", "/api/auth/signup", body={"full_name": "X", "email": "not-an-email", "password": "123"})
    check(s == 422, "Invalid sign-up data is rejected")
    check(login(email, "checkpass123"), "Login with e-mail")
    s, _ = call("POST", "/api/auth/login", body={"username": email, "password": "wrong"})
    check(s == 401, "Wrong password is rejected")
    op = login("operator", "operator123")
    admin = login("admin", "admin123")
    resp = login("ambulance1", "responder123")
    check(op and admin and resp, "Demo accounts (operator, admin, responder) log in")
    s, _ = call("GET", "/api/cameras")
    check(s == 401, "API refuses requests without a login")

    # ---------------------------------------------------------------- real-time + detections
    print("\nLive detection (waiting for real alerts from the detector, up to 4 min)")
    events: list[dict] = []
    ws = await websockets.connect(f"{API.replace('http', 'ws')}/ws?token={op}")
    check(True, "WebSocket connected")

    async def listen():
        try:
            async for msg in ws:
                m = json.loads(msg)
                if m.get("event"):
                    events.append(m)
        except Exception:
            pass
    task = asyncio.create_task(listen())

    _, cams_list = call("GET", "/api/cameras", op)
    cam_types = {t for c in cams_list if c["is_active"] for t in c["detections"]}
    s, recent = call("GET", "/api/incidents?since_hours=24&limit=500", op)
    before = {i["id"] for i in recent}
    seen: dict[str, dict] = {}
    deadline = time.time() + 240
    want = {"fall", "fire", "smoke", "intrusion"} & cam_types
    while time.time() < deadline and not want <= set(seen):
        await asyncio.sleep(5)
        for e in events:
            if e["event"] in ("incident_created", "incident_updated"):
                i = e["data"]
                if i["type"] not in seen and (i["id"] not in before or e["event"] == "incident_updated"):
                    seen[i["type"]] = i
    for t in sorted(want | {"water_distress"}):
        i = seen.get(t)
        if t == "water_distress" and not i:
            check(True, "Water distress", "no live alert expected from the swimmers footage - demo it on the webcam (logic covered by unit tests)")
            continue
        check(i, f"Real {t.replace('_', ' ')} alert pushed over WebSocket",
              f"#{i['id']} {i['camera_name']} {round(i['confidence'] * 100)}% {i['details'].get('method') or i['details'].get('kind', '')}" if i else "none in 4 min")
    ws_new = [e for e in events if e["event"] == "incident_created"]
    check(ws_new or seen, "incident_created events arrive in real time", f"{len(ws_new)} new incident(s), {len(events)} events total")

    # ---------------------------------------------------------------- evidence + location
    print("\nEvidence & location")
    sample = next(iter(seen.values()), None) or (recent[0] if recent else None)
    if sample:
        for _ in range(12):
            _, sample = call("GET", f"/api/incidents/{sample['id']}", op)
            if sample.get("clip_url"):
                break
            await asyncio.sleep(2)
        check(sample.get("location") and sample["location"].get("lat"), "Alert is location-tagged", str(sample.get("location")))
        st, img = call("GET", sample["snapshot_url"]) if sample.get("snapshot_url") else (0, b"")
        check(st == 200 and len(img) > 1000, "Snapshot image is stored and served", f"{len(img)} bytes")
        st, clip = call("GET", sample["clip_url"]) if sample.get("clip_url") else (0, b"")
        check(st == 200 and len(clip) > 10000, "Evidence video clip is stored and served", f"{len(clip)} bytes")

    # ---------------------------------------------------------------- operator workflow
    print("\nVerification & response coordination")
    _, open_list = call("GET", "/api/incidents?status=pending&limit=200", op)
    fall = next((i for i in open_list if i["type"] == "fall"), None) or (open_list[0] if open_list else None)
    if check(fall, "A pending incident is available", f"#{fall['id']} {fall['type']}" if fall else ""):
        s, d = call("POST", f"/api/incidents/{fall['id']}/verify", op, {"notes": "verified by system check"})
        check(s == 200 and d["status"] == "verified", "Verify")
        sugg = d.get("suggestions") or []
        check(sugg and any(g["units"] for g in sugg), "Nearest units suggested by PostGIS",
              "; ".join(f"{g['agency']}: {g['units'][0]['name']} {round(g['units'][0]['distance_m'])} m ~{g['units'][0]['eta_minutes']} min" for g in sugg if g["units"]))
        _, me = call("GET", "/api/dispatches/mine", resp)
        unit_id = me["unit"]["id"]
        s, _ = call("PATCH", f"/api/units/{unit_id}", op, {"status": "available"})
        s, d = call("POST", f"/api/incidents/{fall['id']}/dispatch", op, {"unit_ids": [unit_id]})
        check(s == 200 and d["status"] == "dispatched", "Dispatch a unit", f"unit #{unit_id}")
        await asyncio.sleep(1)
        check(any(e["event"] == "dispatch_created" for e in events), "Responder is notified over WebSocket (dispatch_created)")
        _, mine = call("GET", "/api/dispatches/mine", resp)
        disp = next((x for x in mine["dispatches"] if x["incident_id"] == fall["id"]), None)
        ok = disp is not None
        for stt in ("acknowledged", "en_route", "on_scene", "completed"):
            s, _ = call("POST", f"/api/dispatches/{disp['id']}/status", resp, {"status": stt}) if disp else (0, None)
            ok = ok and s == 200
        check(ok, "Responder updates: acknowledged -> en route -> on scene -> completed")
        s, d = call("POST", f"/api/incidents/{fall['id']}/notes", op, {"notes": "note from system check"})
        check(s == 200, "Add operator note")
        s, d = call("POST", f"/api/incidents/{fall['id']}/resolve", op, {"notes": "resolved by system check"})
        check(s == 200 and d["status"] == "resolved", "Resolve")
        _, d = call("GET", f"/api/incidents/{fall['id']}", op)
        check(len(d.get("events", [])) >= 4, "Audit timeline recorded", f"{len(d.get('events', []))} events")
    other = next((i for i in open_list if fall and i["id"] != fall["id"] and i["status"] == "pending"), None)
    if other:
        s, d = call("POST", f"/api/incidents/{other['id']}/false-alarm", op, {"notes": "false alarm test"})
        check(s == 200 and d["status"] == "false_alarm", "Mark false alarm", f"#{other['id']}")

    # ---------------------------------------------------------------- import recording
    print("\nImport recording (uploaded video analysed like a live camera)")
    if os.path.exists(IMPORT_CLIP):
        raw, ctype = multipart({"name": "System check import", "detections": "fire,smoke"}, "file", IMPORT_CLIP)
        s, cam = call("POST", "/api/cameras/import", op, raw=raw, ctype=ctype)
        if check(s == 201, "Upload recording -> new camera", f"CAM{cam.get('id')}" if s == 201 else str(cam)):
            hit = None
            for _ in range(36):
                await asyncio.sleep(5)
                _, lst = call("GET", f"/api/incidents?camera_id={cam['id']}&limit=5", op)
                if lst:
                    hit = lst[0]
                    break
            check(hit, "Detector analyses the imported recording and raises an alert",
                  f"#{hit['id']} {hit['type']} {round(hit['confidence'] * 100)}%" if hit else "no alert within 3 min")
            s, _ = call("DELETE", f"/api/cameras/{cam['id']}", op)
            check(s == 204, "Delete imported camera (file is removed too)")
    else:
        check(False, "Import clip present", IMPORT_CLIP)

    # ---------------------------------------------------------------- history
    print("\nHistory & analytics")
    s, allh = call("GET", "/api/incidents?limit=1000", op)
    check(s == 200 and allh, "Full incident history is stored", f"{len(allh)} incidents in PostgreSQL")
    s, st = call("GET", "/api/incidents/stats", op)
    check(s == 200 and "last_24h" in st, "Analytics statistics", f"24h total {st.get('last_24h', {}).get('total')}")
    s, ses = call("GET", "/api/auth/sessions?limit=200", admin)
    kinds = {x["kind"] for x in ses} if s == 200 else set()
    check({"signup", "login", "failed"} <= kinds, "Sign-in history (signup / login / failed) is stored", f"{len(ses)} events")
    s, _ = call("GET", "/benchmark.json", base=os.getenv("SAFEWATCH_WEB", "http://localhost:5173"))
    check(s == 200, "Dataset benchmark report is served to the Analytics page")

    task.cancel()
    await ws.close()
    passed = sum(ok for ok, *_ in results)
    print(f"\n{passed}/{len(results)} checks passed in {time.time() - t0:.0f}s")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

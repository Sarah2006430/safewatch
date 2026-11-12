"""Close every open incident (pending / verified / dispatched) so a demo starts with an empty queue.

Nothing is deleted: incidents are marked resolved with a note, so they stay in the
history (Analytics -> All time), together with their evidence clips and audit log.
Dispatched units are released back to 'available'.

    cd backend
    .venv\\Scripts\\python.exe close_open_incidents.py            # asks for confirmation
    .venv\\Scripts\\python.exe close_open_incidents.py --yes
"""
import json
import sys
import urllib.request

API = "http://127.0.0.1:8000"


def call(method, path, token=None, body=None):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body is not None else None, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"null")


def main():
    token = call("POST", "/api/auth/login", body={"username": "admin", "password": "admin123"})["access_token"]
    open_inc = call("GET", "/api/incidents?open_only=true&limit=1000", token)
    print(f"{len(open_inc)} open incident(s).")
    if not open_inc:
        return
    if "--yes" not in sys.argv and input("Mark them all resolved (kept in history)? [y/N] ").strip().lower() != "y":
        print("Cancelled.")
        return
    for i in open_inc:
        call("POST", f"/api/incidents/{i['id']}/resolve", token, {"notes": "Closed before demo session"})
    for u in call("GET", "/api/units", token):
        if u["status"] != "available":
            call("PATCH", f"/api/units/{u['id']}", token, {"status": "available"})
    print(f"Closed {len(open_inc)} incident(s); all units are available again.")


if __name__ == "__main__":
    main()

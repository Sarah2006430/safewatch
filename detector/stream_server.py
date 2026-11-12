"""Tiny MJPEG server so the dashboard can show live annotated camera feeds.

GET /stream/<camera_id>    multipart MJPEG of annotated frames (with boxes & zones)
GET /snapshot/<camera_id>  latest raw frame (used by the zone editor); ?annotated=1 for the overlay frame
GET /health                JSON status of all camera workers
"""
import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

log = logging.getLogger("stream")


class StreamHub:
    def __init__(self):
        self._cond = threading.Condition()
        self.frames: dict[int, dict] = {}
        self.status: dict[int, dict] = {}

    def publish(self, camera_id: int, annotated: bytes, raw: bytes | None = None):
        with self._cond:
            entry = self.frames.setdefault(camera_id, {"seq": 0, "annotated": b"", "raw": b""})
            entry["annotated"] = annotated
            if raw:
                entry["raw"] = raw
            entry["seq"] += 1
            self._cond.notify_all()

    def set_status(self, camera_id: int, **info):
        self.status[camera_id] = {**self.status.get(camera_id, {}), **info}

    def remove(self, camera_id: int):
        with self._cond:
            self.frames.pop(camera_id, None)
            self.status.pop(camera_id, None)

    def wait(self, camera_id: int, last_seq: int, timeout: float = 5.0):
        with self._cond:
            self._cond.wait_for(lambda: self.frames.get(camera_id, {}).get("seq", 0) != last_seq, timeout=timeout)
            e = self.frames.get(camera_id)
            return (e["annotated"], e["seq"]) if e else (None, last_seq)


def make_handler(hub: StreamHub):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _headers(self, code=200, ctype="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.end_headers()

        def do_GET(self):
            parts = self.path.split("?")[0].strip("/").split("/")
            annotated = "annotated=1" in self.path
            try:
                if parts[0] == "health":
                    self._headers()
                    self.wfile.write(json.dumps({"cameras": hub.status}).encode())
                elif parts[0] == "snapshot" and len(parts) == 2:
                    e = hub.frames.get(int(parts[1]))
                    if not e or not (e["raw"] or e["annotated"]):
                        self._headers(404)
                        self.wfile.write(b'{"detail":"no frame yet"}')
                        return
                    self._headers(ctype="image/jpeg")
                    self.wfile.write((e["annotated"] or e["raw"]) if annotated else (e["raw"] or e["annotated"]))
                elif parts[0] == "stream" and len(parts) == 2:
                    self._stream(int(parts[1]))
                else:
                    self._headers(404)
                    self.wfile.write(b'{"detail":"not found"}')
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
            except ValueError:
                self._headers(400)

        def _stream(self, camera_id: int):
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            seq = -1
            last_send = 0.0
            while True:
                frame, seq = hub.wait(camera_id, seq, timeout=5)
                if not frame:
                    continue
                now = time.time()
                if now - last_send < 0.066:  # cap ~15 fps per viewer
                    time.sleep(0.066 - (now - last_send))
                last_send = time.time()
                self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                                 + str(len(frame)).encode() + b"\r\n\r\n" + frame + b"\r\n")

    return Handler


def start_stream_server(hub: StreamHub, port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("0.0.0.0", port), make_handler(hub))
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True, name="mjpeg-server").start()
    log.info("MJPEG stream server on http://0.0.0.0:%d/stream/<camera_id>", port)
    return server

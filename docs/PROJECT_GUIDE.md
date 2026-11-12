# SafeWatch: the complete project guide

*Emergency Detection, Public Safety & Response Coordination*

This guide covers what SafeWatch does, how each part works, why it was built that way, and how to present it. Read sections 1–4 first. The rest is reference for when the interviewer goes deeper.

---

## 1. The project in one paragraph

SafeWatch is a smart-CCTV control-room system. A **detector** service written in Python reads video from CCTV or IP cameras (RTSP), a webcam or recorded footage. It runs **YOLO** deep-learning models on every frame to spot five kinds of emergency: **visible falls, smoke, fire, intrusion into restricted areas, and signs of distress in water**. When it finds one, it sends a **location-tagged alert** with a **snapshot and a video evidence clip** to a **FastAPI** backend. The backend stores the alert in **PostgreSQL + PostGIS** and pushes it instantly over **WebSockets** to a **React** dashboard. There, a human **operator verifies** the evidence and, with one click, **dispatches the nearest police, medical, fire or rescue units**. PostGIS calculates the distances. Responders receive the assignment on their own screen, update their status, and share their GPS position, which appears live on the **Leaflet / OpenStreetMap** map.

---

## 2. How every requirement is met

| Requirement in the brief | Where it is in SafeWatch |
|---|---|
| Detect **visible falls** | `detector/analyzers/fall.py`: pose keypoints + tracking. Raises an alert when a person goes from upright to lying and stays down, or drops fast and disappears. |
| Detect **smoke** | `detector/analyzers/fire_smoke.py` using **our own YOLO model trained on fire/smoke images** (`detector/models/fire_smoke_yolo11n.pt`) |
| Detect **fire** | Same model. A colour/motion heuristic is the fallback if no model is configured. |
| Detect **restricted-area intrusion** | `detector/analyzers/intrusion.py`: a person's feet stay inside a polygon zone (drawn in the UI) longer than the zone's "dwell" time |
| Detect **signs of distress near water** | `detector/analyzers/water.py`: inside a water zone it looks at raised/waving arms, body submerged (head visible, hips not), bobbing in place, and a person disappearing in the water |
| **Location-tagged alerts** | Every incident is stored as a PostGIS `GEOGRAPHY(POINT)`. It uses either the camera's position or, with ground calibration, the exact GPS point where the event happened in the frame (homography). |
| **Video evidence** | The detector keeps a rolling 5-second pre-event buffer and records 6 s after the event. It uploads an H.264 MP4 plus an annotated snapshot. |
| **Operator verification** | Dashboard: Verify / False alarm / Resolve / Notes, with a full audit timeline of who did what and when |
| **Coordinated response by police, medical and rescue** | Agency mapping per emergency type, nearest available units by PostGIS distance, ETA estimate, one-click dispatch, responder app with Acknowledge → En route → On scene → Completed, live GPS sharing |

### Tech stack and where each piece is used
| Required technology | Used for |
|---|---|
| **React.js** | The entire dashboard (`frontend/src`): pages, components, real-time state |
| **Tailwind CSS** | All styling (v4, with a custom light/dark design-token theme in `index.css`) |
| **Python** | Detector service and backend |
| **OpenCV** | Reading RTSP/files/webcam, resizing, drawing overlays, JPEG/MP4 encoding, colour heuristics, background subtraction |
| **YOLO** (Ultralytics YOLO11) | `yolo11n-pose` (person + 17 body keypoints + tracking) and our custom-trained `fire_smoke_yolo11n` |
| **FastAPI** | REST API, file uploads, JWT login, WebSocket hub |
| **PostgreSQL** | All data: users, cameras, zones, incidents, dispatches, audit log, sign-in history |
| **PostGIS** | Geographic columns, GiST spatial indexes, `ST_Distance` nearest-unit search |
| **Leaflet + OpenStreetMap** | Live incident map, unit/camera markers, zone footprints, dispatch lines, location pickers |
| **WebSockets** | Instant push of new alerts, incident/unit/camera/dispatch updates to every open browser |
| **CCTV / IP cameras, RTSP** | Camera `stream_url` can be `rtsp://…` (forced over TCP, auto-reconnect), an HTTP/MJPEG URL, a webcam index or a video file |

---

## 3. Architecture

```
 ┌─────────────────────┐   RTSP / HTTP / file / webcam
 │ CCTV & IP cameras   │──────────────────────────────┐
 └─────────────────────┘                              ▼
                                   ┌───────────────────────────────────────────┐
                                   │ DETECTOR (Python · OpenCV · YOLO)          │
                                   │ one thread per camera:                     │
                                   │  read frame → YOLO pose + ByteTrack        │
                                   │  → fall / intrusion / water analyzers      │
                                   │  → fire/smoke YOLO model                   │
                                   │  → annotate → MJPEG live server :8100      │
                                   │  → alert + snapshot + evidence clip        │
                                   └───────────────┬───────────────────────────┘
                                                   │ HTTPS REST (X-API-Key)
                                                   ▼
 ┌──────────────────────────┐  SQL   ┌───────────────────────────────────────────┐
 │ PostgreSQL + PostGIS     │◀──────▶│ BACKEND (FastAPI · async SQLAlchemy)      │
 │ incidents, units, zones, │        │ auth (JWT), cameras, incidents, dispatch, │
 │ dispatches, audit, users │        │ PostGIS nearest units, media storage,     │
 └──────────────────────────┘        │ WebSocket hub  /ws                        │
                                     └───────────────┬───────────────────────────┘
                                   REST + WebSocket  │        MJPEG video (:8100)
                                                     ▼              │
                                   ┌─────────────────────────────────▼─────────┐
                                   │ FRONTEND (React · Tailwind · Leaflet/OSM)  │
                                   │ Control room: Command, Live Wall, Cameras, │
                                   │ Responders, Analytics · Responder app      │
                                   └────────────────────────────────────────────┘
```

**Why three separate services?**
- The **detector** is CPU/GPU-heavy and long-running. Keeping it separate means you can run several detectors on different machines, each with `CAMERA_IDS=…`, for many cameras. If it crashes, the website keeps working.
- The **backend** is the single source of truth: database, rules, permissions.
- The **frontend** is a static web app, served by Vite in development and nginx in Docker.

### The life of one alert (what happens in about 1 second)
1. The camera thread reads the newest frame. A `FrameReader` thread keeps only the latest frame, so RTSP never lags behind.
2. YOLO11-pose finds people and their 17 keypoints. ByteTrack gives each person an ID across frames.
3. The analyzers update their per-person history, e.g. "person #7 was upright 1.2 s ago and has now been lying for 1.0 s" → **fall**.
4. The detector **POSTs** `/api/incidents` with the type, confidence, details, location and annotated snapshot. It keeps adding frames for 6 more seconds.
5. The backend **merges duplicates**: same camera + same type + still open + within 120 s = the same incident, with `detection_count` going up. Otherwise it creates a new incident with a severity (fire/water = critical, fall/smoke = high, intrusion = medium), writes an audit event, and **broadcasts `incident_created` over WebSocket**.
6. Every open dashboard gets it instantly: toast pop-up, siren sound (Web Audio), browser notification, pulsing map marker.
7. About 6 s later the detector uploads the **evidence clip** (`/api/incidents/{id}/clip`) and the dashboard swaps the snapshot for the video.
8. The operator opens it, watches the evidence and clicks **Verify**. The backend asks PostGIS for the nearest *available* units of the right agencies, ranked by distance, with an ETA.
9. The operator clicks **Dispatch**. Dispatch rows are created, the units become "dispatched", and a `dispatch_created` event reaches the responder's phone.
10. The responder taps Acknowledge → En route → On scene → Completed. Each tap updates the control room live. The operator then **Resolves** the incident, and the times feed the Analytics page.

---

## 4. "Live data": what is live, what is recorded, and what the Live Wall is

This is the most likely interview question, so here is the precise answer.

**SafeWatch always analyses video live, frame by frame, as it plays.** It does not matter where the video comes from. The detector treats every camera the same way: it opens the `stream_url` with OpenCV and analyses frames continuously.

| Camera source | `stream_url` example | When you'd use it |
|---|---|---|
| Real CCTV / IP camera | `rtsp://user:pass@192.168.1.64:554/Streaming/Channels/101` | Production: any Hikvision/Dahua/CP Plus/ONVIF camera |
| Phone as an IP camera | `http://192.168.1.20:8080/video` (Android "IP Webcam" app) | Quick live test with a real moving camera |
| Laptop webcam | `0` | Live demo of intrusion / water distress |
| **Recorded footage** | a video file path | Events you can't stage safely (fire, falls, drowning) |

- **Live Wall** (`/live`) shows the **annotated live output of every active camera**, the exact frames the AI is looking at, with boxes, skeleton tags (DOWN, INTRUDER, WATER score), zones and alert banners. It is an MJPEG stream from the detector's built-in server (`detector/stream_server.py`, port 8100). Connect a real RTSP camera and it shows that camera live.
- **Import recording** (Cameras → *Import recording*) lets an operator upload recorded CCTV footage, e.g. a clip handed over after an incident. The backend stores it in `backend/media/recordings/` and registers it as a camera. Within about 15 s the detector picks it up and analyses it **live, in real time, looping**, raising real alerts with evidence clips exactly as for an RTSP camera. Deleting the camera deletes the file.
- **Why recordings for the demo?** You can't start a fire, fall over or drown during an interview. Instead SafeWatch runs on **real recorded footage from public research datasets** (section 8), the same approach researchers use to evaluate these systems. Nothing is simulated: every alert comes from the model looking at real video.

---

## 5. The detector (`detector/`)

The detector is a Python process. It starts with `python main.py`.

| File | What it does |
|---|---|
| `main.py` | Supervisor. Starts the MJPEG server, limits PyTorch threads per inference (`TORCH_THREADS`, so 6 camera threads don't fight over the CPU), pre-loads YOLO weights, then every 15 s fetches the camera list from the backend and starts/stops/updates one `CameraWorker` per active camera. Forces RTSP over TCP (`OPENCV_FFMPEG_CAPTURE_OPTIONS`) to avoid UDP packet loss. |
| `config.py` | Reads `detector/.env`: backend URL, API key, model paths, confidences, input sizes, FPS, clip lengths, cooldown, stream port. |
| `api_client.py` | Talks to the backend: get cameras, send heartbeats (online/offline), create incidents (multipart with snapshot), upload clips. Retries on failure. |
| `video.py` | `FrameReader` thread: opens RTSP/HTTP/file/webcam, auto-reconnects with back-off, loops files at their real frame rate, and always keeps only the newest frame. Also `write_clip` (H.264 via imageio-ffmpeg, falling back to OpenCV) and the "no signal" frame. |
| `camera_worker.py` | One thread per camera, the heart of the detector. Each frame: resize → **YOLO pose + ByteTrack** (only if this camera needs person detection) → analyzers → **fire/smoke model** (about 3×/s) → annotate → publish to the live stream → keep a 5-s pre-event buffer → on a detection (with a 60-s per-type cooldown) send the alert and start a 6-s post-event clip. |
| `geometry.py` | `Person` (box, confidence, track id, keypoints, helpers like `foot`, `center`), `torso_angle` (angle of the shoulder→hip line from vertical), zone polygons from normalised points, and `GeoMapper`, a homography from 4 image points to 4 GPS points for precise incident locations. |
| `analyzers/fall.py` | Fall logic (below) |
| `analyzers/intrusion.py` | Intrusion logic (below) |
| `analyzers/water.py` | Water-distress logic (below) |
| `analyzers/fire_smoke.py` | Fire/smoke with the YOLO model, or the OpenCV heuristic |
| `annotate.py` | Draws zones, person boxes with tags, detection banners and the header (camera name, FPS, time) |
| `stream_server.py` | Small threaded HTTP server: `/stream/<id>` (MJPEG live), `/snapshot/<id>` (latest frame; `?annotated=1` for the overlay), `/health` (status + FPS of every camera) |
| `evaluate_video.py` | Runs the *same* pipeline offline over a video and prints every alert with timestamps |
| `benchmark_datasets.py` | Clip-by-clip benchmark on the datasets: detection rate on event clips, false-alarm rate on control clips. Writes `benchmark.json`, which the Analytics page shows. |
| `prepare_demo_videos.py` | Builds the looping feeds in `demo-recordings/feeds/` from the raw dataset files |
| `register_dataset_cameras.py` | Registers those feeds as cameras with zones and map positions (safe to re-run) |
| `make_demo_folder.py` | Builds `demo-recordings/` (import clips, evidence copies, README) |
| `prepare_fire_training.py` / `train_fire_smoke.py` | Build a balanced training subset and fine-tune YOLO for fire/smoke |
| `simulate_incident.py` | Developer tool that posts a synthetic alert. Not used for the demo. |
| `tests/test_analyzers.py` | Unit tests for the fall, intrusion, water and homography logic on synthetic keypoints |

### 5.1 Person detection and tracking
`yolo11n-pose` returns, for each person, a box and **17 COCO keypoints** (nose, eyes, ears, shoulders, elbows, wrists, hips, knees, ankles), each with a confidence. **ByteTrack** links detections across frames into tracks with stable IDs, which is essential because every rule depends on "what did *this* person do over the last few seconds". Person confidence is set low (0.15) because people lying on the floor get low scores. The analyzers' temporal rules filter out the noise this lets in.

### 5.2 Fall detection (`fall.py`)
- **Posture per frame.** It's *lying* if the torso angle is ≥ 60° from vertical and the box is wide (aspect ≥ 0.8), or the box is very wide (aspect ≥ 1.4). It's *upright* if the torso is ≤ 35° and the box is tall.
- **Fall** = the person was *upright* within the last 2.5 s and has now been *lying* for ≥ 1 s. Confidence also uses the **descent score**, how far the body centre dropped relative to the person's height.
- **Track re-association.** When someone falls, the detector often loses them and ByteTrack starts a new ID. A new track that appears where a lost one was a moment ago inherits its history. Without this, the "upright before" evidence would be lost exactly at the moment of the fall.
- **Fall then lost.** If a person dropped by more than a third of their height in 1.5 s and then disappeared (curled on the floor, out of frame), it's raised as a lower-confidence fall.
- **Person down.** Lying for 8 s or more without a seen fall (e.g. found collapsed) gives a lower-confidence alert.

### 5.3 Intrusion (`intrusion.py`)
Zones are polygons drawn on the camera image (Cameras → Zones), stored as normalised 0–1 coordinates. A person's **foot point** (bottom-centre of the box) inside a *restricted* zone for longer than the zone's dwell time (default 2 s) raises one alert per person per zone. The foot point is used, not the box, so someone walking *in front of* the zone doesn't trigger it.

### 5.4 Water distress (`water.py`)
For each tracked person inside a *water* zone, over a 4-s window it computes a score:
- **arms raised** above the shoulders (waving for help / the "instinctive drowning response"), weight 0.35;
- **submerged**: head keypoints visible but hips/knees not, weight 0.30;
- **bobbing**: vertical head movement relative to body size, weight 0.20;
- **stationary while submerged**: little horizontal progress, weight 0.15.

A score ≥ 0.55 held for 1.5 s gives **distress**. A confirmed track that **disappears for 3 s while in the water** (not at the frame edge) gives **possible submersion**. One-off, unconfirmed detections are ignored, so detection flicker can't raise false submersion alerts.

### 5.5 Fire and smoke (`fire_smoke.py`)
- **YOLO model.** This is our own `fire_smoke_yolo11n.pt`, classes `fire` and `smoke`, run at 320 px about 3 times per second. An alert needs the class in at least 60% (fire) or 70% (smoke) of recent checks, *and* a mean confidence ≥ 0.45 (fire) or ≥ 0.35 (smoke). That rejects flickering orange lights and sunsets.
- **Fallback heuristic** (no model configured). Flame-coloured pixels by HSV + RGB + YCrCb rules, which must also be moving (MOG2 background subtraction) and flickering. Smoke is greyish, low-saturation, moving regions that blur the background (Laplacian drop). Both need the same temporal persistence.

### 5.6 Evidence clips
`camera_worker.py` keeps a deque of the last ~5 s of annotated JPEG frames. When an alert fires it copies that buffer and keeps adding frames for 6 s. `video.write_clip` encodes an **H.264 MP4**, which plays in every browser, and uploads it. The evidence therefore shows what happened **before** the event, not just after.

### 5.7 Precise location (ground calibration)
A camera's position on the map is its own location. For better precision, enter 4 image points and their 4 GPS coordinates (*Ground calibration*). `GeoMapper` computes a **homography** (OpenCV `getPerspectiveTransform`), so the pixel where the person fell or the fire started becomes a real lat/lon on the map.

---

## 6. The backend (`backend/app/`)

Built with FastAPI and async SQLAlchemy 2 + asyncpg. GeoAlchemy2 handles the PostGIS types.

| File | What it does |
|---|---|
| `main.py` | Creates the app. On startup it runs `init_db` (creates the PostGIS extension, tables and lightweight migrations) and `seed`. It sets up CORS, mounts routers and `/media` (evidence files), and serves `/api/health` and the **`/ws` WebSocket** (JWT in the query string, ping/pong keep-alive). |
| `config.py` | Settings from `backend/.env`: `DATABASE_URL`, `JWT_SECRET`, `DETECTOR_API_KEY`, media folder, default map centre, merge window. |
| `database.py` | Engine, session factory, `init_db` (incl. `ALTER TABLE … ADD COLUMN IF NOT EXISTS` migrations) |
| `models.py` | The database tables (below) |
| `schemas.py` | Pydantic models that validate every request body (sign-up rules, camera fields, zones, dispatch…) |
| `serializers.py` | Converts DB rows to JSON (PostGIS points → `{lat, lon}`, media paths → URLs) |
| `geo.py` | Helpers to build and read PostGIS points/polygons (WKT, SRID 4326) |
| `security.py` | bcrypt password hashing, JWT create/verify, `current_user`, role guards (`staff` = admin/operator, `admin_only`), the detector's `X-API-Key` check |
| `realtime.py` | `ConnectionManager`: set of open WebSockets; `broadcast(event, data)` sends to all |
| `routers/auth.py` | **Sign-up** (name, e-mail, password → operator account), **login with e-mail or username**, logout, `/auth/me`, **sign-in history** (`/auth/sessions`), user admin |
| `routers/cameras.py` | Camera CRUD, **Import recording** upload, heartbeats from the detector, zones CRUD. Every change is broadcast so the detector and dashboards update. |
| `routers/incidents.py` | Create (from detector, with merging), clip upload, list/filter, details, **verify / false-alarm / dispatch / resolve / notes**, nearby units, **stats** for Analytics |
| `routers/units.py` | Response units CRUD; responders can edit only their own unit (status, GPS); `/dispatches/mine`; dispatch status updates (which also update the unit's status) |
| `services/dispatch.py` | Agency mapping, severity mapping, **PostGIS nearest units**, ETA, audit-event helper |
| `seed.py` | First-run demo data: admin, operator, two responder logins, 10 units around the city, demo cameras |

### 6.1 Database tables (PostgreSQL + PostGIS)
| Table | Key columns |
|---|---|
| `users` | username, **email**, full_name, password_hash (bcrypt), role (admin/operator/responder), unit_id |
| `session_events` | user, kind (**signup / login / logout / failed**), ip, browser, time. This is the sign-in history. |
| `cameras` | name, stream_url, **location GEOGRAPHY(POINT,4326)**, address, heading, detections[], calibration (JSON), status, last_seen |
| `zones` | camera_id, name, kind (restricted/water), roi (image polygon), **area GEOGRAPHY(POLYGON)**, dwell_seconds |
| `incidents` | type, severity, status, confidence, **location GEOGRAPHY(POINT)**, camera_id, details (JSONB: model output), snapshot/clip paths, detection_count, timestamps (detected, verified, dispatched, resolved), verified_by, notes |
| `response_units` | name, agency (police/medical/fire/rescue), status, **location GEOGRAPHY(POINT)**, contact |
| `dispatches` | incident ↔ unit, status (assigned → acknowledged → en_route → on_scene → completed), distance_m, eta_minutes, timestamps |
| `incident_events` | **audit trail**: incident, actor, kind, message, time |

**Why `GEOGRAPHY` instead of `GEOMETRY`?** Distances on a geography column come out in **metres on the real Earth**, with no projection maths. GiST indexes keep spatial queries fast as the tables grow.

**Nearest-unit query (conceptually):**
```sql
SELECT u.*, ST_Distance(u.location, i.location) AS meters
FROM response_units u, incidents i
WHERE i.id = :incident AND u.agency = ANY(:agencies) AND u.status = 'available'
ORDER BY meters LIMIT 5;
```
ETA = distance × 1.35 (road factor) ÷ the agency's average urban speed (police 40, medical 35, fire 30, rescue 30 km/h).

### 6.2 Main API endpoints
Full interactive docs are at http://127.0.0.1:8000/docs (Swagger UI, generated by FastAPI).

| Method & path | Who | Purpose |
|---|---|---|
| `POST /api/auth/signup` | public | Create an account (name, e-mail, password ≥ 8) |
| `POST /api/auth/login` | public | Log in with e-mail or username → JWT |
| `POST /api/auth/logout` · `GET /api/auth/sessions` | user | Record logout · sign-in history |
| `GET/POST/PATCH/DELETE /api/cameras…` | staff | Cameras |
| `POST /api/cameras/import` | staff | Upload a recording → new analysed camera |
| `POST /api/cameras/{id}/zones` · `PATCH/DELETE /api/zones/{id}` | staff | Zones |
| `POST /api/incidents` · `/{id}/clip` | detector (API key) | New alert · evidence clip |
| `GET /api/incidents` · `/{id}` · `/stats` | user | List (filters, date range) · details · analytics |
| `POST /api/incidents/{id}/verify · false-alarm · dispatch · resolve · notes` | staff | Operator workflow |
| `GET /api/incidents/{id}/nearby-units` | staff | PostGIS nearest units |
| `GET/POST/PATCH /api/units…` · `GET /api/dispatches/mine` · `POST /api/dispatches/{id}/status` | staff / responder | Response coordination |
| `WS /ws?token=…` | user | Real-time events |

**WebSocket events:** `incident_created`, `incident_updated`, `dispatch_created`, `dispatch_updated`, `unit_updated`, `unit_deleted`, `camera_updated`, `camera_deleted`.

---

## 7. The frontend (`frontend/src/`)

Built with React 18, react-router, Vite, Tailwind CSS 4, react-leaflet and lucide icons.

| File | What it does |
|---|---|
| `main.jsx` | Entry point. Loads fonts (bundled, works offline), Leaflet CSS and styles, applies the saved theme, renders `<App>`. |
| `App.jsx` | Routing by role: staff get the control room, responders get *My Unit*, guests get the login/sign-up page |
| `index.css` | **Design tokens**: the light (sky-blue, default) and dark themes as CSS variables, plus the map, HUD frames, hazard stripes and animations |
| `context/AuthContext.jsx` | Logged-in user, `login`, **`signup`**, `logout` (logged on the server), token in localStorage |
| `context/DataContext.jsx` | Loads cameras, units, incidents and stats once, then keeps them **live via the WebSocket** (auto-reconnect). Fires the toast, siren and browser notification on new alerts. |
| `lib/api.js` | `fetch` wrapper with the JWT, `upload()` with progress for recordings, detector stream/snapshot URLs |
| `lib/constants.jsx` | Incident types and agencies (labels, icons, colours, which agencies respond), status/severity styles |
| `lib/mapIcons.jsx` | Leaflet markers as SVG (diamond = incident, square = unit, circle = camera) |
| `lib/alarm.js` | Siren generated with the Web Audio API (no sound files) |
| `lib/theme.js`, `components/ThemeToggle.jsx` | Light/dark switch, remembered per browser |
| `pages/Login.jsx` | **Sign in** (e-mail or username + password) and **Create account** (full name, e-mail, password, confirm) with validation |
| `pages/Dashboard.jsx` | **Command** screen: stats strip, incident queue, live map, camera thumbnails, incident detail drawer |
| `components/StatsBar.jsx` | Awaiting verification, verified, dispatched, alerts in 24 h, mean time to verify, units ready per agency |
| `components/IncidentFeed.jsx` | The queue: tabs (Active/Review/All), type filters, snapshot thumbnails |
| `components/IncidentMap.jsx` | Leaflet map: incidents, units, cameras, zone footprints, dispatch lines; layer switcher; fly-to the selected incident |
| `components/IncidentDetail.jsx` | Evidence player (clip / snapshot / live), model output, verify/false-alarm/resolve/notes, **Coordinate response** (nearest units with distance and ETA), assigned units, audit log |
| `components/Toasts.jsx` | New-alert pop-ups with the snapshot |
| `pages/LiveWall.jsx`, `components/LiveStream.jsx` | Live annotated camera grid (MJPEG); `CameraThumb` polls snapshots for small previews |
| `pages/Cameras.jsx`, `components/ZoneEditor.jsx`, `components/ImportRecording.jsx`, `components/MapPicker.jsx` | Add/edit RTSP cameras, **import recordings**, draw zones on the camera image, pick locations on the map |
| `pages/Units.jsx` | Response units by agency, status, map |
| `pages/History.jsx`, `components/Benchmark.jsx`, `components/SessionHistory.jsx` | **Analytics**: dataset validation results, alerts by type/hour, response times, full incident history (24 h / 7 d / 30 d / all time, search, filters, **CSV export**), **sign-in history** |
| `pages/Responder.jsx` | Responder app: assignments with evidence and a map, status buttons, Navigate (OSM directions), live GPS sharing |

---

## 8. Data, models and measured accuracy

### Datasets used (all real footage)
| Dataset | What | Licence |
|---|---|---|
| **UR Fall Detection Dataset**, University of Rzeszów (Kwolek & Kepski 2014) | 30 recorded falls + 15 everyday-activity sequences | academic, cite the paper |
| **FIRESENSE** (CERTH / Bilkent University) | 11 fire + 16 hard non-fire videos, 13 smoke + 9 non-smoke videos | CC-BY 4.0 |
| **Fire & smoke images** (Hugging Face `jojomoi-meme/fog_fire_detection`, compiled from Roboflow Universe) | ~30,000 labelled images; we trained on a balanced subset of 3,000 | CC-BY 4.0 |
| **Wikimedia Commons** "Swimmers in Ohepalu bog pool" | aerial swimmers footage | CC0 |

There is **no freely downloadable drowning-video dataset**; the research one, SwimID, needs a signed agreement. That's why water distress is demonstrated live with the webcam.

### Training the fire/smoke model
- Started from YOLO11n pretrained on COCO (transfer learning).
- Fine-tuned on 3,000 images (balanced: fire-only, smoke-only, both, none), 320 px, 12 epochs, batch 16, **on a laptop CPU** (~75 min).
- Validation on **800 held-out images: mAP50 = 0.43** (fire 0.42, smoke 0.44), mAP50-95 = 0.21.
- *mAP50* = mean Average Precision where a predicted box counts as correct if it overlaps the true box by ≥ 50%.

### Clip-level benchmark (`python benchmark_datasets.py`, shown on the Analytics page)
| Detector | Event clips detected | Control clips with a false alarm |
|---|---|---|
| Fall (UR Fall: 30 falls / 15 daily-activity clips) | **23 / 30 (77 %)** | 2 / 15 (13 %) |
| Fire, trained YOLO11n (FIRESENSE: 11 fire / 16 hard negatives) | **9 / 11 (82 %)** | 3 / 16 (19 %) |
| Smoke, trained YOLO11n (FIRESENSE: 13 smoke / 9 negatives) | **9 / 13 (69 %)** | 0 / 9 (0 %) |
| *Baseline: OpenCV colour heuristic, fire* | *11 / 11* | *11 / 16 (69 %)* |
| *Baseline: OpenCV colour heuristic, smoke* | *5 / 13* | *0 / 9* |

Settings: YOLO11n-pose at 480 px, person confidence 0.15; fire/smoke model at 320 px; laptop CPU.

**How to explain these numbers:**
- *Recall* (detection rate) matters most in safety. Missing a fire is worse than a false alarm, and every alert is checked by a human before anyone is dispatched.
- The trained model cut the heuristic's fire false-alarm rate from **69% to about 20%**, and roughly doubled smoke detection.
- Most missed falls are people who end up curled at the bottom edge of the frame, where the small *nano* pose model loses them. A larger model (`yolo11s-pose`) or a GPU would help.
- The single false fall on the daily-activity clips is a person deliberately lying down fast, which is exactly what operator verification is for.

---

## 9. History and persistence

Everything is stored in PostgreSQL and survives restarts:
- **Incidents** with their model output, snapshots and evidence clips (files in `backend/media/incidents/<id>/`);
- the **audit trail** of every operator and responder action, and **dispatches** with their timestamps;
- **sign-in history**: every sign-up, login, logout and failed login, with IP and browser.

The Analytics page reads the full history from the database (24 h, 7 days, 30 days or **all time**) and exports it as CSV.

---

## 10. Security
- Passwords are hashed with **bcrypt**; sessions use **JWT** (signed with `JWT_SECRET`).
- Role-based access: operators/admins run the control room, responders see only their own unit and assignments, and only admins see everyone's sign-in history.
- The detector authenticates with a separate **API key**.
- Pydantic validates every input; uploads are checked by extension and size (≤ 1 GB).
- **Known gaps for production** (be honest if asked): `/media` evidence and the MJPEG streams have no auth (put them behind an authenticated reverse proxy), open sign-up should require admin approval, and secrets in `.env` must be changed.

---

## 11. Performance notes
- On a laptop CPU (i7-1165G7, no GPU) the detector processes about 4–7 frames per second per camera with 6 cameras at once. That's enough for these events, which last seconds; on a GPU it is 20–30+ fps. Other heavy programs (a build, a video call, antivirus scans) slow it down, so close them during a demo.
- Optimisations used:
  - only newest frames are processed;
  - pose runs only on cameras that need it;
  - fire/smoke runs at 320 px about 3×/s;
  - a small PyTorch thread pool per camera thread;
  - browser thumbnails poll snapshots instead of opening many video streams (browsers allow only ~6 connections per server).

---

## 12. Running it

**Double-click `start-safewatch.bat`** in the project folder (PostgreSQL runs as a Windows service). It opens three windows (backend, detector, frontend) and the browser at http://localhost:5173. Keep the three windows open; close them to stop. Running it again is safe: it only starts what isn't already running.

The same thing from a PowerShell window in the project folder:
```bash
powershell -ExecutionPolicy Bypass -File .\start-safewatch.ps1
```

| Account | Password | Role |
|---|---|---|
| `operator` | `operator123` | Control room |
| `admin` | `admin123` | Control room + all sign-in history |
| `ambulance1` / `police1` | `responder123` | Responder app |

You can also create a new account on the sign-in page (**Create an account**).

---

## 13. Demo script for the interview (about 10 minutes)

**Before the interview:**
0. *(Optional, the night before)* Start with an empty queue while keeping all history: `cd backend` then `.venv\Scripts\python.exe close_open_incidents.py`. To verify everything works: `.venv\Scripts\python.exe check_system.py` (about 5 minutes, prints PASS/FAIL per feature; it really handles one incident).
1. Start everything with `start-safewatch.ps1` 10 minutes early, so the YOLO models are loaded and alerts are already in the queue.
2. Use a full-size Chrome/Edge window and allow notifications and sound.
3. Open a second browser window (or a private window) logged in as `ambulance1`, for the responder part.
4. On the Cameras page, disable the cameras you won't show to free CPU (e.g. the webcam if you won't do the water demo).

**1. The problem and the sign-up (1 min).** Show the sign-in page. Click **Create an account**, register with your own name and e-mail, and you land in the console. "Every sign-in is logged; I'll show that at the end."

**2. Command screen (2 min).** Point at the stats strip, the incident queue, the map of the city with incidents (diamonds), units (squares) and cameras (circles), and the live camera thumbnails. "These cameras are analysing real recorded CCTV footage from research datasets right now. Nothing is simulated: the model is watching every frame." Wait for a new alert: siren, toast, pulsing marker.

**3. Live Wall (1 min).** Show the annotated live output: person boxes, the DOWN tag when someone falls, the restricted zone in front of the server-hall door, and FIRE/SMOKE banners. "This is what the AI sees. A real RTSP CCTV camera appears here the same way."

**4. Verify and coordinate (3 min).** Open a **Fall** alert from *Care Home*:
- play the **evidence clip**, which shows the 5 s before the fall;
- point at the location tag and the model output (torso angle, descent score);
- click **Verify**; the *Coordinate response* panel lists the nearest ambulances with distance and ETA, calculated by PostGIS;
- click **Nearest per agency**, then **Dispatch**.

Switch to the `ambulance1` window: the assignment appeared instantly. Tap **Acknowledge → En route → On scene**. Switch back: the control room updated live, with a dispatch line on the map. Click **Resolve**.

Repeat quickly for a **Fire** alert from *Industrial Yard*. It suggests fire brigade, ambulance *and* police.

**5. Import a recording live (2 min).** Cameras → **Import recording** → choose `demo-recordings/import/fire_single_FIRESENSE-pos2.mp4`, click a location on the map, then **Import & analyse**. Within about 15–30 s a new camera appears and a **fire** alert arrives from it. "An operator can upload footage handed over after an incident, and it's analysed exactly like a live camera."

**6. Live webcam (optional, 1 min).**
- *Intrusion:* walk into the right third of the webcam picture (the "Server Room Door" zone). An alert comes after 2 s.
- *Water distress:* sit close so only your head and shoulders are in the left part of the frame (the "Pool edge" zone), then raise and wave both arms.

**7. Analytics and history (1 min).** Show **Validated on public datasets** (detection and false-alarm rates, trained model vs heuristic), alerts by type, response times, the full incident history with *All time* and **CSV export**, and **Sign-in history**, which includes the account you made at the start.

**If something goes wrong:**
- No new alerts → the queue already holds real alerts from earlier, with evidence clips.
- Detector window crashed → re-run `python main.py` in `detector`.
- No video at all → open `demo-recordings/evidence/`, which holds clips SafeWatch itself recorded.

---

## 14. Likely interview questions (with short answers)

**Why YOLO?** It's a one-stage detector: one pass of the network finds all objects, so it's fast enough for real-time video. YOLO11 also has a *pose* variant that gives body keypoints, which falls and drowning need. We used the *nano* size to run on a CPU.

**How does fall detection work?** A pose model and tracking give each person's torso angle and box shape over time. A fall is upright → lying within 2.5 s, staying down ≥ 1 s, plus how fast the body dropped. We re-attach tracks lost during the fall, and handle people who drop and disappear from view.

**Why not just train one model for "fall"?** A single frame of someone lying down can't tell a fall from someone resting. The *transition over time* is what defines a fall, which is why we combine pose with temporal rules.

**How did you measure accuracy?** Clip-level testing on public datasets: the percentage of event clips detected and the percentage of non-event clips that raised a false alarm. The detector code is exactly the same as live.

**Why PostGIS?** To store locations as real geographic points and let the database answer "nearest available ambulance" with `ST_Distance` and a spatial index, instead of doing distance maths in Python.

**Why WebSockets instead of polling?** Alerts must appear within a second. A WebSocket keeps one connection open, and the server pushes events the moment they happen, with no wasted requests.

**How are duplicates avoided?** The detector has a 60-s cooldown per camera and type. The backend merges detections of the same type from the same camera into the open incident within 120 s (`detection_count` increases).

**How is the location tagged?** By the camera's position, or precisely by a homography from 4 calibrated image points to GPS. The incident is stored as a PostGIS point and shown on the map.

**What about privacy?** Only alerts store footage (an 11-s clip), not continuous recording. Access needs a login with roles, and all sign-ins are logged. Face blurring and retention policies would be next steps.

**How would you scale it?** Run more detector instances (`CAMERA_IDS` splits cameras between them), use GPUs, put the backend behind a load balancer (stateless JWT), and use Redis pub/sub for WebSocket fan-out across backend instances.

**What would you improve next?** A larger pose model on a GPU, a drowning model trained on SwimID (with permission), road-network ETAs (OSRM), SMS/push notifications to responders, and authenticated media.

---

## 15. Folder map
```
emergency detection/
├── backend/            FastAPI app (app/), media/ (evidence + imported recordings), .env
├── detector/           YOLO detector, analyzers/, models/fire_smoke_yolo11n.pt, datasets/raw (source videos)
├── frontend/           React + Tailwind app (src/), public/benchmark.json
├── demo-recordings/    feeds/ (looping cameras), import/ (clips to upload live), evidence/ (recorded alerts), README.txt
├── docs/PROJECT_GUIDE.md   this file
├── start-safewatch.bat     double-click to start everything (runs start-safewatch.ps1)
├── docker-compose.yml      optional: run everything in Docker
└── README.md               setup and commands
```


---

## 16. Website walkthrough: every screen and button

### Sign-in page (first screen)
| Item | What it does |
|---|---|
| **Moon/Sun icon** (top right) | Switches between the light (blue) and dark theme |
| **E-mail or username** + **Password** | Your login details |
| **Enter console** | Logs you in. Operators/admins go to the control room, responders to their unit screen. |
| **Create an account** | Switches to the sign-up form |
| *Sign-up:* **Full name, E-mail, Password, Confirm password** | It checks as you type: valid e-mail, password of 8+ characters, and matching passwords. Errors appear in orange. |
| **Create account** | Creates the account, logs you in and records a "signup" in the history |
| **Sign in** link | Goes back to the login form |

### Always visible: left sidebar
| Item | What it does |
|---|---|
| **SAFEWATCH** logo | Just the brand |
| **Command** (red number) | Main control screen. The number is how many alerts still need verifying. |
| **Live Wall** | All cameras' live AI view |
| **Cameras** | Add, edit, import and zone the cameras |
| **Responders** | Police, ambulance, fire and rescue units |
| **Analytics** | Accuracy results, statistics, full history, sign-in log |
| Your name + role | Who is logged in |
| **Sign out** | Logs out (recorded in the history) |

### Always visible: top bar
| Item | What it does |
|---|---|
| Page name | Which screen you're on |
| **Alerts open** | Number of unverified alerts |
| **Cams 6/6** | How many cameras are online. Green means all working. |
| **Units ready 10/10** | Response units free to send |
| **Moon/Sun** | Theme switch |
| **Alarm / Muted** (speaker) | Turns the siren sound on or off for new alerts |
| **Live link** (green dot) | The real-time connection (WebSocket) is working. Red/"Offline" means it's reconnecting. |
| Clock | Current time and date |

### Pop-up alert card (top right, appears by itself)
When the AI detects something, a card slides in with a siren. It shows the type, severity, camera, AI confidence and a snapshot.
- **Click the card** to open that incident.
- **X** closes the card.

### Command page (the main screen)
**Stats strip across the top:**
- **Awaiting verification**: new alerts that no one has checked (red stripe when above 0);
- **Verified**: confirmed but no unit sent yet;
- **Units dispatched**: incidents with help on the way;
- **Alerts · 24 h**: total alerts today, plus the false-alarm %;
- **Mean time to verify**: how fast operators confirm alerts;
- **Police / Medical / Fire Brigade / Rescue**: units ready per agency. The small bars show each unit: coloured = free, orange = busy.

**Left column: Incident queue**
| Item | What it does |
|---|---|
| **Active** tab | All open incidents |
| **Review** tab | Only unverified ones (the to-do list) |
| **All** tab | Everything, including closed ones |
| 5 icon buttons (person, flame, smoke, ban, waves) | Filter by type: fall, fire, smoke, intrusion, water. Click again to remove the filter. |
| Each incident row | Snapshot, number, severity, type, camera, status, AI %, time. "CLIP" means video evidence exists, and "×5" means it was detected 5 times. **Click a row** to open it. |

**Middle: Map**
| Item | What it does |
|---|---|
| **Diamonds** | Incidents. Pulsing = waiting for verification. |
| **Squares** | Response units (police blue, ambulance green, fire red, rescue amber) |
| **Circles** | Cameras (green = online) |
| Shaded areas | Zones on the map |
| Dotted lines | A dispatched unit going to an incident |
| **+ / −** | Zoom |
| **Layers icon** (top right) | Show or hide incidents, responders, cameras and zones |
| **Situation** box | How many active incidents |
| **Show closed** | Also show resolved or false-alarm incidents |
| **Camera thumbnails** (bottom) | Mini live views of each camera. A coloured tag means the camera has an alert. They scroll sideways when the incident panel is open. |
| Clicking a marker | Diamond: opens that incident. Square or circle: shows its details. |

**Right: Incident detail panel** (opens when you click an incident)
| Item | What it does |
|---|---|
| **X** | Closes the panel |
| Progress bar | Pending → Verified → Dispatched → Resolved |
| **Evidence clip** tab | Plays the AI-recorded video (5 s before + 6 s after) |
| **Snapshot** tab | The still picture at the moment of detection |
| **Live** tab | That camera's live AI view right now |
| Info boxes | Camera, AI confidence and number of hits, GPS position, last seen, address |
| **Open in OpenStreetMap** | Opens the exact location on openstreetmap.org |
| **Model output** | What the AI measured (e.g. torso angle, descent score, zone name, fire persistence) |
| **Notes box** | Type a comment for the record |
| **Verify** | Confirms it's a real emergency, which unlocks dispatch |
| **False alarm** | Rejects it (counts in the false-alarm rate) |
| **Resolve** | Closes the incident as handled and frees its units |
| **Add note** | Saves your note to the audit log without changing the status |
| **Coordinate response** | The nearest *free* units of the right agencies, with distance and ETA, calculated by PostGIS. A fall suggests medical; a fire suggests fire, medical and police. |
| **Nearest per agency** | Ticks the closest unit of each agency automatically |
| Checkboxes | Pick units by hand |
| **Dispatch N units** | Sends them. The responder gets the job instantly and a line appears on the map. |
| **Assigned units** | Who was sent and their live status (assigned, en route, on scene…) |
| **Audit log** | Every action, with the time and who did it, AI detector included |

### Live Wall
- A grid of every active camera, showing **exactly what the AI sees** live: person boxes, tags (**DOWN** = fallen, **INTRUDER**, **WATER** score), red/blue zones, and FIRE/SMOKE banners.
- A **red border with a stripe** means the camera has an unverified alert.
- The coloured tags under each camera show its open alerts, e.g. "INTRUSION ×5".
- The **⤢ button** opens that camera full size. **X** closes it.
- **"NO SIGNAL · detector off?"** means the detector window isn't running.

### Cameras
| Item | What it does |
|---|---|
| **Import recording** | Upload a video file (drag-drop or click). Then choose a name, an address, what to detect for, and click the map for its location. **Import & analyse** turns it into a camera that the AI watches live in about 15 s. |
| **Add camera** | Add a real camera: name, **stream URL** (RTSP like `rtsp://user:pass@IP:554/...`, a phone URL, `0` for the webcam, or a file path), address, direction, detections, **click the map** for its location. *Ground calibration* is optional, for precise GPS of events. |
| Each camera card | Live thumbnail, status dot, the stream URL with the password hidden, location, last frame, number of zones, and icons for what it detects |
| **Zones** | Opens the zone editor (below) |
| **Pencil** | Edit the camera |
| **Disable / Enable** | Stop or start AI analysis of this camera (frees CPU) |
| **Bin** | Delete the camera. An imported video file is deleted too. |

**Zone editor:**
| Item | What it does |
|---|---|
| **Click on the camera picture** | Adds a corner point. 3 or more points make a polygon. |
| **Undo point / Clear** | Remove the last point, or all points |
| **Refresh frame** | Loads a fresh picture from the camera |
| **Zone name**, **Zone type** | *Restricted area* triggers intrusion; *Water body* enables drowning detection |
| **Dwell time** | How many seconds a person must stay inside before the alert |
| **Save zone** | Saves it; the AI uses it immediately |
| Bin icon next to a zone | Deletes that zone |

### Responders
- Units are grouped by agency, each showing how many are ready.
- Each unit has a **status dropdown** (available, dispatched, en route, on scene, offline) to change by hand, and a **bin** to remove it.
- **Add unit** opens a form for the name, agency, contact and **location on the map**.
- The right side shows a map of all units.

**How availability is decided:** each unit has a status in the database. Dispatch sets it to *dispatched*. The responder's buttons set *en route* and *on scene*, and *Completed* sets it back to *available*. Resolving an incident frees its units, and an operator can change any status by hand. Only units whose status is *available* are suggested, nearest first (PostGIS `ST_Distance`), and *offline* units cannot be dispatched at all.

### Analytics
| Item | What it does |
|---|---|
| **Validated on public datasets** | Accuracy proof: fall, fire and smoke detection rates and false-alarm rates measured on real videos, plus the colour-heuristic baseline |
| **Alerts by type · 24 h** | Bar chart per emergency type |
| **Alerts per hour · 24 h** | When alerts happened (hover a bar for the number) |
| **Response performance** | Average time to verify, time to dispatch, false-alarm rate, open incidents |
| **Date range** dropdown | Last 24 h / 7 days / 30 days / **All time**, loaded from the database |
| **Search** box | Find by incident number, camera or notes |
| **Type / status** dropdowns | Filter the table |
| **CSV** | Downloads the filtered history as an Excel-ready file |
| Table rows | Click one to open that incident on the Command page |
| **Sign-in history** | Every signup, login, logout and failed login, with time, user, IP and browser. Admins see everyone; others see only their own. |

### My Unit (responder login, e.g. `ambulance1`)
| Item | What it does |
|---|---|
| Unit name + status | e.g. Ambulance A1, available |
| **Share live location** | Sends your phone/laptop GPS to the control-room map every 10 s |
| Assignment card | The emergency, its address, distance and ETA, snapshot, mini map from you to the scene, evidence video |
| **Acknowledge → En route → Arrived on scene → Mark completed** | Each tap updates the control room live |
| **Navigate** | Opens OpenStreetMap driving directions to the scene |
| **Recent** | Your finished jobs |

---

## 17. Demo checklist, step by step (about 10 minutes)

**The night before**
1. Practise the webcam demos once, with the lights on.
2. *(Optional)* Clear the queue but keep the history: open PowerShell in the `backend` folder and run `.venv\Scripts\python.exe close_open_incidents.py`.

**10 minutes before the interview**
1. Close other heavy programs, then **double-click `start-safewatch.bat`** in the project folder. Three windows open (backend, detector, frontend), then the browser at http://localhost:5173. Run it only once; keep the three windows open.
2. Open a **second browser window** (Incognito) and log in as `ambulance1` / `responder123`. Keep it aside.

**During the interview**

| # | Show | Say |
|---|---|---|
| 1 | **Sign-in page → Create an account** with your name and e-mail | "Secure login with roles; every sign-in is logged." |
| 2 | **Command page**: stats strip, queue, map, thumbnails | "This is the control room. Cameras run real CCTV footage from research datasets, and the AI watches them live." |
| 3 | **Live Wall** | "This is what the AI sees: people, falls (DOWN), restricted zones, fire and smoke." |
| 4 | Back to **Command**; wait for a pop-up | "An alert just arrived in real time, with a siren and its location on the map." |
| 5 | Open a **Person Fall** alert, play the **Evidence clip**, show the **Model output** | "It recorded 5 seconds before the fall. It measured the torso angle and how fast the body dropped." |
| 6 | **Verify → Nearest per agency → Dispatch** | "PostGIS finds the nearest free ambulance, with distance and ETA." |
| 7 | Switch to the **ambulance1** window: **Acknowledge → En route → Arrived → Completed**. Switch back. | "The responder got it instantly, and the control room updates live." Then click **Resolve**. |
| 8 | Open a **Fire** alert | "Fire calls the fire brigade, an ambulance *and* police." |
| 9 | **Cameras → Import recording** → `demo-recordings/import/fire_single_FIRESENSE-pos2.mp4` → click the map → **Import & analyse**. Go to **Command** and wait about 30 s. | "Any CCTV footage can be uploaded and analysed. Here's a brand-new fire alert from it." |
| 10 | **Webcam**: Live Wall → ⤢ on *Demo Webcam*. Walk into the **right third** for 3 s. | "Now truly live, on my laptop camera: intrusion." |
| 11 | *(optional)* Sit close on the **left side**, head and shoulders only, and **wave both arms** | "Signs of drowning: arms waving, body submerged, bobbing." |
| 12 | **Analytics**: accuracy panel → **All time** → **CSV** → **Sign-in history** | "77% of real falls detected; the trained model cut fire false alarms from 69% to 19%; everything is stored, including the account I created at the start." |

**If something doesn't happen**
- Use the older alerts already in the queue.
- Each camera raises one alert of each type per minute, so wait 60 s.
- Thumbnails say "NO SIGNAL": the detector window was closed. Double-click `start-safewatch.bat` again (it only starts what's missing).
- "Upload failed: cannot reach the SafeWatch server": the backend window was closed. Start it again the same way.
- Backup videos are in `demo-recordings/evidence/`.

---

## 18. What every file does

### `backend/`: the server (FastAPI + PostgreSQL)
| File | Job |
|---|---|
| `app/main.py` | Starts the server: database setup, demo data, all routes, the `/media` files, the `/ws` live connection |
| `app/config.py` | Reads settings from `.env` (database password, secret keys, map centre) |
| `app/database.py` | Connects to PostgreSQL, creates tables, small upgrades (e.g. adds the e-mail column) |
| `app/models.py` | The database tables: users, sign-in history, cameras, zones, incidents, units, dispatches, audit log |
| `app/schemas.py` | Rules for incoming data (e.g. valid e-mail, password ≥ 8 characters) |
| `app/serializers.py` | Turns database rows into the JSON the website reads |
| `app/geo.py` | Converts lat/lon to PostGIS map points and polygons |
| `app/security.py` | Password hashing (bcrypt), login tokens (JWT), who can do what (roles), the detector's API key |
| `app/realtime.py` | Keeps track of open browsers and pushes live events to all of them |
| `app/routers/auth.py` | Sign-up, login, logout, sign-in history, user admin |
| `app/routers/cameras.py` | Cameras, **import recording**, camera online/offline heartbeats, zones |
| `app/routers/incidents.py` | Creating alerts (with duplicate merging), evidence upload, verify, false alarm, dispatch, resolve, notes, statistics |
| `app/routers/units.py` | Response units, a responder's own jobs, status updates |
| `app/services/dispatch.py` | Which agencies handle which emergency, severity, **nearest units via PostGIS**, ETA |
| `app/seed.py` | Creates demo accounts, 10 units and the demo cameras on the first run |
| `check_system.py` | Automatic test of the whole system (PASS/FAIL list) |
| `close_open_incidents.py` | Empties the queue before a demo (keeps history) |
| `media/` | Stored snapshots, evidence clips and uploaded recordings |
| `requirements.txt`, `.env`, `Dockerfile` | Python packages, settings, Docker build |

### `detector/`: the AI (Python + OpenCV + YOLO)
| File | Job |
|---|---|
| `main.py` | Starts the AI: loads models, watches the camera list, runs one worker per camera. Refuses to start if another detector is already running. |
| `config.py` | AI settings from `.env` (models, thresholds, speeds) |
| `camera_worker.py` | **The core loop** for each camera: read frame → find people → check fall/intrusion/water → check fire/smoke → draw overlay → send alerts and evidence clips |
| `video.py` | Opens cameras/files/RTSP, reconnects if a stream drops, writes MP4 clips |
| `geometry.py` | Person helpers (torso angle, foot point), zone shapes, pixel → GPS conversion |
| `analyzers/fall.py` | Fall detection logic |
| `analyzers/intrusion.py` | Restricted-zone logic |
| `analyzers/water.py` | Drowning/distress logic |
| `analyzers/fire_smoke.py` | Fire and smoke (trained YOLO model, or the colour fallback) |
| `annotate.py` | Draws boxes, tags, zones and banners on the video |
| `stream_server.py` | Serves the live AI video to the website (port 8100) |
| `api_client.py` | Sends alerts, clips and heartbeats to the backend |
| `models/fire_smoke_yolo11n.pt` | **Our trained fire/smoke AI model** |
| `yolo11n-pose.pt` | The person + body-pose AI model (downloaded automatically) |
| `train_fire_smoke.py`, `prepare_fire_training.py` | How the fire/smoke model was trained |
| `evaluate_video.py` | Runs the AI on one video and lists every alert with timestamps |
| `benchmark_datasets.py` | Measures accuracy on all dataset videos (the Analytics numbers) |
| `prepare_demo_videos.py` | Builds the looping camera videos from the raw datasets |
| `register_dataset_cameras.py` | Adds those videos as cameras on the map |
| `make_demo_folder.py` | Builds the `demo-recordings` folder |
| `simulate_incident.py` | Developer tool for fake alerts. Not used in the demo. |
| `tests/test_analyzers.py` | Unit tests for fall, intrusion and water logic |
| `datasets/raw/` | The original downloaded research videos |

### `frontend/`: the website (React + Tailwind + Leaflet)
| File | Job |
|---|---|
| `src/main.jsx` | Starts the website, loads fonts and theme |
| `src/App.jsx` | Decides which screens you see (login, control room or responder) |
| `src/index.css` | All colours, light/dark themes, map and animation styles |
| `src/context/AuthContext.jsx` | Login, sign-up, logout state |
| `src/context/DataContext.jsx` | Loads data and keeps it **live via WebSocket**; triggers pop-ups and the siren |
| `src/lib/api.js` | Talks to the backend; upload with progress bar |
| `src/lib/constants.jsx` | Emergency types, agencies, icons, colours |
| `src/lib/mapIcons.jsx` | Map marker shapes |
| `src/lib/alarm.js` | Makes the siren sound |
| `src/lib/format.js` | Formats times, distances, percentages |
| `src/lib/theme.js` | Saves your light/dark choice |
| `src/pages/Login.jsx` | Sign-in and Create account page |
| `src/pages/Dashboard.jsx` | Command page |
| `src/pages/LiveWall.jsx` | Live Wall |
| `src/pages/Cameras.jsx` | Cameras page |
| `src/pages/Units.jsx` | Responders page |
| `src/pages/History.jsx` | Analytics page |
| `src/pages/Responder.jsx` | My Unit (responder) page |
| `src/components/Layout.jsx` | Sidebar and top bar |
| `src/components/StatsBar.jsx` | The stats strip |
| `src/components/IncidentFeed.jsx` | The incident queue |
| `src/components/IncidentMap.jsx` | The map |
| `src/components/IncidentDetail.jsx` | The incident panel (evidence, verify, dispatch, audit log) |
| `src/components/Toasts.jsx` | Pop-up alert cards |
| `src/components/LiveStream.jsx` | Live video and thumbnails |
| `src/components/ZoneEditor.jsx` | Drawing zones |
| `src/components/ImportRecording.jsx` | Import recording dialog |
| `src/components/MapPicker.jsx` | Click-the-map location picker |
| `src/components/Benchmark.jsx` | Accuracy panel |
| `src/components/SessionHistory.jsx` | Sign-in history table |
| `src/components/ThemeToggle.jsx` | Light/dark button |
| `src/components/ui.jsx` | Shared buttons, badges, pop-up windows, input styles |
| `public/benchmark.json` | Accuracy results shown on Analytics |
| `vite.config.js`, `package.json` | Dev server setup and JavaScript packages |

### Project root
| Item | Job |
|---|---|
| `start-safewatch.bat` | Double-click to start everything (runs the script below) |
| `start-safewatch.ps1` | Starts backend, detector and website in three windows; skips anything already running |
| `demo-recordings/` | All demo videos (`feeds`, `import`, `evidence`) + `README.txt` |
| `docs/PROJECT_GUIDE.md` | This guide (also as `docs/SafeWatch_Project_Guide.docx`) |
| `README.md` | Setup instructions |
| `docker-compose.yml` | Optional: run everything with Docker |
| `.gitignore` | Files git should ignore |

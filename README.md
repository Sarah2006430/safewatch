# SafeWatch: Emergency Detection, Public Safety & Response Coordination

SafeWatch watches CCTV and IP cameras with AI and detects emergencies:

| Emergency | How it is detected |
|---|---|
| 🧍 **Visible falls** | YOLO11-pose keypoints and ByteTrack tracking. The person's torso angle and bounding-box shape change from upright to lying within about 2.5 s, the body centre drops quickly, and the person stays down for 1 s or more. A person seen lying for a long time with no fall observed is flagged as "person down". |
| 🔥 **Fire** | A custom YOLO fire/smoke model if you provide one. Otherwise an OpenCV check for flame colours (HSV, RGB and YCrCb rules) that flicker and move. |
| 💨 **Smoke** | The same YOLO model, or a heuristic: moving grey, low-saturation regions that blur the background. |
| 🚷 **Restricted-area intrusion** | A person's foot point stays inside a restricted polygon (drawn in the UI) longer than the zone's dwell time. |
| 🌊 **Distress near water** | Inside a water zone it looks at raised or waving arms, a body that is submerged (head visible, no hips or knees), vertical bobbing with no forward progress, and a person who **disappears** while in the water (possible submersion). |

Each detection becomes a **location-tagged alert** with **video evidence** (an annotated snapshot plus an H.264 clip covering about 5 s before and 6 s after the event). The alert is pushed **in real time over WebSockets** to the control room. An **operator verifies** it, then **coordinates the response**. PostGIS finds the nearest available **police, medical, fire and rescue** units and estimates their ETAs. Responders get the assignment on their own screen, update their status, and can share their live GPS location.

```
 CCTV / IP cameras ──RTSP──▶  Detector (Python · OpenCV · YOLO)  ──REST──▶  Backend (FastAPI)  ──▶ PostgreSQL + PostGIS
                              │ pose tracking, fire/smoke,          snapshot    │ incidents, dispatch,
                              │ zones, evidence clips               + clip      │ nearest units (ST_Distance)
                              └── MJPEG live view ───────┐                      │
                                                         ▼                      ▼ WebSockets
                                             React + Tailwind + Leaflet/OpenStreetMap dashboard
                                             (operators · responders)
```

## Tech stack

| Layer | Used for |
|---|---|
| **React.js + Tailwind CSS** (Vite) | Command-centre dashboard, live camera wall, camera/zone editor, responder app, analytics |
| **Python, OpenCV, YOLO (Ultralytics YOLO11)** | Pose detection and tracking, fall / intrusion / water-distress logic, fire and smoke detection, evidence clips |
| **FastAPI** | REST API, JWT auth, roles (admin, operator, responder), media storage |
| **PostgreSQL + PostGIS** | All locations stored as `GEOGRAPHY(POINT/POLYGON, 4326)` with GiST indexes; nearest-unit search with `ST_Distance` |
| **Leaflet + OpenStreetMap** | Live incident map, responders, cameras, zone footprints, dispatch routes, location pickers |
| **WebSockets** | Instant alerts, incident, unit and camera updates, responder assignments |
| **CCTV / IP cameras over RTSP** | `rtsp://` streams over TCP with auto-reconnect. HTTP/MJPEG URLs, video files and webcams also work |

## Project layout

```
backend/    FastAPI app (app/main.py), models, routers, PostGIS dispatch service, seed data
detector/   main.py (supervisor), camera_worker.py, analyzers/ (fall, fire_smoke, intrusion, water),
            stream_server.py (MJPEG), train_fire_smoke.py, simulate_incident.py, tests/
frontend/   React app (src/pages, src/components, src/context)
docker-compose.yml
```

---

## Quick start (everything already installed)
```bash
powershell -ExecutionPolicy Bypass -File .\start-safewatch.ps1
```
This opens the backend, detector and frontend in three windows, then opens http://localhost:5173 in your browser.

Check everything works (backend + detector running), and optionally clear the queue before a demo. Nothing is deleted; incidents are marked resolved and stay in history:
```bash
cd backend
.venv\Scripts\python.exe check_system.py
.venv\Scripts\python.exe close_open_incidents.py
```

## Running it (Windows, without Docker)

### 1. PostgreSQL + PostGIS
Install PostgreSQL 16 from https://www.postgresql.org/download/windows/. At the end of setup, open **Stack Builder** and choose **Spatial Extensions → PostGIS**. Then create the database:
```bash
psql -U postgres -c "CREATE DATABASE emergency;"
```
The backend runs `CREATE EXTENSION postgis` itself on first start.

*(If you have Docker, you can run just the database with `docker compose up -d db`.)*

### 2. Backend (FastAPI)
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env        # edit DATABASE_URL password / DEFAULT_LAT / DEFAULT_LON for your city
uvicorn app.main:app --reload --port 8000
```
API docs: http://localhost:8000/docs

### 3. Detector (AI / computer vision)
```bash
cd detector
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt      # installs ultralytics + torch (large download)
copy .env.example .env
python main.py
```
The YOLO11 pose weights download automatically on the first run. The demo camera uses your **webcam** (`stream_url = 0`). Live annotated streams are served at http://localhost:8100/stream/1.

### 4. Frontend (React + Tailwind)
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173.

### Demo accounts (created by the seed)
| User | Password | Role |
|---|---|---|
| `admin` | `admin123` | Admin (control room) |
| `operator` | `operator123` | Operator (control room) |
| `ambulance1` | `responder123` | Responder for Ambulance A1 |
| `police1` | `responder123` | Responder for Police Patrol 101 |

Change these passwords and `JWT_SECRET` / `DETECTOR_API_KEY` before any real deployment.

### With Docker (everything)
```bash
docker compose up --build
```
Dashboard: http://localhost:8080. Docker on Windows can't reach a webcam, so add RTSP cameras in that setup.

---

## Demo walkthrough
1. Log in as **operator** and open **Cameras**. The demo webcam has a restricted zone over the right 30 % of the frame.
2. Walk into the right side of the frame. After 2 s an **intrusion** alert appears: a siren plays, a toast pops up, and the marker pulses on the map.
3. Lie down quickly in front of the camera. You get a **fall** alert. Hold a lighter or a flame video up to the camera for **fire**.
4. Click the alert. Review the **video evidence clip** and snapshot, or switch to the live view, then press **Verify** or **False alarm**.
5. The **Coordinate response** panel lists the nearest available units of the right agencies (from PostGIS) with distance and ETA. Select them and click **Dispatch**.
6. In another browser, log in as **ambulance1**. The assignment shows up instantly. Press Acknowledge, En route, On scene, then Completed. The control-room timeline and map update live.
7. **Resolve** the incident. **Analytics** shows response times and false-alarm rates.

No camera? Simulate alerts:
```bash
cd detector
python simulate_incident.py --type water_distress --camera 1
```

### Adding a real CCTV / IP camera
Go to **Cameras → Add camera**, paste the RTSP URL, and click the map to set where the camera is. Common URL formats:
- Hikvision: `rtsp://user:pass@IP:554/Streaming/Channels/101`
- Dahua / CP Plus: `rtsp://user:pass@IP:554/cam/realmonitor?channel=1&subtype=0`
- Android "IP Webcam" app: `http://PHONE_IP:8080/video`

Then open **Zones** and click points on the camera frame to draw restricted areas or water bodies.

**Precise location (optional):** in the camera's *Ground calibration* field, map 4 image points to 4 GPS points. The detector then converts the exact pixel where the person or fire is into lat/lon with a homography, instead of using the camera's own location.

### Real footage from public datasets (no staging needed)
You can't start a fire or fall over in an interview, so SafeWatch can run on **recorded real-world footage from public research datasets**. The files play as looping cameras, and the detector analyses them live, exactly like an RTSP feed. Nothing is simulated: every alert comes from YOLO seeing that footage.

| Camera on the map | Footage | Source / licence |
|---|---|---|
| Care Home · Ward 3 | 30 real falls (RGB view) | [UR Fall Detection Dataset](http://fenix.ur.edu.pl/~mkepski/ds/uf.html), University of Rzeszów (Kwolek & Kepski 2014) |
| Data Centre · Server Hall Door | 15 everyday-activity clips; a restricted zone covers the doorway | UR Fall Detection Dataset (ADL sequences) |
| Industrial Yard · North | 11 real flame videos | [FIRESENSE database](https://zenodo.org/records/836749), CERTH / Bilkent University, CC-BY 4.0 |
| Hillside Watchtower | 13 real smoke videos | FIRESENSE, CC-BY 4.0 |
| Lakeside Promenade | Swimmers in a bog pool (aerial) | [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Swimmers_in_Ohepalu_bog_pool,_July_2021.webm), CC0 |

There is no freely downloadable drowning-video dataset (SwimID, for example, requires a signed agreement). Water distress is therefore best shown **live on the webcam**: sit close so only your head and shoulders are in view inside the "Pool edge" zone (left side of the frame), then raise and wave both arms.

Rebuild everything:
```bash
cd detector
python prepare_demo_videos.py                         # datasets/raw -> demo-recordings/feeds/*.mp4
python register_dataset_cameras.py --password admin123 # adds the cameras and zones to the backend
python main.py
```

Measure accuracy clip by clip (same models and logic as the live detector). The results also appear on the **Analytics** page:
```bash
python benchmark_datasets.py
python evaluate_video.py datasets/demo/falls_ur_room.mp4 --detect fall   # timestamps of every alert
```

**Measured results** (12 Nov 2026, laptop CPU, YOLO11n-pose at 480 px, person confidence 0.15, fire/smoke model at 320 px):

| Detector | Event clips detected | Control clips with a false alarm |
|---|---|---|
| Fall (UR Fall: 30 falls / 15 daily-activity clips) | **23 / 30 (77 %)** | 2 / 15 (13 %) |
| Fire, trained YOLO11n (FIRESENSE: 11 fire / 16 hard negatives) | **9 / 11 (82 %)** | 3 / 16 (19 %) |
| Smoke, trained YOLO11n (FIRESENSE: 13 smoke / 9 negatives) | **9 / 13 (69 %)** | 0 / 9 (0 %) |
| *Baseline: OpenCV colour heuristic, fire* | *11 / 11* | *11 / 16 (69 %)* |
| *Baseline: OpenCV colour heuristic, smoke* | *5 / 13* | *0 / 9* |

The fire/smoke model is YOLO11n fine-tuned on 3,000 images of a CC-BY-4.0 fire/smoke dataset ([Hugging Face](https://huggingface.co/datasets/jojomoi-meme/fog_fire_detection), compiled from Roboflow Universe) for 12 epochs at 320 px on a laptop CPU. It reached **mAP50 0.43** on 800 held-out images, and cut the heuristic's fire false-alarm rate from 69 % to 19 %. Most missed falls are people who end up curled on the floor at the bottom edge of the frame, where the nano pose model loses them. `yolo11s-pose` or a GPU would improve this.

Retrain the fire/smoke model:
```bash
python prepare_fire_training.py C:/path/fire_smoke_dataset.zip --out C:/path/fire_subset --train 4000 --val 800
python train_fire_smoke.py --data C:/path/fire_subset/data.yaml --epochs 12 --imgsz 320 --device cpu --fraction 0.75
copy runs\fire_smoke\train\weights\best.pt models\fire_smoke_yolo11n.pt
```
Then set `FIRE_SMOKE_MODEL=models/fire_smoke_yolo11n.pt` in `detector/.env`.

### Import a recording from the UI
Cameras → **Import recording**: upload any MP4/AVI/MOV/MKV/WEBM file (up to 1 GB), choose what to analyse and click its location on the map. It becomes a camera that the detector analyses live (looping). Short ready-made clips are in `demo-recordings/import/`.

The full explanation of the system and the interview demo script are in [docs/PROJECT_GUIDE.md](docs/PROJECT_GUIDE.md).

### Better fire / smoke accuracy
The colour heuristic works for a demo. For real use, train a YOLO model on the D-Fire dataset:
```bash
cd detector
python train_fire_smoke.py --data fire_smoke_data.yaml --epochs 50
```
Then set `FIRE_SMOKE_MODEL=runs/fire_smoke/train/weights/best.pt` in `detector/.env`.

### Tests
```bash
cd detector
python -m unittest discover tests
```
The tests check the fall, intrusion, water-distress and geo-calibration logic on synthetic data.

## Key API endpoints
| Method | Path | Purpose |
|---|---|---|
| POST | `/api/auth/login` | JWT login |
| GET/POST/PATCH | `/api/cameras`, `/api/cameras/{id}/zones` | Cameras and zones |
| POST | `/api/incidents` *(detector, X-API-Key)* | Create an alert with a snapshot |
| POST | `/api/incidents/{id}/clip` *(detector)* | Attach the evidence video |
| POST | `/api/incidents/{id}/verify` · `/false-alarm` · `/dispatch` · `/resolve` · `/notes` | Operator workflow |
| GET | `/api/incidents/{id}/nearby-units` | PostGIS nearest responders |
| GET | `/api/incidents/stats` | Dashboard analytics |
| GET/POST/PATCH | `/api/units`, `/api/dispatches/mine`, `/api/dispatches/{id}/status` | Responder coordination |
| WS | `/ws?token=…` | Real-time events |

## Limitations / notes
- Detection accuracy depends on camera angle, lighting and resolution. Every alert goes to a human operator, who confirms it before anyone is dispatched.
- Evidence media (`/media`) and the MJPEG streams have no authentication. Put them behind a reverse proxy with auth before deploying for real.
- ETAs are straight-line distance × 1.35 at average urban speeds. Plug in OSRM if you need road routing.

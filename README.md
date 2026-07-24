# DeepGuard AI — Multimodal Anti-Spoofing Verification System

## App Description

DeepGuard AI is a privacy-first, edge-based identity verification system that detects presentation attacks — printed photos, phone/video replays, and AI-generated deepfakes — at security checkpoints such as office entry gates, bank counters, ATMs, and remote onboarding calls.

Most face-verification systems today only check **"does this face match?"** — they don't check **"is this a real, living person present right now?"** That gap is exactly what attackers exploit using cheap, easily available tricks like holding up a printed photo or playing a video on a phone screen. Systems that do attempt to catch this typically stream raw video to a central cloud server, which adds latency, consumes bandwidth, and exposes sensitive biometric data as it travels off-device.

DeepGuard AI solves both problems at once: it performs liveness and deepfake detection close to the camera, using only lightweight, anonymized facial landmark data instead of raw video — so verification is fast, and no actual face footage ever needs to leave the local pipeline.

### Problem Statement

> Face-based verification systems used at security checkpoints (offices, banks, ATMs, remote onboarding) can be fooled by presentation attacks — printed photos, replayed videos, and AI-generated deepfakes — because most systems verify identity based on appearance alone, without confirming the subject is a live, physically present human. Existing solutions that do attempt liveness detection typically require streaming raw video to a central server, which introduces latency, bandwidth cost, and exposes sensitive biometric data to interception or misuse.

### Our Solution

> DeepGuard AI checks liveness and deepfake spoofing locally, close to the point of capture, using anonymized facial landmark coordinates instead of raw video — catching fake verification attempts in real time, without ever transmitting a user's actual face footage.

### Key Features

- **Face landmark extraction** — captures facial structure as coordinate data only, never storing or transmitting raw images unnecessarily
- **Liveness detection** — confirms natural human movement (e.g. blinking, head motion) to rule out static photos
- **Deepfake / spoof detection** — identifies printed photos, phone/video replays, and AI-generated faces
- **Real-time risk scoring** — combines liveness and spoof-detection results into a single, interpretable risk score
- **Alert dashboard** — flags high-risk verification attempts instantly for review
- **Local logging** — stores anonymized verification history for auditing and analysis



## Tech Stack

- **Language:** Python 3.10+
- **Face landmark detection:** MediaPipe
- **AI inference:** ONNX Runtime
- **Backend:** FastAPI
- **Frontend:** React
- **Database:** SQLite

---

## Setup Instructions (from scratch)

### Prerequisites

- Python 3.10 or higher installed
- Node.js 18+ and npm installed (for the frontend)
- A working webcam
- Git installed

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/DeepGuard-AI.git
cd DeepGuard-AI
```

### 2. Set up the backend

```bash
cd backend
python -m venv venv
source venv/bin/activate      # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

`requirements.txt` should include, at minimum:

```
opencv-python
mediapipe
fastapi
uvicorn
onnxruntime
numpy
```

### 3. Set up the frontend

```bash
cd ../frontend
npm install
```

### 4. Add the AI models

Place the required ONNX models inside `backend/models/`:

```
backend/models/deepfake_model.onnx
backend/models/liveness_model.onnx
```

---

## Run and Usage Instructions

### 1. Start the backend

```bash
cd backend
uvicorn dashboard:app --reload --port 8000
```

The backend will be available at `http://localhost:8000`.

### 2. Start the frontend

```bash
cd frontend
npm install
npm run dev

```

The app will open at `http://localhost:3000`.

### 3. Using the app

1. Open the web app in your browser.
2. Click **Start Verification**.
3. Allow webcam access and capture your face.
4. The system will check for liveness (e.g. ask you to blink) and analyze the result for spoofing.
5. View the result on the dashboard: **VERIFIED (low risk)** or **HIGH RISK (spoof/attack detected)**.
6. Check the **Supervisor Dashboard** page for a log of all verification attempts.

---

## Project Structure

```
DeepGuard-AI/
├── frontend/                  # React app (verification UI + supervisor dashboard)
├── backend/
│   ├── feature_extractor.py   # Captures frames and extracts face landmarks
│   ├── ai_engine.py           # Runs liveness and deepfake detection models
│   ├── risk_engine.py         # Combines results into a single risk score
│   ├── dashboard.py           # FastAPI app tying everything together
│   ├── database.py            # SQLite logging of verification attempts
│   ├── models/
│   │   ├── deepfake_model.onnx
│   │   └── liveness_model.onnx
│   └── requirements.txt
├── sqlite.db
├── LICENSE
└── README.md
```

---

## Notes

- This project prioritizes data minimization: raw video frames are processed locally and are not stored or transmitted; only anonymized landmark coordinates and verification outcomes are logged.
- The anti-spoofing and liveness models used are pretrained and optimized for lightweight, real-time inference.

## References

- MediaPipe Face Landmarker — https://developers.google.com/mediapipe
- ONNX Runtime — https://onnxruntime.ai/
- FastAPI Documentation — https://fastapi.tiangolo.com/


---

## Developers

Niveditha

---

## License

This project is licensed under the [MIT License](LICENSE).

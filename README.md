# 🛡️ DeepGuard AI — Multimodal Anti-Spoofing Verification System

## 📌 App Description

DeepGuard AI is a **privacy-first, edge-based identity verification system** that detects presentation attacks — printed photos, phone/video replays, and AI-generated deepfakes — at security checkpoints such as office entry gates, bank counters, ATMs, and remote onboarding calls.

Most face-verification systems today only check **"Does this face match?"** They don't verify **"Is this a real, living person present right now?"** Attackers exploit this gap using printed photos, replay videos, or AI-generated faces.

Many existing liveness solutions stream raw video to cloud servers, increasing latency, bandwidth usage, and privacy risks.

✨ **DeepGuard AI solves both problems by performing liveness and deepfake detection locally using anonymized facial landmark coordinates instead of raw video.** Verification is fast, secure, and privacy-preserving.
---

# 🚨 Problem Statement

Face verification systems used in:

- 🏢 Office Entry
- 🏦 Banks
- 💳 ATMs
- 🌐 Remote KYC & Onboarding

can be fooled by:

- 📸 Printed Photos
- 📱 Replay Videos
- 🤖 AI-generated Deepfakes

Most systems only verify appearance instead of confirming a **live human is physically present.**

Cloud-based liveness detection also introduces:

- ⏳ Higher latency
- 🌍 Bandwidth costs
- 🔓 Privacy risks from transmitting biometric data

---

# 💡 Our Solution

DeepGuard AI performs **real-time liveness and deepfake detection directly at the edge**, using only facial landmark coordinates rather than raw images.

✅ Detects spoofing instantly

✅ No raw face video leaves the device

✅ Privacy-first by design

---

# ✨ Key Features

- 👤 **Face Landmark Extraction**
  - Captures only facial landmark coordinates
  - Never stores raw images unnecessarily

- 👁️ **Liveness Detection**
  - Detects blinking
  - Head movement
  - Natural facial motion

- 🧠 **Deepfake & Spoof Detection**
  - Printed photos
  - Phone replay attacks
  - Video replay attacks
  - AI-generated faces

- 📊 **Real-Time Risk Scoring**
  - Combines all detection signals
  - Produces one interpretable risk score

- 🚨 **Alert Dashboard**
  - Instantly flags suspicious verification attempts

- 🗂️ **Local Logging**
  - Stores anonymized verification history
  - Useful for auditing and analytics

---

# 🏗️ System Architecture

```text
                    👤 User
                      │
                      ▼
               📷 Webcam Capture
                      │
                      ▼
        👁️ Face Detection (MediaPipe)
                      │
                      ▼
      📍 Facial Landmark Extraction
      (Only Landmark Coordinates)
                      │
         ❌ No Raw Images Stored
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
 🫣 Liveness Detection      🤖 Deepfake Detection
 (Blink, Head Motion)     (Photo, Replay, AI Face)
          │                       │
          └───────────┬───────────┘
                      ▼
           🧠 Risk Scoring Engine
       (Combine AI Predictions)
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
   ✅ VERIFIED              🚨 HIGH RISK
          │                       │
          └───────────┬───────────┘
                      ▼
          📊 Dashboard & Alerts
                      │
                      ▼
      🗄️ SQLite Audit Log (Local)
```

## 🔄 Workflow

1. 📷 The webcam captures the user's face.
2. 👁️ MediaPipe detects the face and extracts **468 facial landmark coordinates**.
3. 🔒 Raw video frames are processed locally and discarded.
4. 📍 Only landmark coordinates are passed to the AI models.
5. 🫣 The liveness model checks for natural human behavior such as blinking and head movement.
6. 🤖 The spoof detection model detects printed photos, replay attacks, and AI-generated deepfakes.
7. 🧠 The Risk Engine combines the outputs of both models into a single confidence score.
8. 🚦 Based on the score, the system returns either:
   - ✅ VERIFIED
   - 🚨 HIGH RISK
9. 📊 Results are displayed on the dashboard.
10. 🗄️ Only anonymized verification results are stored in the local SQLite database for auditing.

---

# 🛠 Tech Stack

| Component | Technology |
|-----------|------------|
| 💻 Language | Python 3.10+ |
| 👤 Face Detection | MediaPipe |
| 🧠 AI Inference | ONNX Runtime |
| ⚡ Backend | FastAPI |
| 🎨 Frontend | React |
| 🗄 Database | SQLite |

---

# 🚀 Setup Instructions

## 📋 Prerequisites

- ✅ Python 3.10+
- ✅ Node.js 18+
- ✅ npm
- ✅ Git
- ✅ Webcam

---

## 1️⃣ Clone the Repository

```bash
git clone https://github.com/<your-username>/DeepGuard-AI.git

cd DeepGuard-AI
```

---

## 2️⃣ Backend Setup

```bash
cd backend

python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate

pip install -r requirements.txt
```

### requirements.txt

```text
opencv-python
mediapipe
fastapi
uvicorn
onnxruntime
numpy
```

---

## 3️⃣ Frontend Setup

```bash
cd ../frontend

npm install
```

---

## 4️⃣ Add AI Models

Place the ONNX models inside:

```text
backend/models/

├── deepfake_model.onnx
└── liveness_model.onnx
```

---

# ▶️ Run the Project

## 🔹 Start Backend

```bash
cd backend

uvicorn dashboard:app --reload --port 8000
```

Backend runs at

```
http://localhost:8000
```

---

## 🔹 Start Frontend

```bash
cd frontend

npm install

npm run dev
```

Frontend runs at

```
http://localhost:3000
```

---

# 📱 Using the App

1. 🌐 Open the web application.
2. ▶️ Click **Start Verification**.
3. 📷 Allow webcam access.
4. 👁️ Blink or move naturally.
5. 🧠 DeepGuard analyzes liveness and spoofing.
6. 📊 View the result:

✅ VERIFIED

or

🚨 HIGH RISK

7. 📋 Open the Supervisor Dashboard to review verification history.

---


# 📂 Project Structure

```text
DeepGuard-AI/

├── frontend/
│   └── React application

├── backend/
│   ├── feature_extractor.py
│   ├── ai_engine.py
│   ├── risk_engine.py
│   ├── dashboard.py
│   ├── database.py
│   ├── models/
│   │   ├── deepfake_model.onnx
│   │   └── liveness_model.onnx
│   └── requirements.txt

├── sqlite.db
├── LICENSE
└── README.md
```

---

# 🔒 Privacy First

DeepGuard AI follows a **data minimization** approach.

✅ Raw webcam frames are processed locally.

✅ No face videos are transmitted.

✅ Only anonymized landmark coordinates and verification results are stored.

---

# 📚 References

- 👤 MediaPipe Face Landmarker
  https://developers.google.com/mediapipe

- ⚡ ONNX Runtime
  https://onnxruntime.ai/

- 🚀 FastAPI
  https://fastapi.tiangolo.com/

---

# 👩‍💻 Developer

**Niveditha**

---

# 📄 License

This project is licensed under the **MIT License**.

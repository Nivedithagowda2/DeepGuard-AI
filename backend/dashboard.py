"""
dashboard.py
------------
Covers Step 6 of the build plan: the FastAPI backend.

Role in the architecture: the "switchboard operator" — the one piece that isn't
pretending to be a device. It receives a SEQUENCE of webcam frames captured over
a few seconds from the React frontend, accumulates liveness signals across that
sequence, and only makes a final decision once the recording window is complete.

Why a sequence instead of one frame: a single photo can never prove liveness -
it can only be checked for spoof-like texture. Genuine liveness (a real blink,
real head movement) can only be observed by watching multiple frames over time.
See risk_engine.py's module docstring for the specific bug this fixes.

TWO ADDITIONS in this version, aimed directly at the hackathon's judging rubric:

1. Latency instrumentation (targets "Technical Implementation" - 40/100 points,
   which explicitly includes "latency and performance"). Every frame's
   processing time is measured and averaged, logged to the database, and
   returned to the frontend - so you have a real, visible number to show
   judges instead of just claiming the system is fast.

2. WebSocket push for instant alerts (targets the Multi-Device Award, which
   rewards "a seamless, distributed AI experience", and matches your own
   proposal's wording: "a localized push frame is sent instantly to a
   supervisor's smartphone app"). The Supervisor Dashboard no longer polls -
   it receives new results the moment they happen.

Endpoints:
    POST /reset_session         - clears session state, call before a new recording
    POST /verify_frame          - accepts ONE frame from an in-progress recording,
                                   accumulates its signals (does not decide anything yet)
    POST /finalize_verification - call once the recording window (all frames) is
                                   done; analyzes the accumulated sequence, logs it,
                                   pushes it to connected dashboards, and returns
                                   the final VERIFIED / HIGH RISK result
    WS   /ws/alerts              - Supervisor Dashboard connects here for instant,
                                   real-time push of new verification results
    GET  /history                - returns recent verification attempts (used for
                                   the initial load, before live pushes start)
    GET  /health                 - simple check that the server is running

Run with:
    python -m uvicorn dashboard:app --reload --host 0.0.0.0 --port 8000

Then visit http://localhost:8000/docs for interactive API testing.
"""

import time

from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
import cv2

import feature_extractor
import ai_engine
import risk_engine
import database

app = FastAPI(title="DeepGuard AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this to your actual frontend URL before real deployment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HEAD_MOVE_THRESHOLD = 0.025  # normalized (0-1) nose-x range considered "real movement"
MIN_FRAMES_FOR_VALID_SESSION = 5  # need at least this many face-found frames to judge


def _fresh_session():
    return {
        "ear_sequence": [],
        "spoof_scores": [],
        "nose_x_sequence": [],
        "frame_latencies_ms": [],
        "any_face_found": False,
    }


# In-memory session state, accumulated across the /verify_frame calls of one
# recording window. Reset at the start of every new verification attempt.
_session_state = _fresh_session()


class ConnectionManager:
    """Tracks connected Supervisor Dashboard clients and pushes new results
    to all of them instantly - this is what replaces polling."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        # Send to every connected dashboard; drop any that have gone stale
        stale = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                stale.append(connection)
        for connection in stale:
            self.disconnect(connection)


manager = ConnectionManager()


@app.on_event("startup")
def startup_event():
    database.init_db()


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/reset_session")
def reset_session():
    """Call this before starting a new recording window, so old frame data
    from a previous attempt doesn't leak into the new one."""
    global _session_state
    _session_state = _fresh_session()
    return {"message": "Session reset"}


@app.post("/verify_frame")
async def verify_frame(file: UploadFile = File(...)):
    """
    Accepts ONE frame from an in-progress recording window. Extracts landmarks,
    EAR, and spoof score for this frame, and appends them to the session's
    running sequences. Does NOT make a final decision - that only happens in
    /finalize_verification, once the whole sequence has been collected.
    """
    frame_start = time.perf_counter()

    contents = await file.read()
    np_arr = np.frombuffer(contents, np.uint8)
    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if frame is None:
        raise HTTPException(status_code=400, detail="Could not decode uploaded image")

    extraction_result = feature_extractor.process_frame(frame)

    if not extraction_result["face_found"]:
        return {"face_found": False}

    _session_state["any_face_found"] = True
    _session_state["ear_sequence"].append(extraction_result["avg_ear"])

    nose_x = feature_extractor.get_nose_x(extraction_result["landmarks"])
    if nose_x is not None:
        _session_state["nose_x_sequence"].append(nose_x)

    spoof_score = ai_engine.get_spoof_score(frame, extraction_result["face_bbox_xywh"])
    _session_state["spoof_scores"].append(spoof_score)

    frame_elapsed_ms = (time.perf_counter() - frame_start) * 1000
    _session_state["frame_latencies_ms"].append(frame_elapsed_ms)

    return {
        "face_found": True,
        "frames_collected": len(_session_state["spoof_scores"]),
        "frame_latency_ms": round(frame_elapsed_ms, 1),
    }


@app.post("/finalize_verification")
async def finalize_verification():
    """
    Call once the frontend's recording window (all frames of one attempt) is
    complete. Analyzes the full accumulated sequence, logs it, pushes it
    instantly to any connected Supervisor Dashboards, and returns the final
    result. Resets the session automatically, ready for the next attempt.
    """
    global _session_state
    state = _session_state

    if not state["any_face_found"] or len(state["spoof_scores"]) < MIN_FRAMES_FOR_VALID_SESSION:
        _session_state = _fresh_session()
        return {
            "status": "NO FACE DETECTED",
            "risk_score": None,
            "message": "Not enough face frames captured. Please try again, "
                       "keeping your face clearly in view for the full recording.",
        }

    blink_transition = feature_extractor.detect_blink_transition(state["ear_sequence"])

    if state["nose_x_sequence"]:
        head_range = max(state["nose_x_sequence"]) - min(state["nose_x_sequence"])
    else:
        head_range = 0.0
    head_moved = head_range > HEAD_MOVE_THRESHOLD

    avg_spoof_score = float(np.mean(state["spoof_scores"]))
    avg_latency_ms = float(np.mean(state["frame_latencies_ms"])) if state["frame_latencies_ms"] else None

    risk_result = risk_engine.calculate_risk(
        avg_spoof_real_prob=avg_spoof_score,
        blink_transition_detected=blink_transition,
        head_moved=head_moved,
    )

    record_id = database.log_verification(
        status=risk_result["status"],
        risk_score=risk_result["risk_score"],
        blink_detected=blink_transition,
        spoof_score=avg_spoof_score,
        reasons=risk_result["reasons"],
        processing_time_ms=avg_latency_ms,
    )

    result_payload = {
        "id": record_id,
        "status": risk_result["status"],
        "risk_score": risk_result["risk_score"],
        "spoof_score": round(avg_spoof_score, 2),
        "blink_detected": blink_transition,
        "head_moved": head_moved,
        "reasons": risk_result["reasons"],
        "processing_time_ms": round(avg_latency_ms, 1) if avg_latency_ms else None,
        "timestamp": None,  # frontend uses its own receipt time for the live push
    }

    # Push this result instantly to any connected Supervisor Dashboards -
    # this is the "zero-latency inter-device state distribution" from the
    # original proposal, actually implemented instead of just claimed.
    await manager.broadcast({"type": "new_verification", "record": result_payload})

    # Ready for the next attempt
    _session_state = _fresh_session()

    return result_payload


@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    """
    Supervisor Dashboard connects here. Whenever /finalize_verification
    produces a new result, it's pushed to every connected client immediately -
    no polling delay.
    """
    await manager.connect(websocket)
    try:
        while True:
            # We don't expect the client to send anything meaningful, but we
            # need to keep the connection open and detect disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/history")
def history(limit: int = 50):
    return {"records": database.get_history(limit=limit)}

"""
feature_extractor.py
---------------------
Covers Steps 1, 2, 3 of the build plan:
  Step 1 - Webcam capture
  Step 2 - Face landmark extraction (MediaPipe FaceLandmarker - Tasks API)
  Step 3 - Blink detection (Eye Aspect Ratio)

Role in the architecture: "The Watcher" — pretends to be the Arduino UNO Q in the
laptop simulation. Its only job is: look at the camera, find face landmarks, detect
blinks, and hand off a small, safe payload (landmark coordinates + blink info) —
never the raw image itself — to the next stage (ai_engine.py).

IMPORTANT - MediaPipe API note:
Recent MediaPipe releases (0.10.2x+) removed the older `mediapipe.solutions.face_mesh`
API in favor of the actively-maintained Tasks API (`FaceLandmarker`). This file uses
the Tasks API so it keeps working regardless of which exact mediapipe version pip
installs on your machine. The first time you run this file, it will automatically
download the required model file (~a few MB) into backend/models/. This requires
an internet connection on first run only; after that it's cached locally.

This file works two ways:
  1. Run directly (`python feature_extractor.py`) -> opens a live webcam test window.
  2. Imported by dashboard.py -> exposes `process_frame()` for the backend to call
     on a single image at a time (e.g., a frame uploaded from the React frontend).
"""

import os
import urllib.request

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import (
    FaceLandmarker,
    FaceLandmarkerOptions,
    RunningMode,
)

# Standard MediaPipe Face Mesh eye landmark indices (topology is unchanged between
# the legacy solutions API and the new FaceLandmarker - both use the same underlying
# 468/478-point face mesh model).
LEFT_EYE = [362, 385, 387, 263, 373, 380]
RIGHT_EYE = [33, 160, 158, 133, 153, 144]

EAR_THRESHOLD = 0.21
EAR_CONSEC_FRAMES = 2

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "face_landmarker.task")
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/1/face_landmarker.task"
)

_landmarker_singleton = None


def _ensure_model_downloaded():
    os.makedirs(MODEL_DIR, exist_ok=True)
    if not os.path.exists(MODEL_PATH):
        print(f"[feature_extractor] Downloading face landmark model to {MODEL_PATH} ...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print("[feature_extractor] Model downloaded.")


def _get_landmarker():
    global _landmarker_singleton
    if _landmarker_singleton is None:
        _ensure_model_downloaded()
        options = FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=MODEL_PATH),
            running_mode=RunningMode.IMAGE,
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        _landmarker_singleton = FaceLandmarker.create_from_options(options)
    return _landmarker_singleton


def euclidean(p1, p2):
    return np.linalg.norm(np.array(p1) - np.array(p2))


def eye_aspect_ratio(landmarks, eye_indices, img_w, img_h):
    pts = []
    for idx in eye_indices:
        lm = landmarks[idx]
        pts.append((lm.x * img_w, lm.y * img_h))
    vertical_1 = euclidean(pts[1], pts[5])
    vertical_2 = euclidean(pts[2], pts[4])
    horizontal = euclidean(pts[0], pts[3])
    if horizontal == 0:
        return 0.0
    return (vertical_1 + vertical_2) / (2.0 * horizontal)


def extract_landmarks_as_list(landmarks):
    return [(lm.x, lm.y, lm.z) for lm in landmarks]


def get_face_bounding_box(landmarks, img_w, img_h, margin=0.2):
    """Returns (x1, y1, x2, y2) pixel box around the face, with a margin,
    for cropping before spoof-detection (Step 4)."""
    xs = [lm.x for lm in landmarks]
    ys = [lm.y for lm in landmarks]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)

    box_w = x_max - x_min
    box_h = y_max - y_min
    x_min = max(0.0, x_min - box_w * margin)
    x_max = min(1.0, x_max + box_w * margin)
    y_min = max(0.0, y_min - box_h * margin)
    y_max = min(1.0, y_max + box_h * margin)

    return (
        int(x_min * img_w), int(y_min * img_h),
        int(x_max * img_w), int(y_max * img_h),
    )


def get_tight_face_bbox_xywh(landmarks, img_w, img_h):
    """
    Returns a TIGHT (no margin) face bounding box as (x, y, w, h) pixel values.

    Used by the real anti-spoofing model (ai_engine.py), which applies its own
    specific crop-scale factor (e.g. 2.7x) around this tight box to reproduce
    exactly the crop region the model was trained on - a pre-margined crop
    would throw that scale factor off.
    """
    xs = [lm.x for lm in landmarks]
    ys = [lm.y for lm in landmarks]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)

    x1 = int(x_min * img_w)
    y1 = int(y_min * img_h)
    x2 = int(x_max * img_w)
    y2 = int(y_max * img_h)
    return (x1, y1, x2 - x1, y2 - y1)


def process_frame(frame_bgr):
    """
    Main entry point used by dashboard.py (Step 6).

    Input: a single BGR image (numpy array), e.g. from an uploaded webcam frame.
    Output: a dict with:
        - face_found (bool)
        - avg_ear (float or None)
        - blink_like (bool)  -> True if EAR is currently below threshold (eyes closing)
        - face_crop (numpy array or None) -> cropped face image, for Step 4
        - landmarks (list of (x,y,z) or None)
    """
    img_h, img_w = frame_bgr.shape[:2]
    rgb_frame = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

    landmarker = _get_landmarker()
    result = landmarker.detect(mp_image)

    if not result.face_landmarks:
        return {
            "face_found": False,
            "avg_ear": None,
            "blink_like": False,
            "face_crop": None,
            "landmarks": None,
            "face_bbox_xywh": None,
        }

    landmarks = result.face_landmarks[0]  # list of NormalizedLandmark for the first face

    left_ear = eye_aspect_ratio(landmarks, LEFT_EYE, img_w, img_h)
    right_ear = eye_aspect_ratio(landmarks, RIGHT_EYE, img_w, img_h)
    avg_ear = (left_ear + right_ear) / 2.0

    x1, y1, x2, y2 = get_face_bounding_box(landmarks, img_w, img_h)
    face_crop = frame_bgr[y1:y2, x1:x2].copy() if (x2 > x1 and y2 > y1) else None
    tight_bbox_xywh = get_tight_face_bbox_xywh(landmarks, img_w, img_h)

    return {
        "face_found": True,
        "avg_ear": avg_ear,
        "blink_like": avg_ear < EAR_THRESHOLD,
        "face_crop": face_crop,
        "landmarks": extract_landmarks_as_list(landmarks),
        "face_bbox_xywh": tight_bbox_xywh,
    }


def get_nose_x(landmarks_list):
    """
    Returns the normalized (0-1) horizontal position of the nose tip.
    Used across multiple frames to detect real head-turn movement -
    a static photo/screen held still will barely move; a real head turning
    left/right will show a clear horizontal trail.
    landmarks_list is the list of (x, y, z) tuples returned in process_frame()'s
    "landmarks" field. Index 1 is the nose tip in MediaPipe's face landmark topology.
    """
    if not landmarks_list or len(landmarks_list) <= 1:
        return None
    return landmarks_list[1][0]


def detect_blink_transition(ear_sequence, threshold=EAR_THRESHOLD):
    """
    Detects a GENUINE blink across a sequence of EAR readings taken over time -
    this is the key fix over single-frame blink checking.

    A real blink is a full cycle: eyes open (EAR >= threshold) -> eyes closed
    (EAR < threshold) -> eyes open again (EAR >= threshold).

    Why this matters: a static printed photo or a replayed video frame that
    happens to show partially-closed/downcast eyes will get STUCK in the
    "closed" state and never transition back to "open" within the sequence -
    so it correctly returns False, unlike a naive single-frame check which
    would have wrongly counted that one low reading as a completed blink.

    Input: a list of avg_ear float values, sampled across a recording window
           (e.g., one value per captured frame over ~3 seconds).
    Output: True if at least one full open->closed->open cycle occurred.
    """
    state = "open"
    for ear in ear_sequence:
        if ear is None:
            continue
        if state == "open" and ear < threshold:
            state = "closed"
        elif state == "closed" and ear >= threshold:
            return True  # completed a full close-then-reopen cycle
    return False


def run_standalone_test():
    """Live webcam test window — run this file directly to test Steps 1-3."""
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: Could not open webcam. Check camera permissions/index.")
        return

    total_blinks = 0
    low_ear_streak = 0

    print("Webcam started. Press 'q' to quit.")

    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            print("Failed to read frame from webcam.")
            break

        frame = cv2.flip(frame, 1)
        result = process_frame(frame)

        status_text = "No face detected"
        status_color = (0, 0, 255)

        if result["face_found"]:
            if result["blink_like"]:
                low_ear_streak += 1
            else:
                if low_ear_streak >= EAR_CONSEC_FRAMES:
                    total_blinks += 1
                low_ear_streak = 0

            status_text = f"Face OK | EAR: {result['avg_ear']:.2f} | Blinks: {total_blinks}"
            status_color = (0, 200, 0)

        cv2.putText(frame, status_text, (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, status_color, 2)
        cv2.putText(frame, "Press 'q' to quit", (20, frame.shape[0] - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        cv2.imshow("DeepGuard AI - Feature Extractor", frame)

        if cv2.waitKey(5) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    print(f"Session ended. Total blinks detected: {total_blinks}")


if __name__ == "__main__":
    run_standalone_test()

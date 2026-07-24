"""
ai_engine.py
------------
Covers Step 4 of the build plan: Anti-spoofing / deepfake detection.

Role in the architecture: "The Judge" — pretends to be the Copilot+ PC's NPU in the
laptop simulation. Takes a frame + face bounding box and decides how likely it is
to be a REAL, live human face vs. a printed photo, phone/tablet replay, or deepfake.

IMPORTANT - why this file was rewritten:
An earlier version used a simple image-sharpness heuristic as a placeholder. Real
testing (during hackathon prep) showed this heuristic is NOT reliable: a sharp,
well-lit printed photo or phone screen can score as "more textured" than a real
face under soft webcam lighting, so it can be fooled in both directions. This is
a known limitation of naive sharpness-based liveness checks - detecting real
print/replay attacks needs a model actually TRAINED on spoof vs. real image
patterns (screen moire, print texture, color response, edge artifacts), which a
generic sharpness measurement cannot capture.

This file now integrates a REAL pretrained anti-spoofing model:
    MiniFASNetV2 - based on the Silent-Face-Anti-Spoofing research from
    Minivision AI (https://github.com/minivision-ai/Silent-Face-Anti-Spoofing),
    ONNX-exported and published by yakhyo:
    https://github.com/yakhyo/face-anti-spoofing

HOW TO ADD THE REAL MODEL (do this before your demo):
    1. Download the ONNX weights directly from the GitHub release:
       https://github.com/yakhyo/face-anti-spoofing/releases/download/weights/MiniFASNetV2.onnx
       (Alternative variant: MiniFASNetV1SE.onnx - see README for the tradeoffs)
    2. Save it as: backend/models/antispoof_model.onnx
    3. Restart the backend - it will auto-detect and use it.

Until you add the model file, this falls back to the old sharpness heuristic
so the app still runs end-to-end - but for your actual hackathon demo, you
should use the real model. The heuristic should be treated as "the pipeline
works, plug in the real brain" - not as your final anti-spoofing defense.

The crop and preprocessing logic below exactly follows the reference inference
code published alongside these weights (onnx_inference.py in that repo), so the
model receives input in the same format it was trained/validated on.
"""

import os
import numpy as np
import cv2

MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "antispoof_model.onnx")

# Crop scale factor - how much surrounding context around the tight face box to
# include. This matters a lot for anti-spoofing: too tight a crop misses the
# screen bezel / paper edge / hand-holding-phone context that often gives away
# a spoof attempt. Use 2.7 for MiniFASNetV2 (recommended default), or 4.0 if you
# swap in the MiniFASNetV1SE variant instead.
CROP_SCALE = 2.7

_onnx_session = None
_mode = None  # "model" or "heuristic"
_input_name = None
_output_name = None
_input_size = None  # (height, width), read from the model itself


def _try_load_model():
    global _onnx_session, _mode, _input_name, _output_name, _input_size
    if os.path.exists(MODEL_PATH):
        try:
            import onnxruntime as ort
            _onnx_session = ort.InferenceSession(
                MODEL_PATH, providers=["CPUExecutionProvider"]
            )
            input_cfg = _onnx_session.get_inputs()[0]
            _input_name = input_cfg.name
            _input_size = tuple(input_cfg.shape[2:])  # (H, W)
            _output_name = _onnx_session.get_outputs()[0].name
            _mode = "model"
            print(f"[ai_engine] Loaded real anti-spoofing model from {MODEL_PATH} "
                  f"(input size {_input_size})")
            return
        except Exception as e:
            print(f"[ai_engine] Found model file but failed to load it: {e}")
    _mode = "heuristic"
    print("[ai_engine] No ONNX model found at backend/models/antispoof_model.onnx - "
          "using a WEAK fallback heuristic. Download the real model before your "
          "demo (see ai_engine.py docstring for the link).")


def _crop_face(frame_bgr, bbox_xywh):
    """
    Crops a scaled region around the face box, matching the reference
    implementation's cropping logic exactly (centered, scaled, clipped to
    image bounds, then resized to the model's expected input size).
    """
    src_h, src_w = frame_bgr.shape[:2]
    x, y, box_w, box_h = bbox_xywh

    if box_w <= 0 or box_h <= 0:
        return None

    scale = min((src_h - 1) / box_h, (src_w - 1) / box_w, CROP_SCALE)
    new_w = box_w * scale
    new_h = box_h * scale
    center_x = x + box_w / 2
    center_y = y + box_h / 2

    x1 = max(0, int(center_x - new_w / 2))
    y1 = max(0, int(center_y - new_h / 2))
    x2 = min(src_w - 1, int(center_x + new_w / 2))
    y2 = min(src_h - 1, int(center_y + new_h / 2))

    cropped = frame_bgr[y1:y2 + 1, x1:x2 + 1]
    if cropped.size == 0:
        return None

    target_size = _input_size[::-1] if _input_size else (80, 80)  # (W, H) for cv2.resize
    return cv2.resize(cropped, target_size)


def _preprocess_for_model(face_crop_bgr):
    """
    Matches the reference implementation exactly: NO pixel normalization
    (no /255), just float32 cast, channel-first (CHW), batch dimension added.
    This is unusual (most vision models normalize to 0-1) but matches how this
    specific model was trained - changing this will silently break predictions.
    """
    face = face_crop_bgr.astype(np.float32)
    face = np.transpose(face, (2, 0, 1))  # HWC -> CHW
    face = np.expand_dims(face, axis=0)   # add batch dimension
    return face


def _softmax(x):
    e_x = np.exp(x - np.max(x, axis=1, keepdims=True))
    return e_x / e_x.sum(axis=1, keepdims=True)


def _predict_with_model(frame_bgr, bbox_xywh):
    face_crop = _crop_face(frame_bgr, bbox_xywh)
    if face_crop is None:
        return 0.0

    input_tensor = _preprocess_for_model(face_crop)
    outputs = _onnx_session.run([_output_name], {_input_name: input_tensor})
    logits = outputs[0]
    probs = _softmax(logits)

    # NOTE: per the reference implementation this model ships with, index 1
    # corresponds to "Real". If you swap in a different exported model with a
    # different class ordering, verify this against that model's own docs/code.
    real_prob = float(probs[0, 1])
    return real_prob


def _predict_with_heuristic(frame_bgr, bbox_xywh):
    """
    WEAK fallback signal - texture/sharpness based, used only when no real
    model file is present. See this file's module docstring for why this is
    not a reliable anti-spoofing defense on its own.
    """
    x, y, w, h = bbox_xywh
    crop = frame_bgr[max(0, y):y + h, max(0, x):x + w]
    if crop.size == 0:
        return 0.0

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

    LOW_VARIANCE = 15.0
    HIGH_VARIANCE = 60.0

    if laplacian_var <= LOW_VARIANCE:
        real_prob = 0.15
    elif laplacian_var >= HIGH_VARIANCE:
        real_prob = 0.92
    else:
        span = HIGH_VARIANCE - LOW_VARIANCE
        real_prob = 0.15 + 0.77 * ((laplacian_var - LOW_VARIANCE) / span)

    return float(np.clip(real_prob, 0.0, 1.0))


def get_spoof_score(frame_bgr, bbox_xywh):
    """
    Main entry point used by dashboard.py.

    Input:
        frame_bgr: the full captured frame (BGR numpy array)
        bbox_xywh: tight face bounding box (x, y, w, h) from
                   feature_extractor.process_frame()'s "face_bbox_xywh" field
    Output: a float between 0.0 and 1.0 - probability the face is REAL
            (higher = more likely a genuine live human).
    """
    if frame_bgr is None or bbox_xywh is None:
        return 0.0

    global _mode
    if _mode is None:
        _try_load_model()

    if _mode == "model":
        try:
            return _predict_with_model(frame_bgr, bbox_xywh)
        except Exception as e:
            print(f"[ai_engine] Model inference failed, falling back to heuristic: {e}")
            return _predict_with_heuristic(frame_bgr, bbox_xywh)
    else:
        return _predict_with_heuristic(frame_bgr, bbox_xywh)


if __name__ == "__main__":
    # Standalone test: point this at a saved image file. Runs the full
    # landmark-detection + spoof-scoring pipeline on it, without needing the
    # webcam or FastAPI running.
    import sys
    import feature_extractor

    if len(sys.argv) != 2:
        print("Usage: python ai_engine.py <path_to_face_image.jpg>")
        sys.exit(1)

    img = cv2.imread(sys.argv[1])
    if img is None:
        print(f"Could not read image at {sys.argv[1]}")
        sys.exit(1)

    result = feature_extractor.process_frame(img)
    if not result["face_found"]:
        print("No face detected in the image.")
        sys.exit(1)

    score = get_spoof_score(img, result["face_bbox_xywh"])
    print(f"Mode: {_mode}")
    print(f"Real-face probability: {score:.2f}")
    print("=> REAL" if score >= 0.5 else "=> FAKE / SPOOF SUSPECTED")

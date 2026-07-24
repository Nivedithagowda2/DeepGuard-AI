"""
risk_engine.py
--------------
Covers Step 5 of the build plan: Risk scoring.

Role in the architecture: takes liveness signals gathered across a multi-second
recording window - a genuine blink transition, real head-turn movement, and an
averaged anti-spoofing score - and combines them into one risk score and a
VERIFIED / HIGH RISK status.

IMPORTANT DESIGN NOTE (fixed after real-world testing):
An earlier version of this system made decisions from a SINGLE photo snapshot.
That allowed a printed photo with downcast/half-closed eyes to be misread as a
"blink" (a low EAR reading in one frame), incorrectly passing verification.

The fix: liveness signals are now computed from a SEQUENCE of frames captured
over ~3 seconds (see feature_extractor.detect_blink_transition), so a genuine
open->closed->open eye cycle is required - something a static photo physically
cannot produce - and real head movement is tracked the same way.

Deliberately rule-based (no ML here) so it's transparent, fast, and easy to
explain and tune live during the hackathon.
"""

# Tune these weights based on real testing with your own webcam and test attacks.
SPOOF_WEIGHT = 60           # weight given to a low average spoof-real-score
NO_BLINK_WEIGHT = 25        # weight given to never completing a real blink cycle
NO_HEAD_MOVEMENT_WEIGHT = 15  # weight given to no detected head-turn movement

SPOOF_REAL_THRESHOLD = 0.5    # below this average real-probability -> suspicious
RISK_HIGH_THRESHOLD = 50      # risk_score >= this -> HIGH RISK


def calculate_risk(avg_spoof_real_prob, blink_transition_detected, head_moved):
    """
    Inputs:
        avg_spoof_real_prob (float 0-1): average of ai_engine.get_spoof_score()
            across every frame in the recording window
        blink_transition_detected (bool): True only if a genuine open->closed->open
            eye cycle was observed across the recording (see detect_blink_transition)
        head_moved (bool): True if the nose position moved enough across the
            recording window to indicate real head turning, not a static image

    Returns a dict:
        {
            "risk_score": int (0-100),
            "status": "VERIFIED" | "HIGH RISK",
            "reasons": [list of strings explaining the score]
        }
    """
    risk_score = 0
    reasons = []

    if avg_spoof_real_prob < SPOOF_REAL_THRESHOLD:
        risk_score += SPOOF_WEIGHT
        reasons.append(f"Low average real-face confidence ({avg_spoof_real_prob:.2f})")

    if not blink_transition_detected:
        risk_score += NO_BLINK_WEIGHT
        reasons.append("No genuine blink cycle detected (eyes never fully reopened)")

    if not head_moved:
        risk_score += NO_HEAD_MOVEMENT_WEIGHT
        reasons.append("No natural head movement detected")

    risk_score = min(risk_score, 100)
    status = "HIGH RISK" if risk_score >= RISK_HIGH_THRESHOLD else "VERIFIED"

    if not reasons:
        reasons.append("All liveness checks passed")

    return {
        "risk_score": risk_score,
        "status": status,
        "reasons": reasons,
    }


if __name__ == "__main__":
    # Standalone tests - run `python risk_engine.py` to sanity-check the logic
    # with hand-picked sample values, without needing the webcam or AI model.
    test_cases = [
        {
            "label": "Real face: blinked, turned head, high spoof-real confidence",
            "avg_spoof_real_prob": 0.91,
            "blink_transition_detected": True,
            "head_moved": True,
        },
        {
            "label": "Printed photo: eyes downcast the whole time (the bug we fixed)",
            "avg_spoof_real_prob": 0.20,
            "blink_transition_detected": False,   # never re-opens -> correctly False
            "head_moved": False,
        },
        {
            "label": "Phone replay: video blinks naturally but spoof model catches texture",
            "avg_spoof_real_prob": 0.25,
            "blink_transition_detected": True,
            "head_moved": True,
        },
        {
            "label": "Real face: sat still and didn't blink during the window",
            "avg_spoof_real_prob": 0.88,
            "blink_transition_detected": False,
            "head_moved": False,
        },
    ]

    for case in test_cases:
        label = case.pop("label")
        result = calculate_risk(**case)
        print(f"\n{label}")
        print(f"  -> risk_score={result['risk_score']}, status={result['status']}")
        print(f"  -> reasons: {', '.join(result['reasons'])}")

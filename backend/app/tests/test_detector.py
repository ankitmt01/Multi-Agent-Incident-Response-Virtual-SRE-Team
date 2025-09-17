# backend/app/tests/test_detector.py
from app.detectors.detector import normalize, infer_severity

def test_normalize_units():
    sigs = [
        {"name": "5xx_rate", "value": 0.02, "unit": "", "window_s": 60},  # ratio -> should stay 0.02 (treated as %? we keep raw but MED rules use %)
        {"name": "latency_p95", "value": 1.2, "unit": "s", "window_s": 60},
        {"name": "latency_p95_ms", "value": 900, "unit": "ms", "window_s": 60},
    ]
    out = normalize(sigs)
    # latency in ms
    p95_ms = [s for s in out if s["name"].lower().startswith("latency")][0]["value"]
    assert 1199 <= p95_ms <= 1201  # ~1.2s -> 1200ms

def test_severity_low():
    sigs = [
        {"name": "5xx_rate", "value": 0.2, "unit": "%", "window_s": 60},
        {"name": "latency_p95_ms", "value": 600, "unit": "ms", "window_s": 60},
    ]
    assert infer_severity(sigs) == "LOW"

def test_severity_medium_by_error():
    sigs = [
        {"name": "5xx_rate", "value": 0.7, "unit": "%", "window_s": 60},
        {"name": "latency_p95_ms", "value": 600, "unit": "ms", "window_s": 60},
    ]
    assert infer_severity(sigs) == "MEDIUM"

def test_severity_medium_by_latency():
    sigs = [
        {"name": "5xx_rate", "value": 0.1, "unit": "%", "window_s": 60},
        {"name": "latency_p95_ms", "value": 900, "unit": "ms", "window_s": 60},
    ]
    assert infer_severity(sigs) == "MEDIUM"

def test_severity_high_joint():
    sigs = [
        {"name": "5xx_rate", "value": 1.2, "unit": "%", "window_s": 60},
        {"name": "latency_p95_ms", "value": 1100, "unit": "ms", "window_s": 60},
    ]
    assert infer_severity(sigs) == "HIGH"

def test_severity_high_extreme_single():
    # Extreme error OR extreme latency should trigger HIGH
    sigs1 = [{"name":"5xx_rate","value": 2.5, "unit":"%", "window_s":60}]
    sigs2 = [{"name":"latency_p95_ms","value": 1600, "unit":"ms", "window_s":60}]
    assert infer_severity(sigs1) == "HIGH"
    assert infer_severity(sigs2) == "HIGH"

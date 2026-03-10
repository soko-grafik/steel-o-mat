from __future__ import annotations
import numpy as np
try:
    import cv2
except ImportError:
    cv2 = None
try:
    import pytesseract
except ImportError:  # optional dependency
    pytesseract = None

def _segment_centers(mask: np.ndarray) -> list[tuple[float, float]]:
    if cv2 is None:
        return []
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    centers: list[tuple[float, float]] = []
    for contour in contours:
        if cv2.contourArea(contour) < 30:
            continue
        moments = cv2.moments(contour)
        if moments["m00"] == 0:
            continue
        centers.append((moments["m10"] / moments["m00"], moments["m01"] / moments["m00"]))
    return centers


def _detect_twenty_vector(frame: np.ndarray, center: tuple[float, float], radius_est: float) -> np.ndarray | None:
    """
    Tries to locate the number '20' on the board using OCR.
    Returns a normalized vector from board center towards the center of the "20" label.
    """
    if pytesseract is None:
        return None

    try:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) if cv2 is not None else frame
        ocr = pytesseract.image_to_data(
            rgb,
            output_type=pytesseract.Output.DICT,
            config="--psm 11 -c tessedit_char_whitelist=0123456789",
        )
    except Exception:
        return None

    best_vec = None
    best_score = -1.0
    cx, cy = center
    lower_r = radius_est * 0.65
    upper_r = radius_est * 1.45

    for idx, text in enumerate(ocr.get("text", [])):
        token = str(text).strip()
        if token != "20":
            continue

        x = float(ocr["left"][idx] + ocr["width"][idx] / 2.0)
        y = float(ocr["top"][idx] + ocr["height"][idx] / 2.0)
        vec = np.array([x - cx, y - cy], dtype=float)
        dist = np.linalg.norm(vec)
        if dist < 1e-6:
            continue
        if not (lower_r <= dist <= upper_r):
            continue

        confidence = float(ocr.get("conf", ["0"])[idx] or 0.0)
        score = confidence - abs(dist - radius_est)
        if score > best_score:
            best_score = score
            best_vec = vec / dist

    return best_vec


def _detect_reference_vector_template(frame: np.ndarray, center: tuple[float, float], radius_est: float) -> tuple[np.ndarray, str, float] | None:
    """
    Fallback without OCR engine:
    scans the number ring with a rotated patch and matches synthetic templates for
    20 / 11 / 6 / 3. Returns the inferred "20-up" vector plus matched label.
    """
    if cv2 is None:
        return None

    h, w = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    # Synthetic templates (white digits on dark background), edge-based matching.
    templates: dict[str, np.ndarray] = {}
    for label, font_scale, thickness in [("20", 1.1, 2), ("11", 1.1, 2), ("6", 1.2, 2), ("3", 1.2, 2)]:
        tmpl = np.zeros((48, 96), dtype=np.uint8)
        text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)[0]
        tx = max(2, (tmpl.shape[1] - text_size[0]) // 2)
        ty = max(text_size[1] + 2, (tmpl.shape[0] + text_size[1]) // 2 - 2)
        cv2.putText(tmpl, label, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, font_scale, 255, thickness, cv2.LINE_AA)
        templates[label] = cv2.Canny(tmpl, 40, 120)

    cx, cy = center
    ring_r = radius_est * 1.1
    patch_w, patch_h = 190, 112
    best_score = -1.0
    best_angle = None
    best_label = None

    for ring_factor in [1.0, 1.08, 1.16, 1.24]:
        ring_r = radius_est * ring_factor
        for angle_deg in range(0, 360, 2):
            angle = np.deg2rad(angle_deg)
            px = cx + np.cos(angle) * ring_r
            py = cy + np.sin(angle) * ring_r
            if px < 0 or py < 0 or px >= w or py >= h:
                continue

            # Rotate local tangent near the number ring to horizontal.
            tangent_deg = angle_deg + 90.0
            rot = cv2.getRotationMatrix2D((float(px), float(py)), -tangent_deg, 1.0)
            rotated = cv2.warpAffine(gray, rot, (w, h))

            x0 = int(px - patch_w // 2)
            y0 = int(py - patch_h // 2)
            x1 = x0 + patch_w
            y1 = y0 + patch_h
            if x0 < 0 or y0 < 0 or x1 > w or y1 > h:
                continue
            patch = rotated[y0:y1, x0:x1]
            patch_edges = cv2.Canny(patch, 40, 120)

            for label, template_edges in templates.items():
                for scale in [0.85, 1.0, 1.15, 1.3]:
                    tw = max(8, int(template_edges.shape[1] * scale))
                    th = max(8, int(template_edges.shape[0] * scale))
                    scaled = cv2.resize(template_edges, (tw, th), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
                    if patch_edges.shape[0] < th or patch_edges.shape[1] < tw:
                        continue
                    result = cv2.matchTemplate(patch_edges, scaled, cv2.TM_CCOEFF_NORMED)
                    _, score, _, _ = cv2.minMaxLoc(result)
                    score = float(score)
                    if score > best_score:
                        best_score = score
                        best_angle = angle
                        best_label = label

    if best_angle is None or best_label is None or best_score < 0.13:
        return None

    # Offsets in clockwise degrees from 20 to the label's sector center.
    offset_from_20 = {
        "20": 0.0,
        "6": 90.0,
        "3": 180.0,
        "11": 270.0,
    }[best_label]
    angle_20 = best_angle - np.deg2rad(offset_from_20)
    vec = np.array([np.cos(angle_20), np.sin(angle_20)], dtype=float)
    norm = np.linalg.norm(vec)
    if norm <= 1e-6:
        return None
    return vec / norm, best_label, best_score


def _tesseract_available() -> bool:
    if pytesseract is None:
        return False
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def detect_dartboard(frame: np.ndarray) -> dict[str, object] | None:
    """
    Detects the 4 calibration points automatically.
    Returns calibration result:
    - points: 4 image points (Top, Right, Bottom, Left)
    - orientation_source: "ocr_20" | "fallback_top_segment"
    - warning: optional warning string
    """
    if cv2 is None or frame is None:
        return None

    h, w = frame.shape[:2]
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    
    # Red mask (Double ranges)
    mask_red1 = cv2.inRange(hsv, np.array([0, 120, 100]), np.array([10, 255, 255]))
    mask_red2 = cv2.inRange(hsv, np.array([160, 120, 100]), np.array([180, 255, 255]))
    mask_red = cv2.bitwise_or(mask_red1, mask_red2)
    
    # Green mask
    mask_green = cv2.inRange(hsv, np.array([40, 60, 60]), np.array([85, 255, 255]))
    
    # Rings mask for ellipse fitting
    mask_rings = cv2.bitwise_or(mask_red, mask_green)
    kernel = np.ones((5, 5), np.uint8)
    mask_rings = cv2.morphologyEx(mask_rings, cv2.MORPH_CLOSE, kernel)
    
    contours, _ = cv2.findContours(mask_rings, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = [cnt for cnt in contours if cv2.contourArea(cnt) > 100]
    if not candidates:
        return None
        
    all_pts = np.vstack(candidates)
    if len(all_pts) < 5:
        return None
    
    ellipse = cv2.fitEllipse(all_pts)
    center, axes, angle = ellipse
    radius_est = max(axes) / 2
    
    # Find centers of segments to get general board orientation
    red_segs = _segment_centers(mask_red)
    green_segs = _segment_centers(mask_green)
    
    if not red_segs or not green_segs:
        return None
        
    p_top_mid = min(red_segs, key=lambda p: p[1])
    vec_up = np.array([p_top_mid[0] - center[0], p_top_mid[1] - center[1]])
    norm = np.linalg.norm(vec_up)
    if norm <= 1e-6:
        return None
    vec_up = vec_up / norm

    # Prefer OCR-based 20 detection to orient overlay/calibration to the real "20" label.
    vec_twenty = _detect_twenty_vector(frame, (float(center[0]), float(center[1])), float(radius_est))
    orientation_source = "fallback_top_segment"
    orientation_score = 0.0
    warning = None
    if vec_twenty is not None:
        vec_up = vec_twenty
        orientation_source = "ocr_20"
        orientation_score = 1.0
    else:
        template_result = _detect_reference_vector_template(frame, (float(center[0]), float(center[1])), float(radius_est))
        if template_result is not None:
            vec_twenty_template, matched_label, match_score = template_result
            vec_up = vec_twenty_template
            orientation_source = f"template_{matched_label}"
            orientation_score = float(match_score)
            warning = f"Template orientation via {matched_label} (score={match_score:.2f})."

    if orientation_source == "fallback_top_segment":
        if not _tesseract_available():
            warning = "Tesseract OCR not available and template matching did not find 20; orientation may be wrong if board is rotated."
        else:
            warning = "OCR/template could not find number 20; orientation may be wrong if board is rotated."
    
    # Angular step for the "Right" corner (9 degrees = pi/20 rad)
    phi = np.pi / 20.0
    
    def get_corner(base_vec, angle_offset):
        # Rotate base vector by angle_offset to find the wire direction
        c, s = np.cos(angle_offset), np.sin(angle_offset)
        # Image coordinates: y is down, so clockwise rotation is [c -s; s c]
        wire_vec = np.array([
            base_vec[0] * c - base_vec[1] * s,
            base_vec[0] * s + base_vec[1] * c
        ])
        
        # Search for the furthest mask pixel along this wire
        best_p = (center[0] + wire_vec[0] * radius_est, center[1] + wire_vec[1] * radius_est)
        max_d = 0
        for r in np.linspace(radius_est * 0.8, radius_est * 1.15, 30):
            px, py = int(center[0] + wire_vec[0] * r), int(center[1] + wire_vec[1] * r)
            if 0 <= px < w and 0 <= py < h:
                if mask_rings[py, px] > 0:
                    d = np.sqrt((px-center[0])**2 + (py-center[1])**2)
                    if d > max_d:
                        max_d = d
                        best_p = (float(px), float(py))
        return best_p

    # Points for: Top (D20-D1), Right (D6-D13), Bottom (D3-D19), Left (D11-D14)
    # Clockwise rotation in image space (y-down) is positive angle offset
    p_top = get_corner(vec_up, phi)
    
    vec_right = np.array([-vec_up[1], vec_up[0]])
    p_right = get_corner(vec_right, phi)
    
    p_bottom = get_corner(-vec_up, phi)
    
    vec_left = np.array([vec_up[1], -vec_up[0]])
    p_left = get_corner(vec_left, phi)
    
    return {
        "points": [
            [float(p_top[0]), float(p_top[1])],
            [float(p_right[0]), float(p_right[1])],
            [float(p_bottom[0]), float(p_bottom[1])],
            [float(p_left[0]), float(p_left[1])],
        ],
        "orientation_source": orientation_source,
        "orientation_score": orientation_score,
        "warning": warning,
    }

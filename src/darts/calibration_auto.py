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
    Tries to locate numbers on the board using OCR on cropped patches.
    """
    if pytesseract is None or cv2 is None:
        return None

    h, w = frame.shape[:2]
    cx, cy = center
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # We scan around the number ring
    patch_w = int(radius_est * 0.45)
    patch_h = int(radius_est * 0.28)
    
    votes_x = 0.0
    votes_y = 0.0
    total_weight = 0.0

    label_offsets_deg = {
        "20": 0.0, "1": 18.0, "18": 36.0, "4": 54.0, "13": 72.0, "6": 90.0,
        "10": 108.0, "15": 126.0, "2": 144.0, "17": 162.0, "3": 180.0,
        "19": 198.0, "7": 216.0, "16": 234.0, "8": 252.0, "11": 270.0,
        "14": 288.0, "9": 306.0, "12": 324.0, "5": 342.0
    }

    # Step through radii and angles to find numbers
    for ring_factor in [1.10, 1.20, 1.30]:
        ring_r = radius_est * ring_factor
        for angle_deg in range(0, 360, 18):
            angle = np.deg2rad(angle_deg)
            px = cx + np.cos(angle) * ring_r
            py = cy + np.sin(angle) * ring_r
            
            if px < 0 or py < 0 or px >= w or py >= h:
                continue
                
            # Rotate patch to be upright for Tesseract
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
            # Pre-process patch with adaptive threshold for better OCR
            patch = cv2.adaptiveThreshold(
                patch, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
            )
            
            try:
                # PSM 7: Treat the image as a single text line.
                text = pytesseract.image_to_string(
                    patch, 
                    config="--psm 7 -c tessedit_char_whitelist=0123456789"
                ).strip()
            
                if text in label_offsets_deg:
                    offset_rad = np.deg2rad(label_offsets_deg[text])
                    angle_20 = angle - offset_rad
                    
                    weight = 2.0 if text == "20" else 1.0
                    votes_x += np.cos(angle_20) * weight
                    votes_y += np.sin(angle_20) * weight
                    total_weight += weight
            except Exception:
                continue

    if total_weight < 0.5:
        # Fallback to the original full-frame OCR if patches failed
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            ocr = pytesseract.image_to_data(
                rgb,
                output_type=pytesseract.Output.DICT,
                config="--psm 11 -c tessedit_char_whitelist=0123456789",
            )
            
            best_vec = None
            best_score = -1.0
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
                if not (lower_r <= dist <= upper_r):
                    continue
                confidence = float(ocr.get("conf", ["0"])[idx] or 0.0)
                score = confidence - abs(dist - radius_est)
                if score > best_score:
                    best_score = score
                    best_vec = vec / dist
            return best_vec
        except Exception:
            return None

    avg_angle = np.arctan2(votes_y, votes_x)
    return np.array([np.cos(avg_angle), np.sin(avg_angle)], dtype=float)


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
    for label, font_scale, thickness in [
        ("20", 1.1, 2), ("1", 1.2, 2), ("5", 1.2, 2),
        ("11", 1.1, 2), ("6", 1.2, 2), ("3", 1.2, 2)
    ]:
        tmpl = np.zeros((48, 96), dtype=np.uint8)
        text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)[0]
        tx = max(2, (tmpl.shape[1] - text_size[0]) // 2)
        ty = max(text_size[1] + 2, (tmpl.shape[0] + text_size[1]) // 2 - 2)
        cv2.putText(tmpl, label, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, font_scale, 255, thickness, cv2.LINE_AA)
        templates[label] = cv2.Canny(tmpl, 40, 120)

    cx, cy = center
    ring_r = radius_est * 1.12
    # patch size relative to radius
    patch_w = int(radius_est * 0.45)
    patch_h = int(radius_est * 0.28)
    
    # Collect multiple candidates for consensus
    candidates: list[dict[str, object]] = []

    for ring_factor in [1.02, 1.10, 1.18, 1.26, 1.34]:
        ring_r = radius_est * ring_factor
        for angle_deg in range(0, 360, 3):
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
            patch_edges = cv2.Canny(patch, 30, 100)

            for label, template_edges in templates.items():
                target_h = radius_est * 0.09
                scale_base = target_h / template_edges.shape[0]
                
                for scale_mult in [0.85, 1.0, 1.15]:
                    scale = scale_base * scale_mult
                    tw = max(10, int(template_edges.shape[1] * scale))
                    th = max(10, int(template_edges.shape[0] * scale))
                    if patch_edges.shape[0] < th or patch_edges.shape[1] < tw:
                        continue
                    scaled = cv2.resize(template_edges, (tw, th), interpolation=cv2.INTER_LINEAR)
                    result = cv2.matchTemplate(patch_edges, scaled, cv2.TM_CCOEFF_NORMED)
                    _, score, _, _ = cv2.minMaxLoc(result)
                    score = float(score)
                    if score > 0.12:
                        candidates.append({
                            "label": label,
                            "angle": angle,
                            "score": score
                        })

    if not candidates:
        return None

    # Offsets in clockwise degrees from 20 to the label's sector center.
    label_offsets_deg = {
        "20": 0.0,
        "1": 18.0,
        "5": -18.0,
        "6": 90.0,
        "3": 180.0,
        "11": 270.0,
    }

    # Vote for the "20-up" vector
    votes_x = 0.0
    votes_y = 0.0
    total_weight = 0.0
    
    best_label = "unknown"
    best_score = 0.0

    for cand in candidates:
        label = str(cand["label"])
        angle = float(cand["angle"])
        score = float(cand["score"])
        
        if score > best_score:
            best_score = score
            best_label = label
            
        offset_rad = np.deg2rad(label_offsets_deg.get(label, 0.0))
        angle_20 = angle - offset_rad
        
        # Weight by score and label importance (20 is most important)
        weight = score * (1.5 if label == "20" else 1.0)
        votes_x += np.cos(angle_20) * weight
        votes_y += np.sin(angle_20) * weight
        total_weight += weight

    if total_weight < 0.2:
        return None

    avg_angle = np.arctan2(votes_y, votes_x)
    vec = np.array([np.cos(avg_angle), np.sin(avg_angle)], dtype=float)
    return vec, best_label, best_score / total_weight if total_weight > 0 else best_score


def _angle_distance_deg(a: float, b: float) -> float:
    diff = (a - b + 180.0) % 360.0 - 180.0
    return abs(diff)


def _detect_spider_wire_angles(frame: np.ndarray, center: tuple[float, float], radius_est: float) -> list[float]:
    """
    Detect candidate spider wire ray angles (radians, image coordinate system).
    Returns up to 20 ray angles in [0, 2*pi), clockwise order preserved.
    """
    if cv2 is None:
        return []

    h, w = frame.shape[:2]
    cx, cy = center
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, 45, 130)

    min_len = max(15, int(radius_est * 0.22))
    max_gap = max(8, int(radius_est * 0.10))
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180.0,
        threshold=40,
        minLineLength=min_len,
        maxLineGap=max_gap,
    )
    if lines is None:
        return []

    candidate_angles_deg_mod_180: list[float] = []
    for entry in lines[:, 0]:
        x1, y1, x2, y2 = map(float, entry)
        dx = x2 - x1
        dy = y2 - y1
        length = float(np.hypot(dx, dy))
        if length < min_len:
            continue

        # Keep only lines that are close to board center (radial wire candidates).
        line_dist = abs((dy * cx) - (dx * cy) + (x2 * y1) - (y2 * x1)) / max(length, 1e-6)
        if line_dist > radius_est * 0.08:
            continue

        mid_x = (x1 + x2) * 0.5
        mid_y = (y1 + y2) * 0.5
        mid_r = float(np.hypot(mid_x - cx, mid_y - cy))
        if not (radius_est * 0.18 <= mid_r <= radius_est * 1.08):
            continue

        angle_deg = (np.degrees(np.arctan2(dy, dx)) + 360.0) % 180.0
        candidate_angles_deg_mod_180.append(float(angle_deg))

    if len(candidate_angles_deg_mod_180) < 8:
        return []

    # Build a circular histogram over [0, 180) to find dominant line orientations
    # without assuming constant angular spacing in image space.
    hist = np.zeros(180, dtype=float)
    for angle_deg in candidate_angles_deg_mod_180:
        hist[int(round(angle_deg)) % 180] += 1.0

    kernel = np.array([1.0, 2.0, 3.0, 2.0, 1.0], dtype=float)
    smooth = np.zeros_like(hist)
    for i in range(180):
        for k, value in enumerate(kernel):
            smooth[i] += value * hist[(i + k - 2) % 180]

    peak_indices = np.argsort(smooth)[::-1]
    selected_peaks: list[int] = []
    min_sep_deg = 6
    for idx in peak_indices:
        if smooth[idx] <= 0:
            break
        if all(min(abs(idx - p), 180 - abs(idx - p)) >= min_sep_deg for p in selected_peaks):
            selected_peaks.append(int(idx))
        if len(selected_peaks) >= 10:
            break

    if len(selected_peaks) < 6:
        return []

    # Refine each peak with local weighted mean.
    refined_line_angles_deg: list[float] = []
    window_deg = 4.0
    for peak in selected_peaks:
        weights = []
        values = []
        for observed in candidate_angles_deg_mod_180:
            delta = min(abs(observed - peak), 180.0 - abs(observed - peak))
            if delta <= window_deg:
                weight = 1.0 - (delta / window_deg)
                weights.append(weight)
                values.append(observed)
        if not weights:
            refined_line_angles_deg.append(float(peak))
            continue
        # Circular mean modulo 180°
        angles2 = np.deg2rad(np.array(values) * 2.0)
        x = float(np.sum(np.cos(angles2) * np.array(weights)))
        y = float(np.sum(np.sin(angles2) * np.array(weights)))
        mean2 = np.arctan2(y, x)
        mean_deg = (np.rad2deg(mean2) * 0.5) % 180.0
        refined_line_angles_deg.append(float(mean_deg))

    ray_angles_deg: list[float] = []
    for line_angle in refined_line_angles_deg:
        ray_angles_deg.append(line_angle % 360.0)
        ray_angles_deg.append((line_angle + 180.0) % 360.0)

    ray_angles_deg = sorted(ray_angles_deg)
    return [float(np.deg2rad(deg)) for deg in ray_angles_deg]


def _snap_wire_angle(target_angle_rad: float, wire_angles: list[float], max_error_deg: float = 10.0) -> float:
    if not wire_angles:
        return target_angle_rad
    target_deg = (np.degrees(target_angle_rad) + 360.0) % 360.0
    best = target_deg
    best_err = 360.0
    for wire in wire_angles:
        wire_deg = (np.degrees(wire) + 360.0) % 360.0
        err = _angle_distance_deg(target_deg, wire_deg)
        if err < best_err:
            best = wire_deg
            best_err = err
    if best_err <= max_error_deg:
        return float(np.deg2rad(best))
    return target_angle_rad


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
    mask_red1 = cv2.inRange(hsv, np.array([0, 70, 50]), np.array([10, 255, 255]))
    mask_red2 = cv2.inRange(hsv, np.array([160, 70, 50]), np.array([180, 255, 255]))
    mask_red = cv2.bitwise_or(mask_red1, mask_red2)
    
    # Green mask
    mask_green = cv2.inRange(hsv, np.array([35, 45, 45]), np.array([90, 255, 255]))
    
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
    
    # Initial fit to get estimate for outlier removal
    ellipse = cv2.fitEllipse(all_pts)
    center, axes, angle = ellipse
    radius_est = max(axes) / 2
    
    # Filter points that are too far from the estimated rings
    filtered_pts = []
    for pt in all_pts:
        dist = np.hypot(pt[0][0] - center[0], pt[0][1] - center[1])
        if radius_est * 0.4 <= dist <= radius_est * 1.15:
            filtered_pts.append(pt)
            
    if len(filtered_pts) < 5:
        return None
        
    ellipse = cv2.fitEllipse(np.array(filtered_pts))
    center, axes, angle = ellipse
    radius_est = max(axes) / 2
    
    # Find centers of segments to get general board orientation
    red_segs = _segment_centers(mask_red)
    green_segs = _segment_centers(mask_green)
    
    # Filter segments by distance from center to remove noise
    def filter_segs(segs):
        return [
            p for p in segs 
            if radius_est * 0.5 <= np.hypot(p[0] - center[0], p[1] - center[1]) <= radius_est * 1.15
        ]
    
    red_segs = filter_segs(red_segs)
    green_segs = filter_segs(green_segs)
    
    if not red_segs or not green_segs:
        return None
        
    # Find the red segment that is most "up" (closest to 12 o'clock)
    # If the board is upside down, we might need to rely more on OCR/Template.
    # Fallback: assume the 20 is the red segment closest to the top of the image.
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

    # If OCR/Template found 20 at the bottom, vec_up now points down. 
    # This is correct for upside-down boards.
    
    if orientation_source == "fallback_top_segment":
        # Check if any detected wire angles suggest a 180 flip? 
        # (Hard to tell without numbers).
        if not _tesseract_available():
            warning = "OCR not available. Orientation assumes 20 is at the top."
        else:
            warning = "OCR could not find numbers. Orientation assumes 20 is at the top."
    
    # Angular step for the "Right" corner (9 degrees = pi/20 rad)
    phi = np.pi / 20.0

    detected_wire_angles = _detect_spider_wire_angles(frame, (float(center[0]), float(center[1])), float(radius_est))

    ellipse_center = np.array([float(center[0]), float(center[1])], dtype=float)
    axis_a = max(float(axes[0]) * 0.5, 1e-6)
    axis_b = max(float(axes[1]) * 0.5, 1e-6)
    ellipse_theta = float(np.deg2rad(angle))
    cos_t = float(np.cos(ellipse_theta))
    sin_t = float(np.sin(ellipse_theta))

    def get_corner(wire_angle_rad: float):
        snapped_angle = _snap_wire_angle(wire_angle_rad, detected_wire_angles)
        wire_vec = np.array([np.cos(snapped_angle), np.sin(snapped_angle)], dtype=float)

        # Exact ray/ellipse intersection at the fitted outer double ring.
        # Convert direction into ellipse-local coordinates.
        dir_local_x = cos_t * wire_vec[0] + sin_t * wire_vec[1]
        dir_local_y = -sin_t * wire_vec[0] + cos_t * wire_vec[1]
        denom = (dir_local_x * dir_local_x) / (axis_a * axis_a) + (dir_local_y * dir_local_y) / (axis_b * axis_b)

        if denom > 1e-12:
            t = 1.0 / np.sqrt(denom)
            point = ellipse_center + wire_vec * float(t)
            px = float(np.clip(point[0], 0, w - 1))
            py = float(np.clip(point[1], 0, h - 1))
            return (px, py)

        # Fallback: old scan method if numerical issues occur.
        best_p = (center[0] + wire_vec[0] * radius_est, center[1] + wire_vec[1] * radius_est)
        max_d = 0.0
        for r in np.linspace(radius_est * 0.8, radius_est * 1.15, 30):
            px_i = int(center[0] + wire_vec[0] * r)
            py_i = int(center[1] + wire_vec[1] * r)
            if 0 <= px_i < w and 0 <= py_i < h and mask_rings[py_i, px_i] > 0:
                d = float(np.hypot(px_i - center[0], py_i - center[1]))
                if d > max_d:
                    max_d = d
                    best_p = (float(px_i), float(py_i))
        return best_p

    # Points for: Top (D20-D1), Right (D6-D13), Bottom (D3-D19), Left (D11-D14)
    # Clockwise rotation in image space (y-down) is positive angle offset
    angle_up = float(np.arctan2(vec_up[1], vec_up[0]))
    top_boundary_target = (angle_up + phi) % (2.0 * np.pi)

    # Prefer ordering along detected rays (projective-safe). Fallback to 90° rotations.
    if 16 <= len(detected_wire_angles) <= 24:
        ray_degrees = sorted((np.degrees(a) + 360.0) % 360.0 for a in detected_wire_angles)
        snapped_top = _snap_wire_angle(top_boundary_target, detected_wire_angles)
        snapped_top_deg = (np.degrees(snapped_top) + 360.0) % 360.0

        nearest_top_index = min(
            range(len(ray_degrees)),
            key=lambda i: _angle_distance_deg(ray_degrees[i], snapped_top_deg),
        )

        # Estimate segment count between rays to pick the right ones even if some are missing
        def get_ray_at_offset(start_idx, offset_deg):
            target = (ray_degrees[start_idx] + offset_deg) % 360.0
            best_idx = min(range(len(ray_degrees)), key=lambda i: _angle_distance_deg(ray_degrees[i], target))
            # If the closest ray is too far from expected 90/180/270 offset, fallback to calculation
            if _angle_distance_deg(ray_degrees[best_idx], target) > 10.0:
                return np.deg2rad(target)
            return np.deg2rad(ray_degrees[best_idx])

        top_angle = np.deg2rad(ray_degrees[nearest_top_index])
        right_angle = get_ray_at_offset(nearest_top_index, 90.0)
        bottom_angle = get_ray_at_offset(nearest_top_index, 180.0)
        left_angle = get_ray_at_offset(nearest_top_index, 270.0)
    else:
        top_angle = top_boundary_target
        right_angle = angle_up + np.pi / 2.0 + phi
        bottom_angle = angle_up + np.pi + phi
        left_angle = angle_up - np.pi / 2.0 + phi

    p_top = get_corner(float(top_angle))
    p_right = get_corner(float(right_angle))
    p_bottom = get_corner(float(bottom_angle))
    p_left = get_corner(float(left_angle))
    
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


def _estimate_twenty_angle_deg(points: list[list[float]]) -> float | None:
    if len(points) != 4:
        return None
    arr = np.array(points, dtype=float)
    if arr.shape != (4, 2):
        return None
    center = np.mean(arr, axis=0)
    # arr[0] is p_top (intersection at 20/1 wire), which is 9 degrees clockwise from 20-center.
    vec_top = arr[0] - center
    angle_top_deg = np.degrees(np.arctan2(vec_top[1], vec_top[0]))
    # Subtract the 9 degree offset (phi) to get the center of the 20 segment.
    return float((angle_top_deg - 9.0 + 360.0) % 360.0)


def _orientation_weight(source: str) -> float:
    if source == "ocr_20":
        return 4.0
    if source == "template_20":
        return 3.0
    if source.startswith("template_"):
        return 2.0
    return 0.5


def select_stable_detection(detections: list[dict[str, object]]) -> dict[str, object] | None:
    """
    Multi-frame stabilizer:
    - clusters detections by inferred 20-angle
    - chooses strongest cluster
    - returns median points from cluster and best orientation metadata
    """
    if not detections:
        return None

    enriched: list[dict[str, object]] = []
    for detection in detections:
        points = detection.get("points")
        if not isinstance(points, list) or len(points) != 4:
            continue
        twenty_angle = _estimate_twenty_angle_deg(points)
        if twenty_angle is None:
            continue
        source = str(detection.get("orientation_source") or "unknown")
        score = float(detection.get("orientation_score") or 0.0)
        strength = _orientation_weight(source) + score
        enriched.append(
            {
                "detection": detection,
                "twenty_angle": twenty_angle,
                "strength": strength,
            }
        )

    if not enriched:
        return None

    clusters: list[list[dict[str, object]]] = []
    max_delta_deg = 11.0
    for item in enriched:
        placed = False
        for cluster in clusters:
            ref_angle = float(cluster[0]["twenty_angle"])
            delta = _angle_distance_deg(float(item["twenty_angle"]), ref_angle)
            if delta <= max_delta_deg:
                cluster.append(item)
                placed = True
                break
        if not placed:
            clusters.append([item])

    def cluster_score(cluster: list[dict[str, object]]) -> float:
        total_strength = sum(float(entry["strength"]) for entry in cluster)
        return total_strength + len(cluster) * 0.6

    best_cluster = max(clusters, key=cluster_score)
    best_single = max(best_cluster, key=lambda entry: float(entry["strength"]))
    best_detection = dict(best_single["detection"])

    cluster_points = np.array([entry["detection"]["points"] for entry in best_cluster], dtype=float)
    median_points = np.median(cluster_points, axis=0)
    best_detection["points"] = [[float(p[0]), float(p[1])] for p in median_points]

    if len(best_cluster) > 1:
        existing_warning = str(best_detection.get("warning") or "").strip()
        stable_note = f"Stable over {len(best_cluster)}/{len(enriched)} frames."
        best_detection["warning"] = f"{existing_warning} {stable_note}".strip()

    return best_detection

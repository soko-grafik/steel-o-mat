from __future__ import annotations
import numpy as np
try:
    import cv2
except ImportError:
    cv2 = None

def detect_dartboard(frame: np.ndarray) -> dict[str, Any] | None:
    """
    Detects the 4 calibration points automatically.
    Returns a dict with points and the frame resolution.
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
    red_segs = get_segments(mask_red)
    green_segs = get_segments(mask_green)
    
    if not red_segs or not green_segs:
        return None
        
    p_top_mid = min(red_segs, key=lambda p: p[1])
    vec_up = np.array([p_top_mid[0] - center[0], p_top_mid[1] - center[1]])
    vec_up = vec_up / np.linalg.norm(vec_up)
    
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
        "points": [p_top, p_right, p_bottom, p_left],
        "width": w,
        "height": h
    }

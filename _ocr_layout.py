"""Geometry helpers for OCR reading-order recovery on magazine pages."""
from statistics import median

import numpy as np


def _as_points(box):
    if hasattr(box, "tolist"):
        box = box.tolist()
    if not isinstance(box, (list, tuple)):
        return []
    if len(box) >= 4 and all(isinstance(v, (int, float)) for v in box[:4]):
        x1, y1, x2, y2 = (float(v) for v in box[:4])
        return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
    points = []
    for point in box:
        if hasattr(point, "tolist"):
            point = point.tolist()
        if isinstance(point, (list, tuple)) and len(point) >= 2:
            try:
                points.append((float(point[0]), float(point[1])))
            except (TypeError, ValueError):
                pass
    return points


def make_record(text, box, score=1.0):
    """Normalize one OCR result into text plus an axis-aligned bounding box."""
    text = str(text or "").strip()
    points = _as_points(box)
    if not text or not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    try:
        confidence = float(score)
    except (TypeError, ValueError):
        confidence = 1.0
    return {
        "text": text,
        "box": points,
        "x1": min(xs), "y1": min(ys),
        "x2": max(xs), "y2": max(ys),
        "score": confidence,
    }


def _row_sort(records):
    """Sort nearby text lines top-to-bottom, then left-to-right per row."""
    if not records:
        return []
    heights = [max(1.0, item["y2"] - item["y1"]) for item in records]
    tolerance = max(3.0, median(heights) * 0.55)
    rows = []
    for item in sorted(records, key=lambda r: ((r["y1"] + r["y2"]) / 2, r["x1"])):
        center = (item["y1"] + item["y2"]) / 2
        target = None
        for row in reversed(rows[-3:]):
            if abs(center - row["center"]) <= tolerance:
                target = row
                break
        if target is None:
            rows.append({"center": center, "items": [item]})
        else:
            target["items"].append(item)
            target["center"] = sum(
                (entry["y1"] + entry["y2"]) / 2
                for entry in target["items"]
            ) / len(target["items"])
    ordered = []
    for row in sorted(rows, key=lambda r: r["center"]):
        ordered.extend(sorted(row["items"], key=lambda r: r["x1"]))
    return ordered


def _largest_gap(records, axis):
    start_key, end_key = ("x1", "x2") if axis == "x" else ("y1", "y2")
    intervals = sorted((item[start_key], item[end_key]) for item in records)
    if len(intervals) < 2:
        return None
    merged = [list(intervals[0])]
    for start, end in intervals[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    best = None
    for current, following in zip(merged, merged[1:]):
        gap = following[0] - current[1]
        cut = (current[1] + following[0]) / 2
        before = [item for item in records if item[end_key] <= cut]
        after = [item for item in records if item[start_key] >= cut]
        if before and after and (best is None or gap > best[0]):
            best = (gap, before, after)
    return best


def _xy_cut(records, width, height, depth=0):
    if len(records) <= 2 or depth >= 10:
        return [_row_sort(records)]
    heights = [max(1.0, item["y2"] - item["y1"]) for item in records]
    line_height = median(heights)
    x_span = max(item["x2"] for item in records) - min(item["x1"] for item in records)
    y_span = max(item["y2"] for item in records) - min(item["y1"] for item in records)
    vertical = _largest_gap(records, "x")
    horizontal = _largest_gap(records, "y")

    v_ok = bool(vertical and vertical[0] >= max(10.0, x_span * 0.035,
                                                line_height * 0.8))
    h_ok = bool(horizontal and horizontal[0] >= max(8.0, y_span * 0.018,
                                                    line_height * 1.15))
    if not v_ok and not h_ok:
        return [_row_sort(records)]

    v_score = vertical[0] / max(1.0, width) if v_ok else -1.0
    h_score = horizontal[0] / max(1.0, height) if h_ok else -1.0
    chosen = horizontal if h_ok and h_score > v_score * 1.2 else vertical
    first, second = chosen[1], chosen[2]
    return (_xy_cut(first, width, height, depth + 1) +
            _xy_cut(second, width, height, depth + 1))


def layout_groups(records, width, height, multi_column=True):
    """Return ordered OCR blocks; each block contains ordered text records."""
    records = [record for record in records if record and record.get("text")]
    if not records:
        return []
    if not multi_column:
        return [_row_sort(records)]
    return [group for group in _xy_cut(records, width, height) if group]


def detect_spread_split(image, force=False):
    """Return the likely center gutter x-coordinate, or None for a single page."""
    width, height = image.size
    if width < 2:
        return None
    ratio = width / max(1.0, float(height))
    if not force and ratio < 1.2:
        return None

    sample = image.convert("L")
    if sample.width > 1200:
        scale = 1200.0 / sample.width
        sample = sample.resize((1200, max(1, int(sample.height * scale))))
    values = np.asarray(sample, dtype=np.uint8)
    top = max(0, int(values.shape[0] * 0.04))
    bottom = max(top + 1, int(values.shape[0] * 0.96))
    ink = np.mean(values[top:bottom] < 235, axis=0)
    window = max(3, int(len(ink) * 0.012))
    smooth = np.convolve(ink, np.ones(window) / window, mode="same")
    left = max(1, int(len(smooth) * 0.42))
    right = min(len(smooth) - 1, int(len(smooth) * 0.58))
    center_values = smooth[left:right]
    if not len(center_values):
        return width // 2 if force else None
    local_index = int(np.argmin(center_values))
    split_sample = left + local_index

    side_values = np.concatenate((
        smooth[int(len(smooth) * 0.15):int(len(smooth) * 0.35)],
        smooth[int(len(smooth) * 0.65):int(len(smooth) * 0.85)],
    ))
    baseline = float(np.median(side_values)) if len(side_values) else 0.0
    gutter = float(smooth[split_sample])
    white_gutter = baseline >= 0.006 and gutter <= max(0.012, baseline * 0.55)

    if not force and not white_gutter:
        return None
    if force and not white_gutter:
        return width // 2

    # argmin returns the first point of a flat white gutter. Expand around the
    # minimum and use its midpoint so a wide binding margin is split centrally.
    valley_limit = min(max(0.008, gutter + 0.004), max(0.012, baseline * 0.55))
    valley_left = split_sample
    valley_right = split_sample
    while valley_left > left and smooth[valley_left - 1] <= valley_limit:
        valley_left -= 1
    while valley_right + 1 < right and smooth[valley_right + 1] <= valley_limit:
        valley_right += 1
    split_sample = (valley_left + valley_right) // 2
    split = int(round(split_sample * width / float(sample.width)))
    return max(int(width * 0.32), min(int(width * 0.68), split))

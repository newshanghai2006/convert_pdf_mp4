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


def _row_sort(records, reading_order="ltr"):
    """Sort nearby text lines top-to-bottom, then by the selected direction."""
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
        ordered.extend(sorted(
            row["items"], key=lambda r: r["x1"],
            reverse=reading_order == "rtl"))
    return ordered


def _column_sort(records, reading_order="rtl"):
    """Sort vertical text top-to-bottom, with columns in reading order."""
    if not records:
        return []
    widths = [max(1.0, item["x2"] - item["x1"]) for item in records]
    tolerance = max(3.0, median(widths) * 0.7)
    columns = []
    for item in sorted(records, key=lambda r: ((r["x1"] + r["x2"]) / 2,
                                                r["y1"])):
        center = (item["x1"] + item["x2"]) / 2
        target = None
        for column in columns:
            overlap = min(item["x2"], column["x2"]) - max(
                item["x1"], column["x1"])
            if overlap > 0 or abs(center - column["center"]) <= tolerance:
                target = column
                break
        if target is None:
            columns.append({
                "center": center, "x1": item["x1"], "x2": item["x2"],
                "items": [item],
            })
        else:
            target["items"].append(item)
            target["x1"] = min(target["x1"], item["x1"])
            target["x2"] = max(target["x2"], item["x2"])
            target["center"] = sum(
                (entry["x1"] + entry["x2"]) / 2
                for entry in target["items"]
            ) / len(target["items"])
    ordered = []
    for column in sorted(columns, key=lambda c: c["center"],
                         reverse=reading_order == "rtl"):
        ordered.extend(sorted(
            column["items"],
            key=lambda r: (r["y1"], -r["x1"] if reading_order == "rtl"
                           else r["x1"])))
    return ordered


def detect_text_orientation(records):
    """Infer horizontal or vertical layout from OCR box shapes/alignment."""
    records = [record for record in records if record and record.get("text")]
    if len(records) < 2:
        if records:
            item = records[0]
            if item["y2"] - item["y1"] > (item["x2"] - item["x1"]) * 1.35:
                return "vertical"
        return "horizontal"

    tall_weight = 0
    wide_weight = 0
    for item in records:
        width = max(1.0, item["x2"] - item["x1"])
        height = max(1.0, item["y2"] - item["y1"])
        weight = max(1, len(item["text"]))
        if height > width * 1.35:
            tall_weight += weight
        elif width > height * 1.35:
            wide_weight += weight
    if tall_weight > wide_weight * 1.25:
        return "vertical"
    if wide_weight > tall_weight * 1.25:
        return "horizontal"

    centers = [((item["x1"] + item["x2"]) / 2,
                (item["y1"] + item["y2"]) / 2) for item in records]
    widths = [max(1.0, item["x2"] - item["x1"]) for item in records]
    heights = [max(1.0, item["y2"] - item["y1"]) for item in records]
    x_tolerance = median(widths) * 0.8
    y_tolerance = median(heights) * 0.8
    vertical_votes = 0
    horizontal_votes = 0
    for index, (x1, y1) in enumerate(centers):
        vertical_distance = min(
            (abs(y1 - y2) for j, (x2, y2) in enumerate(centers)
             if j != index and abs(x1 - x2) <= x_tolerance),
            default=float("inf"))
        horizontal_distance = min(
            (abs(x1 - x2) for j, (x2, y2) in enumerate(centers)
             if j != index and abs(y1 - y2) <= y_tolerance),
            default=float("inf"))
        if vertical_distance < horizontal_distance:
            vertical_votes += 1
        elif horizontal_distance < vertical_distance:
            horizontal_votes += 1
    return "vertical" if vertical_votes > horizontal_votes * 1.25 else "horizontal"


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


def _xy_cut(records, width, height, orientation="horizontal",
            reading_order="ltr", depth=0):
    if len(records) <= 2 or depth >= 10:
        sorter = _column_sort if orientation == "vertical" else _row_sort
        return [sorter(records, reading_order)]
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
        sorter = _column_sort if orientation == "vertical" else _row_sort
        return [sorter(records, reading_order)]

    v_score = vertical[0] / max(1.0, width) if v_ok else -1.0
    h_score = horizontal[0] / max(1.0, height) if h_ok else -1.0
    chosen = horizontal if h_ok and h_score > v_score * 1.2 else vertical
    first, second = chosen[1], chosen[2]
    if chosen is vertical and reading_order == "rtl":
        first, second = second, first
    return (_xy_cut(first, width, height, orientation, reading_order,
                    depth + 1) +
            _xy_cut(second, width, height, orientation, reading_order,
                    depth + 1))


def layout_groups(records, width, height, multi_column=True,
                  text_orientation="auto", reading_order="auto"):
    """Return ordered OCR blocks; each block contains ordered text records."""
    records = [record for record in records if record and record.get("text")]
    if not records:
        return []
    if text_orientation not in ("auto", "horizontal", "vertical"):
        text_orientation = "auto"
    orientation = (detect_text_orientation(records)
                   if text_orientation == "auto" else text_orientation)
    if reading_order not in ("auto", "ltr", "rtl"):
        reading_order = "auto"
    order = (("rtl" if orientation == "vertical" else "ltr")
             if reading_order == "auto" else reading_order)
    sorter = _column_sort if orientation == "vertical" else _row_sort
    if not multi_column:
        return [sorter(records, order)]
    return [group for group in _xy_cut(
        records, width, height, orientation, order) if group]


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

#!/usr/bin/env python3
"""
OCR worker：被 pipeline.ocr_pdf_subprocess 以子进程方式调用。

设计要点（性能 & 健壮性）：
  - 一次子进程尽量处理「从 START 到 END 的所有剩余页」，把 OCR 引擎初始化
    （EasyOCR / RapidOCR / PaddleOCR）成本**只付一次**，
    而不是每 4 页重新加载一次。
  - 逐页写入 out_txt 并 flush；已完成的页会跳过。因此即便子进程中途崩溃，
    主进程重新拉起时可从断点续跑，不会重做。
  - 单页 OCR 失败不再让整个流程卡死：捕获异常后写入空的 PAGE 头，
    保证 done 计数前进，主进程不会误判为“无进展”。
  - 直接把内存中的 numpy 图像喂给 OCR 引擎，不再落地临时 JPEG
    （避免 JPEG 压缩损失，也不再残留 _ocr_tmp_*.jpg）。

用法: py _ocr_worker.py <pdf> <start> <end> <out_txt> [lang] [engine]
      start/end 为 0-based 索引（end 不含），engine 默认为 easyocr
"""
import sys
import os
import re
import gc
import json

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import numpy as np
import fitz
from PIL import Image

PDF = sys.argv[1]
START = int(sys.argv[2])
END = int(sys.argv[3])
OUT = sys.argv[4]
# 识别语言：ch_sim(简体) 或 ch_tra(繁体)，均搭配英文。默认简体。
# 注意 easyocr 不允许简体+繁体同时使用，只能二选一。
LANG = sys.argv[5] if len(sys.argv) > 5 else "ch_sim"
if LANG not in ("ch_sim", "ch_tra"):
    LANG = "ch_sim"
OCR_ENGINE = sys.argv[6].strip().lower() if len(sys.argv) > 6 else "easyocr"
if OCR_ENGINE not in ("easyocr", "rapidocr", "paddleocr"):
    OCR_ENGINE = "easyocr"

# 渲染分辨率：越高越清晰但越慢、越费内存。
RENDER_ZOOM = float(os.getenv("OCR_RENDER_ZOOM", str(150 / 72.0)))
# easyocr 内部会把长边缩放到 canvas_size。这是清晰度 / 内存 / 速度的关键权衡：
#   - 太小（如旧版 800）：小字糊掉、识别很差。
#   - 太大（如 2560）：在低内存机器上会 OOM 甚至段错误（单页可能要 ~1GB）。
# 1024 在本机（内存偏紧）实测稳定且比 800 清晰。内存充裕的机器可上调到 1280/1600 提高精度；
# 若出现 "not enough memory" 或段错误崩溃，请下调该值。
CANVAS_SIZE = int(os.getenv("OCR_CANVAS_SIZE", "1024"))
MAG_RATIO = float(os.getenv("OCR_MAG_RATIO", "1.0"))

doc = fitz.open(PDF)
N = doc.page_count
mat = fitz.Matrix(RENDER_ZOOM, RENDER_ZOOM)


def done_pages():
    if not os.path.exists(OUT):
        return set()
    with open(OUT, encoding="utf-8") as f:
        return set(int(m) for m in re.findall(r"========== PAGE (\d+)", f.read()))


def _load_reader():
    if OCR_ENGINE == "easyocr":
        import easyocr
        # 若模型已存在则关闭联网下载，避免初始化阶段长时间等待。
        model_dir = os.path.join(os.path.expanduser("~"), ".EasyOCR", "model")
        recog_file = {"ch_sim": "zh_sim_g2.pth", "ch_tra": "chinese.pth"}
        need = ("craft_mlt_25k.pth", recog_file.get(LANG, "zh_sim_g2.pth"))
        have_models = all(os.path.exists(os.path.join(model_dir, n)) for n in need)
        reader = easyocr.Reader([LANG, "en"], gpu=False, verbose=False,
                                quantize=False, download_enabled=not have_models)
        print(f"READER_READY engine=easyocr lang={LANG}", flush=True)
        return reader

    if OCR_ENGINE == "rapidocr":
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError:
            try:
                from rapidocr import RapidOCR
            except ImportError as e:
                raise RuntimeError(
                    "RapidOCR 未安装，请运行: py -3.14 -m pip install rapidocr_onnxruntime"
                ) from e
        reader = RapidOCR()
        print(f"READER_READY engine=rapidocr lang={LANG}", flush=True)
        return reader

    try:
        from paddleocr import PaddleOCR
    except ImportError as e:
        raise RuntimeError(
            "PaddleOCR 未安装，请按 README 安装 paddleocr 与 paddlepaddle"
        ) from e
    paddle_lang = "chinese_cht" if LANG == "ch_tra" else "ch"
    try:
        # PaddleOCR 3.x API.
        reader = PaddleOCR(
            lang=paddle_lang,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=True,
        )
    except TypeError:
        # PaddleOCR 2.x API.
        reader = PaddleOCR(use_angle_cls=True, lang=paddle_lang,
                           use_gpu=False, show_log=False)
    print(f"READER_READY engine=paddleocr lang={LANG}", flush=True)
    return reader


def _json_value(value):
    if hasattr(value, "json"):
        value = value.json
        if callable(value):
            value = value()
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            return None
    return value


def _paddle_lines(result):
    """Read text from PaddleOCR 2.x nested lists or 3.x result objects."""
    def is_old_line(value):
        if not (isinstance(value, (list, tuple)) and len(value) >= 2):
            return False
        info = value[1]
        return (isinstance(info, (list, tuple)) and len(info) >= 1 and
                isinstance(info[0], str))

    if isinstance(result, (list, tuple)):
        items = result
    elif hasattr(result, "__iter__") and not isinstance(result, (str, bytes, dict)):
        items = list(result)
    else:
        items = [result]
    lines = []
    for item in items:
        data = _json_value(item)
        if isinstance(data, dict):
            if isinstance(data.get("res"), dict):
                data = data["res"]
            texts = data.get("rec_texts") or data.get("texts") or []
            lines.extend(str(x).strip() for x in texts if str(x).strip())
            continue
        if not isinstance(item, (list, tuple)):
            continue
        if is_old_line(item):
            pages = [item]
        elif item and is_old_line(item[0]):
            pages = [item]
        else:
            pages = item
        for line in pages:
            if not isinstance(line, (list, tuple)) or len(line) < 2:
                continue
            info = line[1]
            text = info[0] if isinstance(info, (list, tuple)) else info
            if text and str(text).strip():
                lines.append(str(text).strip())
    return lines


def _rapid_lines(result):
    if isinstance(result, tuple):
        result = result[0]
    lines = []
    for item in result or []:
        if isinstance(item, dict):
            text = item.get("text") or item.get("txt") or ""
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            text = item[1]
        else:
            text = ""
        if text and str(text).strip():
            lines.append(str(text).strip())
    return lines


def recognize(image, reader):
    if OCR_ENGINE == "easyocr":
        return [str(x).strip() for x in reader.readtext(
            np.array(image), detail=0, paragraph=False,
            canvas_size=CANVAS_SIZE, mag_ratio=MAG_RATIO,
            workers=0, batch_size=1) if str(x).strip()]

    # ONNX/Paddle implementations conventionally expect BGR arrays.
    bgr = np.array(image)[:, :, ::-1]
    if OCR_ENGINE == "rapidocr":
        return _rapid_lines(reader(bgr))
    if hasattr(reader, "predict"):
        return _paddle_lines(reader.predict(input=bgr))
    return _paddle_lines(reader.ocr(bgr, cls=True))


reader = _load_reader()

already = done_pages()
with open(OUT, "a", encoding="utf-8") as f:
    for i in range(START, min(END, N)):
        if (i + 1) in already:
            continue
        pix = None
        im = None
        try:
            pix = doc[i].get_pixmap(matrix=mat)
            im = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            lines = recognize(im, reader)
        except Exception as e:  # 单页失败：写空页，保证进度前进
            lines = []
            print(f"PAGE_ERROR {i+1}: {e}", flush=True)
        f.write(f"========== PAGE {i+1} ==========\n" + "\n".join(lines) + "\n\n")
        f.flush()
        del pix, im, lines
        gc.collect()
        print(f"DONE {i+1}", flush=True)
print("BATCH_OK", flush=True)

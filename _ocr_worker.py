#!/usr/bin/env python3
"""
OCR worker：被 pipeline.ocr_pdf_subprocess 以子进程方式调用。

设计要点（性能 & 健壮性）：
  - 一次子进程尽量处理「从 START 到 END 的所有剩余页」，把昂贵的
    torch / easyocr / Reader 初始化（本机约 80~90 秒）**只付一次**，
    而不是每 4 页重新加载一次。
  - 逐页写入 out_txt 并 flush；已完成的页会跳过。因此即便子进程中途崩溃，
    主进程重新拉起时可从断点续跑，不会重做。
  - 单页 OCR 失败不再让整个流程卡死：捕获异常后写入空的 PAGE 头，
    保证 done 计数前进，主进程不会误判为“无进展”。
  - 直接把内存中的 numpy 图像喂给 easyocr，不再落地临时 JPEG
    （避免 JPEG 压缩损失，也不再残留 _ocr_tmp_*.jpg）。

用法: py _ocr_worker.py <pdf> <start> <end> <out_txt>
      start/end 为 0-based 索引（end 不含）
"""
import sys
import os
import re
import gc

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import numpy as np
import fitz
from PIL import Image
import easyocr

PDF = sys.argv[1]
START = int(sys.argv[2])
END = int(sys.argv[3])
OUT = sys.argv[4]
# 识别语言：ch_sim(简体) 或 ch_tra(繁体)，均搭配英文。默认简体。
# 注意 easyocr 不允许简体+繁体同时使用，只能二选一。
LANG = sys.argv[5] if len(sys.argv) > 5 else "ch_sim"
if LANG not in ("ch_sim", "ch_tra"):
    LANG = "ch_sim"

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


# 若模型已存在，则关闭联网下载：避免在网络被墙/半通的机器上，Reader 初始化
# 因尝试联网校验/下载而**长时间卡住**（表现为一直停在“正在加载 OCR 模型”）。
# 各语言用到的识别模型文件不同：简体=zh_sim_g2.pth，繁体=chinese.pth（+共享的检测模型 craft）。
_MODEL_DIR = os.path.join(os.path.expanduser("~"), ".EasyOCR", "model")
_RECOG_FILE = {"ch_sim": "zh_sim_g2.pth", "ch_tra": "chinese.pth"}
_NEED = ("craft_mlt_25k.pth", _RECOG_FILE.get(LANG, "zh_sim_g2.pth"))
_HAVE_MODELS = all(os.path.exists(os.path.join(_MODEL_DIR, n)) for n in _NEED)

reader = easyocr.Reader([LANG, 'en'], gpu=False, verbose=False, quantize=False,
                        download_enabled=not _HAVE_MODELS)
print(f"READER_READY lang={LANG}", flush=True)

already = done_pages()
with open(OUT, "a", encoding="utf-8") as f:
    for i in range(START, min(END, N)):
        if (i + 1) in already:
            continue
        try:
            pix = doc[i].get_pixmap(matrix=mat)
            im = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            lines = reader.readtext(
                np.array(im), detail=0, paragraph=False,
                canvas_size=CANVAS_SIZE, mag_ratio=MAG_RATIO,
                workers=0, batch_size=1)
        except Exception as e:  # 单页失败：写空页，保证进度前进
            lines = []
            print(f"PAGE_ERROR {i+1}: {e}", flush=True)
        f.write(f"========== PAGE {i+1} ==========\n" + "\n".join(lines) + "\n\n")
        f.flush()
        del pix, im, lines
        gc.collect()
        print(f"DONE {i+1}", flush=True)
print("BATCH_OK", flush=True)

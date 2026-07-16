#!/usr/bin/env python3
"""
《大众电影》PDF -> 解说视频 本地 Web 应用。
运行: py -3.14 app.py  然后浏览器打开 http://127.0.0.1:5005

功能:
  - 上传 PDF
  - 自动提取文字 (文字层优先, 纯图片则 OCR)
  - 可编辑每段旁白
  - 调参数: 每片段页数 / 每片段时长 / 封面时长 / 声音 / 语速 / 标题信息
  - 生成 MP4 并下载
"""
import os
import io
import re
import json
import time
import uuid
import threading

from flask import Flask, request, jsonify, send_file, Response
from werkzeug.utils import secure_filename

import pipeline
from index_html import INDEX_HTML

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(BASE_DIR, "font.ttf")
OCR_WORKER = os.path.join(BASE_DIR, "_ocr_worker.py")
UPLOAD_DIR = os.path.join(BASE_DIR, "tasks")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)

VOICES = [
    ("zh-CN-YunxiNeural", "云希（男声）"),
    ("zh-CN-YunyangNeural", "云扬（男·新闻）"),
    ("zh-CN-XiaoxiaoNeural", "晓晓（女声）"),
    ("zh-CN-XiaoyiNeural", "晓伊（女声）"),
    ("zh-CN-liaoning-XiaobeiNeural", "辽宁晓蓓（女）"),
    ("zh-CN-shaanxi-XiaoniNeural", "陕西小妮（女）"),
]
RATES = ["+12%", "+6%", "+0%", "-10%", "-20%"]

# 任务状态  task_id -> dict
TASKS = {}
TASKS_LOCK = threading.Lock()


def update_task(tid, **kw):
    with TASKS_LOCK:
        TASKS[tid].update(kw)


# ---------------------------------------------------------------------------
# 后台：提取文字
# ---------------------------------------------------------------------------
def do_prepare(tid, pdf_path, pages_per_clip, use_ocr, ocr_lang="ch_sim"):
    def cb(stage, pct, msg):
        update_task(tid, stage=stage, progress=pct, message=msg)

    try:
        pages = pipeline.extract_page_texts(
            pdf_path, use_ocr=use_ocr, progress_cb=cb,
            ocr_worker=OCR_WORKER, py_exe=__import__("sys").executable,
            ocr_lang=ocr_lang)
        clips = pipeline.group_into_clips(pages, pages_per_clip)
        update_task(tid, stage="ready", progress=1.0,
                    message="文字提取完成，可编辑旁白后生成",
                    narration=clips, clips=len(clips),
                    page_count=len(pages))
    except Exception as e:
        update_task(tid, stage="error", message=f"提取失败: {e}")


# ---------------------------------------------------------------------------
# 后台：生成视频
# ---------------------------------------------------------------------------
def do_generate(tid, pdf_path, params, narration):
    def cb(stage, pct, msg):
        update_task(tid, stage=stage, progress=pct, message=msg)

    try:
        params["font_path"] = FONT_PATH
        out_path = TASKS[tid]["output_path"]
        res = pipeline.build_video(pdf_path, out_path, params, narration, cb)
        if res:
            srt_path = os.path.splitext(out_path)[0] + ".srt"
            srt_ready = (params.get("subtitle_mode") in ("srt", "burn")
                         and os.path.exists(srt_path))
            update_task(tid, stage="done", progress=1.0,
                        message="视频生成完成", output_ready=True,
                        srt_path=srt_path, srt_ready=srt_ready)
        else:
            update_task(tid, stage="error", message="视频合成失败，请查看服务端日志")
    except Exception as e:
        update_task(tid, stage="error", message=f"生成失败: {e}")


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return Response(INDEX_HTML, mimetype="text/html")


@app.route("/api/voices")
def api_voices():
    return jsonify({"voices": VOICES, "rates": RATES})


@app.route("/api/prepare", methods=["POST"])
def api_prepare():
    if "pdf" not in request.files:
        return jsonify({"error": "no pdf"}), 400
    f = request.files["pdf"]
    if not f.filename:
        return jsonify({"error": "empty"}), 400
    pages_per_clip = int(request.form.get("pages_per_clip", 2))
    use_ocr = request.form.get("use_ocr", "true").lower() == "true"
    page_range = request.form.get("page_range", "").strip()
    ocr_lang = request.form.get("ocr_lang", "ch_sim").strip()
    if ocr_lang not in ("ch_sim", "ch_tra"):
        ocr_lang = "ch_sim"

    tid = uuid.uuid4().hex[:12]
    work = os.path.join(UPLOAD_DIR, tid)
    os.makedirs(work, exist_ok=True)
    fname = secure_filename(f.filename) or "input.pdf"
    pdf_path = os.path.join(work, fname)
    f.save(pdf_path)
    out_path = os.path.join(work, "output.mp4")

    # 页码选择：把选中的页抽成子 PDF，后续全流程都基于它
    sel_msg = ""
    try:
        sel_path = os.path.join(work, "input_sel.pdf")
        work_pdf, n_sel = pipeline.make_working_pdf(pdf_path, sel_path, page_range)
        pdf_path = work_pdf
        if page_range:
            sel_msg = f"（已按页码选择 {n_sel} 页）"
    except Exception as e:
        return jsonify({"error": f"页码选择解析失败: {e}"}), 400

    with TASKS_LOCK:
        TASKS[tid] = {
            "stage": "preparing", "progress": 0.0,
            "message": "开始提取文字" + sel_msg, "pdf_path": pdf_path,
            "output_path": out_path, "output_ready": False,
            "narration": [], "clips": 0, "page_count": 0,
            "srt_ready": False, "srt_path": "",
        }
    t = threading.Thread(target=do_prepare,
                         args=(tid, pdf_path, pages_per_clip, use_ocr, ocr_lang))
    t.daemon = True
    t.start()
    return jsonify({"task_id": tid})


@app.route("/api/status")
def api_status():
    tid = request.args.get("task")
    with TASKS_LOCK:
        st = TASKS.get(tid)
        if not st:
            return jsonify({"error": "not found"}), 404
        # 复制可序列化字段（去掉大对象）
        return jsonify({
            "stage": st["stage"], "progress": st["progress"],
            "message": st["message"], "clips": st["clips"],
            "page_count": st["page_count"],
            "narration": st.get("narration", []),
            "output_ready": st["output_ready"],
            "srt_ready": st.get("srt_ready", False),
        })


@app.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.get_json(force=True)
    tid = data.get("task_id")
    with TASKS_LOCK:
        st = TASKS.get(tid)
        if not st:
            return jsonify({"error": "not found"}), 404
        if st["stage"] != "ready":
            return jsonify({"error": "not ready"}), 400
        pdf_path = st["pdf_path"]
        out_path = st["output_path"]

    narration = data.get("narration", [])
    try:
        clip_durs = [float(x) for x in (data.get("clip_durations") or [])]
    except Exception:
        clip_durs = []
    params = {
        "pages_per_clip": int(data.get("pages_per_clip", 2)),
        "clip_duration": float(data.get("clip_duration", 12.0)),
        "clip_durations": clip_durs,
        "title_duration": float(data.get("title_duration", 3.0)),
        "auto_duration": bool(data.get("auto_duration", False)),
        "max_clip_duration": float(data.get("max_clip_duration", 60.0)),
        "tail_pad": float(data.get("tail_pad", 1.0)),
        "aspect": data.get("aspect", "16:9"),
        "custom_w": float(data.get("custom_w", 16) or 16),
        "custom_h": float(data.get("custom_h", 9) or 9),
        "quality": int(data.get("quality", 1080) or 1080),
        "subtitle_mode": data.get("subtitle_mode", "none"),
        "title": data.get("title", "大众电影"),
        "subtitle": data.get("subtitle", ""),
        "feature": data.get("feature", ""),
        "feature2": data.get("feature2", ""),
        "feature3": data.get("feature3", ""),
        "tagline": data.get("tagline", ""),
        "voice": data.get("voice", "zh-CN-YunxiNeural"),
        "rate": data.get("rate", "+6%"),
    }
    update_task(tid, stage="generating", progress=0.0, message="开始生成视频")
    t = threading.Thread(target=do_generate, args=(tid, pdf_path, params, narration))
    t.daemon = True
    t.start()
    return jsonify({"ok": True})


@app.route("/api/download/<tid>")
def api_download(tid):
    with TASKS_LOCK:
        st = TASKS.get(tid)
        if not st or not st.get("output_ready"):
            return jsonify({"error": "not ready"}), 404
        out_path = st["output_path"]
    return send_file(out_path, mimetype="video/mp4",
                     as_attachment=True, download_name="解说视频.mp4")


@app.route("/api/download_srt/<tid>")
def api_download_srt(tid):
    with TASKS_LOCK:
        st = TASKS.get(tid)
        if not st or not st.get("srt_ready"):
            return jsonify({"error": "not ready"}), 404
        srt_path = st.get("srt_path", "")
    if not srt_path or not os.path.exists(srt_path):
        return jsonify({"error": "not found"}), 404
    return send_file(srt_path, mimetype="application/x-subrip",
                     as_attachment=True, download_name="解说字幕.srt")


def _preflight():
    """启动前自检：打印关键依赖状态，避免“运行无显示”一头雾水。"""
    import shutil
    print("=" * 50, flush=True)
    print("PDF 解说视频生成器 启动自检", flush=True)
    ff = shutil.which("ffmpeg")
    print(f"  ffmpeg : {'OK ' + ff if ff else '缺失! 请安装 ffmpeg 并加入 PATH'}", flush=True)
    fp = shutil.which("ffprobe")
    print(f"  ffprobe: {'OK ' + fp if fp else '缺失! 请安装 ffmpeg(含 ffprobe)'}", flush=True)
    for mod in ("flask", "fitz", "PIL", "edge_tts"):
        try:
            __import__(mod)
            print(f"  {mod:8s}: OK", flush=True)
        except Exception as e:
            print(f"  {mod:8s}: 缺失! {e}", flush=True)
    try:
        __import__("easyocr")
        print("  easyocr : OK（纯图片PDF的OCR可用）", flush=True)
    except Exception:
        print("  easyocr : 未安装（仅影响纯图片PDF的OCR，有文字层的PDF不受影响）", flush=True)
    print("=" * 50, flush=True)


if __name__ == "__main__":
    _preflight()
    print("启动服务: http://127.0.0.1:5005", flush=True)
    print("（若浏览器打不开，确认本机防火墙未拦截 5005 端口）", flush=True)
    app.run(host="127.0.0.1", port=5005, debug=False, threaded=True)

#!/usr/bin/env python3
"""
AI PDF解说视频生成器（《大众电影》式杂志）本地 Web 应用。
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

from index_html import INDEX_HTML

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(BASE_DIR, "font.ttf")
OCR_WORKER = os.path.join(BASE_DIR, "_ocr_worker.py")
UPLOAD_DIR = os.path.join(BASE_DIR, "tasks")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)


def _pipeline():
    import pipeline
    return pipeline

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
TITLE_PREVIEW_LOCK = threading.Lock()


def _bounded_float(data, key, default, low, high):
    try:
        value = float(data.get(key, default))
    except Exception:
        value = default
    return max(low, min(high, value))


def _title_font_sizes(data):
    return {
        "title": _bounded_float(data, "title_font_title", 100, 40, 180),
        "subtitle": _bounded_float(data, "title_font_subtitle", 52, 20, 100),
        "badge": _bounded_float(data, "title_font_badge", 32, 16, 72),
        "info": _bounded_float(data, "title_font_info", 34, 16, 72),
        "tagline": _bounded_float(data, "title_font_tagline", 28, 14, 64),
    }


def update_task(tid, **kw):
    with TASKS_LOCK:
        TASKS[tid].update(kw)


# ---------------------------------------------------------------------------
# 后台：提取文字
# ---------------------------------------------------------------------------
def do_prepare(tid, pdf_path, pages_per_clip, use_ocr, ocr_lang="ch_sim",
               page_range="", ai_ocr_cfg=None, ocr_engine="easyocr"):
    def cb(stage, pct, msg):
        update_task(tid, stage=stage, progress=pct, message=msg)

    try:
        llm_cfg = TASKS[tid].get("llm_cfg") or {}
        ai_ocr_cfg = ai_ocr_cfg or TASKS[tid].get("ai_ocr_cfg") or {}
        # AI OCR has its own image path; keep the existing probe behavior for
        # AI narration that still relies on the local OCR result.
        probe_ocr = bool(llm_cfg.get("enabled") and
                         not ai_ocr_cfg.get("enabled"))
        p = _pipeline()
        if page_range:
            cb("extract", 0.01, "正在解析页码选择")
            sel_path = os.path.join(os.path.dirname(pdf_path), "input_sel.pdf")
            pdf_path, n_sel = p.make_working_pdf(pdf_path, sel_path, page_range)
            update_task(tid, pdf_path=pdf_path)
            if n_sel:
                cb("extract", 0.03, f"页码选择完成，共 {n_sel} 页")
        pages = p.extract_page_texts(
            pdf_path, use_ocr=use_ocr, progress_cb=cb,
            ocr_worker=OCR_WORKER, py_exe=__import__("sys").executable,
            ocr_lang=ocr_lang, probe_ocr=probe_ocr, ai_ocr_cfg=ai_ocr_cfg,
            ocr_engine=ocr_engine)
        clips = p.group_into_clips(pages, pages_per_clip)
        fallback_clips = list(clips)
        update_task(tid, page_texts=pages,
                    fallback_narration=fallback_clips,
                    pages_per_clip=pages_per_clip)
        ai_note = ""
        if llm_cfg.get("enabled"):
            clips, ai_note = p.generate_ai_narration(
                pages, pages_per_clip, clips, llm_cfg, cb)
        ready_msg = "\u6587\u5b57\u63d0\u53d6\u5b8c\u6210\uff0c\u53ef\u7f16\u8f91\u65c1\u767d\u540e\u751f\u6210"
        if llm_cfg.get("enabled"):
            ready_msg = f"\u6587\u5b57\u63d0\u53d6\u5b8c\u6210\uff0c{ai_note or 'AI \u65c1\u767d\u5df2\u751f\u6210'}\uff0c\u53ef\u7f16\u8f91\u540e\u751f\u6210\u89c6\u9891"
        update_task(tid, stage="ready", progress=1.0,
                    message=ready_msg,
                    narration=clips, clips=len(clips),
                    page_count=len(pages))
    except Exception as e:
        update_task(tid, stage="error", message=f"\u63d0\u53d6\u5931\u8d25: {e}")


def do_regenerate_narration(tid, pages, pages_per_clip, fallback_clips, llm_cfg):
    def cb(stage, pct, msg):
        update_task(tid, stage=stage, progress=pct, message=msg)

    try:
        clips, ai_note = _pipeline().generate_ai_narration(
            pages, pages_per_clip, fallback_clips, llm_cfg, cb)
        message = ai_note or "AI \u65c1\u767d\u5df2\u91cd\u65b0\u751f\u6210"
        update_task(tid, stage="ready", progress=1.0, message=message,
                    narration=clips, clips=len(clips), llm_cfg=llm_cfg)
    except Exception as e:
        update_task(tid, stage="ready", progress=1.0,
                    message=f"AI \u65c1\u767d\u91cd\u65b0\u751f\u6210\u5931\u8d25\uff1a{e}\uff1b\u5df2\u4fdd\u7559\u5f53\u524d\u65c1\u767d")


# ---------------------------------------------------------------------------
# \u540e\u53f0\uff1a\u751f\u6210\u89c6\u9891
# ---------------------------------------------------------------------------
def do_generate(tid, pdf_path, params, narration):
    def cb(stage, pct, msg):
        update_task(tid, stage=stage, progress=pct, message=msg)

    try:
        params["font_path"] = FONT_PATH
        out_path = TASKS[tid]["output_path"]
        res = _pipeline().build_video(pdf_path, out_path, params, narration, cb)
        if res:
            srt_path = os.path.splitext(out_path)[0] + ".srt"
            srt_ready = (params.get("subtitle_mode") in
                         ("srt", "burn", "burn_bilingual")
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


@app.route("/api/title_preview", methods=["POST"])
def api_title_preview():
    data = request.get_json(force=True)
    tid = data.get("task_id")
    with TASKS_LOCK:
        st = TASKS.get(tid)
        if not st:
            return jsonify({"error": "task not found"}), 404
        pdf_path = st.get("pdf_path")
    if not pdf_path or not os.path.exists(pdf_path):
        return jsonify({"error": "pdf not found"}), 404

    style = data.get("title_card_style", "classic")
    if style not in ("classic", "custom"):
        style = "classic"
    p = _pipeline()
    full_w, full_h = p.compute_dimensions(
        data.get("aspect", "16:9"),
        float(data.get("custom_w", 16) or 16),
        float(data.get("custom_h", 9) or 9),
        int(data.get("quality", 1080) or 1080))
    scale = min(1.0, 720.0 / max(full_w, full_h))
    width = max(160, int(full_w * scale))
    height = max(160, int(full_h * scale))
    preview_dir = os.path.join(os.path.dirname(pdf_path), "title_preview")
    with TITLE_PREVIEW_LOCK:
        cover_path = os.path.join(preview_dir, "page_01.png")
        if not os.path.exists(cover_path):
            p.extract_cover_page(pdf_path, preview_dir)
        title_path = p.create_title_card(
            preview_dir, FONT_PATH,
            data.get("title", "大众电影"), data.get("subtitle", ""),
            data.get("feature", ""), data.get("feature2", ""),
            data.get("feature3", ""), data.get("tagline", ""),
            width, height, style, _title_font_sizes(data))
        with open(title_path, "rb") as f:
            image_data = f.read()
    return Response(image_data, mimetype="image/png",
                    headers={"Cache-Control": "no-store"})


@app.route("/api/prepare", methods=["POST"])
def api_prepare():
    if "pdf" not in request.files:
        return jsonify({"error": "no pdf"}), 400
    f = request.files["pdf"]
    if not f.filename:
        return jsonify({"error": "empty"}), 400
    pages_per_clip = int(request.form.get("pages_per_clip", 2))
    use_ocr = request.form.get("use_ocr", "true").lower() == "true"
    use_ai_narration = request.form.get("use_ai_narration", "false").lower() == "true"
    use_ai_ocr = request.form.get("use_ai_ocr", "false").lower() == "true"
    if use_ai_narration or use_ai_ocr:
        use_ocr = True
    try:
        narration_target_chars = int(request.form.get("narration_target_chars", 200))
    except (TypeError, ValueError):
        narration_target_chars = 200
    narration_target_chars = max(40, min(400, narration_target_chars))
    llm_common = {
        "provider": request.form.get("llm_provider", "openai").strip().lower(),
        "base_url": request.form.get("llm_base_url", "").strip(),
        "api_key": request.form.get("llm_api_key", "").strip(),
        "model": request.form.get("llm_model", "").strip(),
        "narration_target_chars": narration_target_chars,
    }
    llm_cfg = dict(llm_common, enabled=use_ai_narration)
    ai_ocr_cfg = dict(llm_common, enabled=use_ai_ocr)
    page_range = request.form.get("page_range", "").strip()
    ocr_lang = request.form.get("ocr_lang", "ch_sim").strip()
    if ocr_lang not in ("ch_sim", "ch_tra"):
        ocr_lang = "ch_sim"
    ocr_engine = request.form.get("ocr_engine", "easyocr").strip().lower()
    if ocr_engine not in ("easyocr", "rapidocr", "paddleocr"):
        ocr_engine = "easyocr"

    tid = uuid.uuid4().hex[:12]
    work = os.path.join(UPLOAD_DIR, tid)
    os.makedirs(work, exist_ok=True)
    fname = secure_filename(f.filename) or "input.pdf"
    pdf_path = os.path.join(work, fname)
    f.save(pdf_path)
    out_path = os.path.join(work, "output.mp4")

    with TASKS_LOCK:
        TASKS[tid] = {
            "stage": "preparing", "progress": 0.0,
            "message": "\u6b63\u5728\u89e3\u6790\u9875\u7801\u9009\u62e9" if page_range else "\u5f00\u59cb\u63d0\u53d6\u6587\u5b57",
            "pdf_path": pdf_path,
            "output_path": out_path, "output_ready": False,
            "narration": [], "clips": 0, "page_count": 0,
            "srt_ready": False, "srt_path": "",
            "llm_cfg": llm_cfg,
            "ai_ocr_cfg": ai_ocr_cfg,
            "ocr_engine": ocr_engine,
            "page_range": page_range,
        }
    t = threading.Thread(target=do_prepare,
                         args=(tid, pdf_path, pages_per_clip, use_ocr, ocr_lang,
                               page_range, ai_ocr_cfg, ocr_engine))
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
        # \u590d\u5236\u53ef\u5e8f\u5217\u5316\u5b57\u6bb5\uff08\u53bb\u6389\u5927\u5bf9\u8c61\uff09
        return jsonify({
            "stage": st["stage"], "progress": st["progress"],
            "message": st["message"], "clips": st["clips"],
            "page_count": st["page_count"],
            "narration": st.get("narration", []),
            "output_ready": st["output_ready"],
            "srt_ready": st.get("srt_ready", False),
        })


@app.route("/api/save_narration", methods=["POST"])
def api_save_narration():
    data = request.get_json(force=True)
    tid = data.get("task_id")
    idx = int(data.get("idx", -1))
    text = data.get("text", "")
    with TASKS_LOCK:
        st = TASKS.get(tid)
        if not st:
            return jsonify({"error": "not found"}), 404
        narration = st.get("narration", [])
        if idx < 0 or idx >= len(narration):
            return jsonify({"error": "bad idx"}), 400
        narration[idx] = text
        st["narration"] = narration
    return jsonify({"ok": True})


@app.route("/api/regenerate_narration", methods=["POST"])
def api_regenerate_narration():
    data = request.get_json(force=True)
    tid = data.get("task_id")
    with TASKS_LOCK:
        st = TASKS.get(tid)
        if not st:
            return jsonify({"error": "not found"}), 404
        if st["stage"] not in ("ready", "done"):
            return jsonify({"error": "task is busy"}), 400
        pages = list(st.get("page_texts") or [])
        fallback_clips = list(st.get("fallback_narration") or [])
        pages_per_clip = int(st.get("pages_per_clip") or 1)
        stored_cfg = dict(st.get("llm_cfg") or {})
    if not pages or not fallback_clips:
        return jsonify({"error": "当前任务没有可复用的提取文字，请重新载入 PDF"}), 400

    try:
        target_chars = int(data.get("narration_target_chars", 200))
    except (TypeError, ValueError):
        target_chars = 200
    llm_cfg = {
        "enabled": True,
        "provider": str(data.get("llm_provider") or
                        stored_cfg.get("provider") or "openai").strip().lower(),
        "base_url": str(data.get("llm_base_url") or
                        stored_cfg.get("base_url") or "").strip(),
        "api_key": str(data.get("llm_api_key") or
                       stored_cfg.get("api_key") or "").strip(),
        "model": str(data.get("llm_model") or
                     stored_cfg.get("model") or "").strip(),
        "narration_target_chars": max(40, min(400, target_chars)),
    }
    if llm_cfg["provider"] not in ("openai", "nvidia"):
        llm_cfg["provider"] = "openai"
    if not llm_cfg["base_url"] or not llm_cfg["model"]:
        return jsonify({"error": "请填写 LLM base_url 和 Model"}), 400

    update_task(tid, stage="ai", progress=0.55,
                message="正在复用已提取文字重新生成 AI 旁白，不会执行 OCR",
                llm_cfg=llm_cfg)
    t = threading.Thread(
        target=do_regenerate_narration,
        args=(tid, pages, pages_per_clip, fallback_clips, llm_cfg))
    t.daemon = True
    t.start()
    return jsonify({"ok": True})


@app.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.get_json(force=True)
    tid = data.get("task_id")
    with TASKS_LOCK:
        st = TASKS.get(tid)
        if not st:
            return jsonify({"error": "not found"}), 404
        can_retry_generation = (
            st["stage"] == "ready"
            or (st["stage"] == "error" and st.get("generation_params"))
        )
        if not can_retry_generation:
            return jsonify({"error": "not ready"}), 400
        pdf_path = st["pdf_path"]
        out_path = st["output_path"]
        narration = list(st.get("narration", []))
        stored_llm_cfg = dict(st.get("llm_cfg") or {})

    try:
        clip_durs = [float(x) for x in (data.get("clip_durations") or [])]
    except Exception:
        clip_durs = []
    subtitle_mode = data.get("subtitle_mode", "none")
    if subtitle_mode not in ("none", "srt", "burn", "burn_bilingual"):
        subtitle_mode = "none"
    llm_cfg = {
        "provider": str(data.get("llm_provider") or
                        stored_llm_cfg.get("provider") or "openai").strip().lower(),
        "base_url": str(data.get("llm_base_url") or
                        stored_llm_cfg.get("base_url") or "").strip(),
        "api_key": str(data.get("llm_api_key") or
                       stored_llm_cfg.get("api_key") or "").strip(),
        "model": str(data.get("llm_model") or
                     stored_llm_cfg.get("model") or "").strip(),
    }
    if llm_cfg["provider"] not in ("openai", "nvidia"):
        llm_cfg["provider"] = "openai"
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
        "subtitle_mode": subtitle_mode,
        "subtitle_zh_color": data.get("subtitle_zh_color", "#66FF7A"),
        "subtitle_en_color": data.get("subtitle_en_color", "#FFFFFF"),
        "subtitle_outline_color": data.get("subtitle_outline_color", "#101010"),
        "llm_cfg": llm_cfg,
        "title_card_style": (data.get("title_card_style", "classic")
                             if data.get("title_card_style", "classic") in
                             ("classic", "custom") else "classic"),
        "title_font_sizes": _title_font_sizes(data),
        "title": data.get("title", "大众电影"),
        "subtitle": data.get("subtitle", ""),
        "feature": data.get("feature", ""),
        "feature2": data.get("feature2", ""),
        "feature3": data.get("feature3", ""),
        "tagline": data.get("tagline", ""),
        "voice": data.get("voice", "zh-CN-YunxiNeural"),
        "rate": data.get("rate", "+6%"),
    }
    update_task(
        tid,
        stage="generating",
        progress=0.0,
        message="开始生成视频（复用已提取文字，不会重新执行 OCR）",
        output_ready=False,
        srt_ready=False,
        generation_params=params,
    )
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
    import importlib.util
    print("=" * 50, flush=True)
    print("AI PDF解说视频生成器 启动自检", flush=True)
    ff = shutil.which("ffmpeg")
    print(f"  ffmpeg : {'OK ' + ff if ff else '缺失! 请安装 ffmpeg 并加入 PATH'}", flush=True)
    fp = shutil.which("ffprobe")
    print(f"  ffprobe: {'OK ' + fp if fp else '缺失! 请安装 ffmpeg(含 ffprobe)'}", flush=True)
    for mod in ("flask", "fitz", "PIL", "edge_tts", "easyocr",
                "rapidocr_onnxruntime", "paddleocr", "paddle"):
        try:
            ok = importlib.util.find_spec(mod) is not None
            print(f"  {mod:8s}: {'OK' if ok else '未安装'}", flush=True)
        except Exception as e:
            print(f"  {mod:8s}: 检查失败! {e}", flush=True)
    print("=" * 50, flush=True)


if __name__ == "__main__":
    _preflight()
    print("启动服务: http://127.0.0.1:5005", flush=True)
    print("（若浏览器打不开，确认本机防火墙未拦截 5005 端口）", flush=True)
    app.run(host="127.0.0.1", port=5005, debug=False, threaded=True)

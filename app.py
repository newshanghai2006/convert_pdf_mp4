#!/usr/bin/env python3
"""
AI PDF解说视频生成器（《大众电影》式杂志）本地 Web 应用。
运行: py -3.14 app.py  然后浏览器打开 http://127.0.0.1:5006

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
import hashlib
import hmac
import shutil
import secrets
import threading

from flask import Flask, request, jsonify, send_file, Response, g
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix

from index_html import INDEX_HTML
from task_store import TaskStore

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(BASE_DIR, "font.ttf")
OCR_WORKER = os.path.join(BASE_DIR, "_ocr_worker.py")
UPLOAD_DIR = os.path.join(BASE_DIR, "tasks")
os.makedirs(UPLOAD_DIR, exist_ok=True)
TASK_DB_PATH = os.path.join(UPLOAD_DIR, "tasks.db")


def _positive_int_env(name, default):
    try:
        return max(1, int(os.environ.get(name, str(default))))
    except (TypeError, ValueError):
        return default


def _load_auth_secret():
    configured = os.environ.get("MK_DZDY_AUTH_SECRET", "").encode("utf-8")
    if len(configured) >= 32:
        return hashlib.sha256(configured).digest()
    secret_path = os.path.join(UPLOAD_DIR, ".auth_secret")
    try:
        with open(secret_path, "rb") as f:
            existing = f.read()
        if len(existing) >= 32:
            return existing[:32]
    except FileNotFoundError:
        pass
    generated = secrets.token_bytes(32)
    try:
        fd = os.open(secret_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(generated)
        return generated
    except FileExistsError:
        with open(secret_path, "rb") as f:
            return f.read(32)


app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
MAX_UPLOAD_MB = _positive_int_env("MK_DZDY_MAX_UPLOAD_MB", 512)
MAX_ACTIVE_TASKS = _positive_int_env("MK_DZDY_MAX_ACTIVE_TASKS", 2)
AUTH_COOKIE_DAYS = _positive_int_env("MK_DZDY_AUTH_COOKIE_DAYS", 30)
ASSET_TICKET_HOURS = _positive_int_env("MK_DZDY_ASSET_TICKET_HOURS", 24)
AUTH_COOKIE_NAME = "mk_dzdy_owner"
AUTH_SECRET = _load_auth_secret()
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024


@app.after_request
def _security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Vary"] = "Authorization, Cookie"
    owner_hash = getattr(g, "issue_owner_cookie", None)
    if owner_hash:
        expires = int(time.time()) + AUTH_COOKIE_DAYS * 86400
        payload = f"{owner_hash}.{expires}"
        signature = hmac.new(
            AUTH_SECRET, payload.encode("ascii"), hashlib.sha256).hexdigest()
        response.set_cookie(
            AUTH_COOKIE_NAME, f"{payload}.{signature}",
            max_age=AUTH_COOKIE_DAYS * 86400, httponly=True,
            secure=request.is_secure, samesite="Strict", path="/")
    return response


def _pipeline():
    import pipeline
    return pipeline

VOICES = [
    ("zh-CN-YunyangNeural", "云扬（男·新闻）"),
    ("zh-CN-YunxiNeural", "云希（男声）"),
    ("zh-CN-XiaoxiaoNeural", "晓晓（女声）"),
    ("zh-CN-XiaoyiNeural", "晓伊（女声）"),
    ("zh-CN-liaoning-XiaobeiNeural", "辽宁晓蓓（女）"),
    ("zh-CN-shaanxi-XiaoniNeural", "陕西小妮（女）"),
]
RATES = ["+0%", "+6%", "+12%", "-10%", "-20%"]
VOICE_LABELS = dict(VOICES)

# 任务状态  task_id -> dict
TASKS = {}
TASKS_LOCK = threading.Lock()
TITLE_PREVIEW_LOCK = threading.Lock()
TASK_STORE = TaskStore(TASK_DB_PATH)
TASK_STORE.mark_interrupted_tasks()
CLIENT_TOKEN_RE = re.compile(r"^[0-9a-fA-F]{64}$")
TERMINAL_STAGES = {"ready", "done", "error", "cancelled"}


class TaskCancelled(Exception):
    pass


def _request_owner_hash():
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if CLIENT_TOKEN_RE.fullmatch(token):
            owner_hash = hashlib.sha256(
                token.lower().encode("ascii")).hexdigest()
            g.issue_owner_cookie = owner_hash
            return owner_hash
    cookie = request.cookies.get(AUTH_COOKIE_NAME, "")
    parts = cookie.split(".")
    if len(parts) != 3 or not re.fullmatch(r"[0-9a-f]{64}", parts[0]):
        return None
    owner_hash, expires_text, supplied_signature = parts
    try:
        expires = int(expires_text)
    except ValueError:
        return None
    if expires < int(time.time()):
        return None
    payload = f"{owner_hash}.{expires}"
    expected_signature = hmac.new(
        AUTH_SECRET, payload.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_signature, supplied_signature):
        return None
    return owner_hash


def _require_owner():
    owner_hash = _request_owner_hash()
    if not owner_hash:
        return None, (jsonify({"error": "需要有效的客户端恢复密钥"}), 401)
    TASK_STORE.ensure_owner(owner_hash)
    return owner_hash, None


def _create_asset_ticket(tid, owner_hash):
    expires = int(time.time()) + ASSET_TICKET_HOURS * 3600
    payload = f"asset:{tid}:{owner_hash}:{expires}"
    signature = hmac.new(
        AUTH_SECRET, payload.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{expires}.{signature}"


def _owner_from_asset_ticket(tid, ticket):
    parts = str(ticket or "").split(".")
    if len(parts) != 2 or not re.fullmatch(r"[0-9a-f]{64}", parts[1]):
        return None
    try:
        expires = int(parts[0])
    except ValueError:
        return None
    if expires < int(time.time()):
        return None
    record = TASK_STORE.get_task(tid)
    if not record:
        return None
    owner_hash = record["owner_hash"]
    payload = f"asset:{tid}:{owner_hash}:{expires}"
    expected = hmac.new(
        AUTH_SECRET, payload.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, parts[1]):
        return None
    return owner_hash


def _get_download_task(tid):
    owner_hash = _request_owner_hash()
    if owner_hash:
        st = _get_owned_task(tid, owner_hash)
        if st:
            return st
    ticket_owner = _owner_from_asset_ticket(tid, request.args.get("ticket"))
    if not ticket_owner:
        return None
    return _get_owned_task(tid, ticket_owner)


def _task_snapshot(st):
    keys = (
        "stage", "progress", "message", "pdf_path", "output_path",
        "narration", "clips", "page_count", "srt_ready", "srt_path",
        "output_ready", "page_texts", "fallback_narration",
        "pages_per_clip", "ocr_engine", "compact_ocr_text", "page_range",
        "file_name",
    )
    snap = {key: st.get(key) for key in keys if key in st}
    generation_params = st.get("generation_params") or {}
    if generation_params:
        snap["generation_params"] = {
            "voice": generation_params.get("voice", ""),
            "rate": generation_params.get("rate", ""),
        }
    return snap


def _persist_task(tid):
    with TASKS_LOCK:
        st = TASKS.get(tid)
        if not st:
            return
        snapshot = _task_snapshot(st)
    TASK_STORE.update_task(tid, snapshot)


def _get_owned_task(tid, owner_hash):
    if not tid:
        return None
    with TASKS_LOCK:
        st = TASKS.get(tid)
        if st and st.get("owner_hash") == owner_hash:
            return st
        if st:
            return None
    record = TASK_STORE.get_task(tid, owner_hash)
    if not record:
        return None
    restored = dict(record["state"])
    restored.update({
        "owner_hash": owner_hash,
        "cancel_requested": record["cancel_requested"],
        "delete_pending": record["delete_pending"],
    })
    with TASKS_LOCK:
        TASKS.setdefault(tid, restored)
        return TASKS[tid]


def _task_cancelled(tid):
    with TASKS_LOCK:
        st = TASKS.get(tid)
        if st and st.get("cancel_requested"):
            return True
    record = TASK_STORE.get_task(tid)
    return bool(record and record["cancel_requested"])


def _safe_task_dir(tid):
    root = os.path.realpath(UPLOAD_DIR)
    path = os.path.realpath(os.path.join(root, tid))
    if os.path.dirname(path) != root:
        raise ValueError("invalid task path")
    return path


def _delete_task_files(tid):
    path = _safe_task_dir(tid)
    if os.path.isdir(path):
        shutil.rmtree(path)


def _finalize_pending_delete(tid):
    with TASKS_LOCK:
        st = TASKS.get(tid)
        delete_pending = bool(st and st.get("delete_pending"))
        owner_hash = st.get("owner_hash") if st else None
    if not delete_pending:
        record = TASK_STORE.get_task(tid)
        delete_pending = bool(record and record["delete_pending"])
        owner_hash = owner_hash or (record["owner_hash"] if record else None)
    if not delete_pending:
        return
    with TASKS_LOCK:
        TASKS.pop(tid, None)
    TASK_STORE.delete_task(tid, owner_hash)
    try:
        _delete_task_files(tid)
    except OSError as exc:
        print(f"任务 {tid} 文件清理失败: {exc}", flush=True)


def _bounded_float(data, key, default, low, high):
    try:
        value = float(data.get(key, default))
    except Exception:
        value = default
    return max(low, min(high, value))


def _bounded_rpm(value, default=0.0):
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = default
    return max(0.0, min(6000.0, value))


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
        st = TASKS.get(tid)
        if not st:
            return
        st.update(kw)
    _persist_task(tid)


# ---------------------------------------------------------------------------
# 后台：提取文字
# ---------------------------------------------------------------------------
def do_prepare(tid, pdf_path, pages_per_clip, use_ocr, ocr_lang="ch_sim",
               page_range="", ai_ocr_cfg=None, ocr_engine="easyocr"):
    def cb(stage, pct, msg):
        if _task_cancelled(tid):
            raise TaskCancelled()
        update_task(tid, stage=stage, progress=pct, message=msg)

    try:
        if _task_cancelled(tid):
            raise TaskCancelled()
        llm_cfg = TASKS[tid].get("llm_cfg") or {}
        ai_ocr_cfg = ai_ocr_cfg or TASKS[tid].get("ai_ocr_cfg") or {}
        compact_ocr_text = bool(TASKS[tid].get("compact_ocr_text"))
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
        fallback_clips = p.group_into_clips(pages, pages_per_clip)
        if compact_ocr_text:
            fallback_clips = [
                re.sub(r"[\s\u200b\ufeff]+", "", text)
                for text in fallback_clips
            ]
        clips = list(fallback_clips)
        update_task(tid, page_texts=pages,
                    fallback_narration=fallback_clips,
                    pages_per_clip=pages_per_clip)
        ai_note = ""
        if llm_cfg.get("enabled"):
            clips, ai_note = p.generate_ai_narration(
                pages, pages_per_clip, clips, llm_cfg, cb)
        ready_msg = "文字提取完成，可编辑旁白后生成"
        if llm_cfg.get("enabled"):
            ready_msg = f"文字提取完成，{ai_note or 'AI 旁白已生成'}，可编辑后生成视频"
        update_task(tid, stage="ready", progress=1.0,
                    message=ready_msg,
                    narration=clips, clips=len(clips),
                    page_count=len(pages))
    except TaskCancelled:
        update_task(tid, stage="cancelled", message="任务已取消")
    except Exception as e:
        update_task(tid, stage="error", message=f"提取失败: {e}")
    finally:
        _finalize_pending_delete(tid)


def do_regenerate_narration(tid, pages, pages_per_clip, fallback_clips, llm_cfg):
    def cb(stage, pct, msg):
        if _task_cancelled(tid):
            raise TaskCancelled()
        update_task(tid, stage=stage, progress=pct, message=msg)

    try:
        if _task_cancelled(tid):
            raise TaskCancelled()
        clips, ai_note = _pipeline().generate_ai_narration(
            pages, pages_per_clip, fallback_clips, llm_cfg, cb)
        message = ai_note or "AI 旁白已重新生成"
        update_task(tid, stage="ready", progress=1.0, message=message,
                    narration=clips, clips=len(clips), llm_cfg=llm_cfg)
    except TaskCancelled:
        update_task(tid, stage="cancelled", message="任务已取消")
    except Exception as e:
        update_task(tid, stage="ready", progress=1.0,
                    message=f"AI 旁白重新生成失败：{e}；已保留当前旁白")
    finally:
        _finalize_pending_delete(tid)


# ---------------------------------------------------------------------------
# 后台：生成视频
# ---------------------------------------------------------------------------
def do_generate(tid, pdf_path, params, narration):
    def cb(stage, pct, msg):
        if _task_cancelled(tid):
            raise TaskCancelled()
        update_task(tid, stage=stage, progress=pct, message=msg)

    try:
        if _task_cancelled(tid):
            raise TaskCancelled()
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
    except TaskCancelled:
        update_task(tid, stage="cancelled", message="任务已取消")
    except Exception as e:
        update_task(tid, stage="error", message=f"生成失败: {e}")
    finally:
        _finalize_pending_delete(tid)


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    nonce = secrets.token_urlsafe(18)
    html = INDEX_HTML.replace("<script>", f'<script nonce="{nonce}">', 1)
    response = Response(html, mimetype="text/html")
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        f"script-src 'self' 'nonce-{nonce}'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; media-src 'self' blob:; "
        "connect-src 'self'; object-src 'none'; base-uri 'none'; "
        "frame-ancestors 'none'; form-action 'self'")
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.errorhandler(413)
def request_too_large(_error):
    return jsonify({"error": f"上传文件超过服务器限制（{MAX_UPLOAD_MB} MB）"}), 413


@app.route("/api/voices")
def api_voices():
    return jsonify({"voices": VOICES, "rates": RATES})


def _clean_owner_settings(data):
    provider = str(data.get("llm_provider") or "openai").strip().lower()
    if provider not in ("openai", "nvidia", "sensenova"):
        provider = "openai"
    try:
        target_chars = int(data.get("narration_target_chars", 200))
    except (TypeError, ValueError):
        target_chars = 200
    return {
        "llm_provider": provider,
        "llm_base_url": str(data.get("llm_base_url") or "").strip()[:500],
        "llm_model": str(data.get("llm_model") or "").strip()[:200],
        "llm_rpm": _bounded_rpm(data.get("llm_rpm", 0)),
        "narration_target_chars": max(40, min(400, target_chars)),
        "use_ai_narration": bool(data.get("use_ai_narration", False)),
        "use_ai_ocr": bool(data.get("use_ai_ocr", False)),
    }


@app.route("/api/client/settings", methods=["GET", "PUT"])
def api_client_settings():
    owner_hash, error = _require_owner()
    if error:
        return error
    if request.method == "GET":
        return jsonify({"settings": TASK_STORE.get_owner_settings(owner_hash)})
    data = request.get_json(force=True)
    settings = _clean_owner_settings(data)
    TASK_STORE.save_owner_settings(owner_hash, settings)
    return jsonify({"ok": True, "settings": settings})


@app.route("/api/tasks")
def api_tasks():
    owner_hash, error = _require_owner()
    if error:
        return error
    items = []
    for record in TASK_STORE.list_tasks(owner_hash):
        st = record["state"]
        items.append({
            "task_id": record["task_id"],
            "stage": st.get("stage", "error"),
            "progress": st.get("progress", 0.0),
            "message": st.get("message", ""),
            "file_name": st.get("file_name", "PDF 任务"),
            "page_count": st.get("page_count", 0),
            "output_ready": bool(st.get("output_ready")),
            "srt_ready": bool(st.get("srt_ready")),
            "cancel_requested": record["cancel_requested"],
            "delete_pending": record["delete_pending"],
            "phase": "generate" if st.get("generation_params") else "prepare",
            "created_at": record["created_at"],
            "updated_at": record["updated_at"],
        })
    return jsonify({"tasks": items})


@app.route("/api/tasks/<tid>/cancel", methods=["POST"])
def api_cancel_task(tid):
    owner_hash, error = _require_owner()
    if error:
        return error
    st = _get_owned_task(tid, owner_hash)
    if not st:
        return jsonify({"error": "not found"}), 404
    if st.get("stage") in TERMINAL_STAGES:
        return jsonify({"error": "任务当前不在运行"}), 400
    with TASKS_LOCK:
        st["cancel_requested"] = True
        st["message"] = "正在取消任务，请等待当前步骤结束"
    _persist_task(tid)
    TASK_STORE.set_flags(tid, owner_hash, cancel=True)
    return jsonify({"ok": True})


@app.route("/api/tasks/<tid>", methods=["DELETE"])
def api_delete_task(tid):
    owner_hash, error = _require_owner()
    if error:
        return error
    st = _get_owned_task(tid, owner_hash)
    if not st:
        return jsonify({"error": "not found"}), 404
    if st.get("stage") not in TERMINAL_STAGES:
        with TASKS_LOCK:
            st["cancel_requested"] = True
            st["delete_pending"] = True
            st["message"] = "正在取消并删除任务"
        _persist_task(tid)
        TASK_STORE.set_flags(tid, owner_hash, cancel=True, delete=True)
        return jsonify({"ok": True, "pending": True}), 202
    try:
        _delete_task_files(tid)
    except OSError as exc:
        return jsonify({"error": f"任务文件删除失败: {exc}"}), 500
    with TASKS_LOCK:
        TASKS.pop(tid, None)
    TASK_STORE.delete_task(tid, owner_hash)
    return jsonify({"ok": True, "pending": False})


@app.route("/api/title_preview", methods=["POST"])
def api_title_preview():
    owner_hash, error = _require_owner()
    if error:
        return error
    data = request.get_json(force=True)
    tid = data.get("task_id")
    st = _get_owned_task(tid, owner_hash)
    if not st:
        return jsonify({"error": "task not found"}), 404
    with TASKS_LOCK:
        pdf_path = st.get("pdf_path")
    if not pdf_path or not os.path.exists(pdf_path):
        return jsonify({"error": "pdf not found"}), 404

    style = data.get("title_card_style", "classic")
    if style not in ("classic", "custom", "cinematic"):
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
    owner_hash, error = _require_owner()
    if error:
        return error
    active_count = sum(
        1 for record in TASK_STORE.list_tasks(owner_hash, limit=1000)
        if record["state"].get("stage") not in TERMINAL_STAGES)
    if active_count >= MAX_ACTIVE_TASKS:
        return jsonify({
            "error": f"当前已有 {active_count} 个运行中任务，请等待或取消后再提交"
        }), 429
    if "pdf" not in request.files:
        return jsonify({"error": "no pdf"}), 400
    f = request.files["pdf"]
    if not f.filename:
        return jsonify({"error": "empty"}), 400
    pages_per_clip = int(request.form.get("pages_per_clip", 2))
    use_ocr = request.form.get("use_ocr", "true").lower() == "true"
    use_ai_narration = request.form.get("use_ai_narration", "false").lower() == "true"
    use_ai_ocr = request.form.get("use_ai_ocr", "false").lower() == "true"
    compact_ocr_text = request.form.get(
        "compact_ocr_text", "false").lower() == "true"
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
        "llm_rpm": _bounded_rpm(request.form.get("llm_rpm", 0)),
        "narration_target_chars": narration_target_chars,
    }
    if llm_common["provider"] not in ("openai", "nvidia", "sensenova"):
        llm_common["provider"] = "openai"
    llm_cfg = dict(llm_common, enabled=use_ai_narration)
    ai_ocr_cfg = dict(llm_common, enabled=use_ai_ocr)
    page_range = request.form.get("page_range", "").strip()
    ocr_lang = request.form.get("ocr_lang", "ch_sim").strip()
    if ocr_lang not in ("ch_sim", "ch_tra"):
        ocr_lang = "ch_sim"
    ocr_engine = request.form.get("ocr_engine", "easyocr").strip().lower()
    if ocr_engine not in ("easyocr", "rapidocr", "paddleocr"):
        ocr_engine = "easyocr"

    tid = uuid.uuid4().hex
    work = os.path.join(UPLOAD_DIR, tid)
    os.makedirs(work, exist_ok=True)
    fname = secure_filename(f.filename) or "input.pdf"
    pdf_path = os.path.join(work, fname)
    f.save(pdf_path)
    out_path = os.path.join(work, "output.mp4")

    with TASKS_LOCK:
        TASKS[tid] = {
            "stage": "preparing", "progress": 0.0,
            "message": "正在解析页码选择" if page_range else "开始提取文字",
            "pdf_path": pdf_path,
            "output_path": out_path, "output_ready": False,
            "narration": [], "clips": 0, "page_count": 0,
            "srt_ready": False, "srt_path": "",
            "llm_cfg": llm_cfg,
            "ai_ocr_cfg": ai_ocr_cfg,
            "ocr_engine": ocr_engine,
            "compact_ocr_text": compact_ocr_text,
            "page_range": page_range,
            "file_name": os.path.basename(f.filename)[:255] or fname,
            "owner_hash": owner_hash,
            "cancel_requested": False,
            "delete_pending": False,
        }
        initial_state = _task_snapshot(TASKS[tid])
    TASK_STORE.create_task(tid, owner_hash, initial_state)
    t = threading.Thread(target=do_prepare,
                         args=(tid, pdf_path, pages_per_clip, use_ocr, ocr_lang,
                               page_range, ai_ocr_cfg, ocr_engine))
    t.daemon = True
    t.start()
    return jsonify({"task_id": tid})


@app.route("/api/status")
def api_status():
    owner_hash, error = _require_owner()
    if error:
        return error
    tid = request.args.get("task")
    st = _get_owned_task(tid, owner_hash)
    if not st:
        return jsonify({"error": "not found"}), 404
    with TASKS_LOCK:
        # 复制可序列化字段（去掉大对象）
        generation_params = st.get("generation_params") or {}
        voice = generation_params.get("voice", "")
        asset_ticket = (_create_asset_ticket(tid, owner_hash)
                        if st.get("output_ready") else "")
        return jsonify({
            "stage": st["stage"], "progress": st["progress"],
            "message": st["message"], "clips": st["clips"],
            "page_count": st["page_count"],
            "narration": st.get("narration", []),
            "output_ready": st["output_ready"],
            "srt_ready": st.get("srt_ready", False),
            "voice": voice,
            "voice_label": VOICE_LABELS.get(voice, ""),
            "rate": generation_params.get("rate", ""),
            "cancel_requested": bool(st.get("cancel_requested")),
            "delete_pending": bool(st.get("delete_pending")),
            "asset_ticket": asset_ticket,
        })


@app.route("/api/save_narration", methods=["POST"])
def api_save_narration():
    owner_hash, error = _require_owner()
    if error:
        return error
    data = request.get_json(force=True)
    tid = data.get("task_id")
    idx = int(data.get("idx", -1))
    text = data.get("text", "")
    st = _get_owned_task(tid, owner_hash)
    if not st:
        return jsonify({"error": "not found"}), 404
    with TASKS_LOCK:
        narration = st.get("narration", [])
        if idx < 0 or idx >= len(narration):
            return jsonify({"error": "bad idx"}), 400
        narration[idx] = text
        st["narration"] = narration
    _persist_task(tid)
    return jsonify({"ok": True})


@app.route("/api/regenerate_narration", methods=["POST"])
def api_regenerate_narration():
    owner_hash, error = _require_owner()
    if error:
        return error
    data = request.get_json(force=True)
    tid = data.get("task_id")
    st = _get_owned_task(tid, owner_hash)
    if not st:
        return jsonify({"error": "not found"}), 404
    with TASKS_LOCK:
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
        "llm_rpm": _bounded_rpm(
            data.get("llm_rpm") if data.get("llm_rpm") is not None
            else stored_cfg.get("llm_rpm", 0)),
        "narration_target_chars": max(40, min(400, target_chars)),
    }
    if llm_cfg["provider"] not in ("openai", "nvidia", "sensenova"):
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
    owner_hash, error = _require_owner()
    if error:
        return error
    data = request.get_json(force=True)
    tid = data.get("task_id")
    st = _get_owned_task(tid, owner_hash)
    if not st:
        return jsonify({"error": "not found"}), 404
    with TASKS_LOCK:
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
        "llm_rpm": _bounded_rpm(
            data.get("llm_rpm") if data.get("llm_rpm") is not None
            else stored_llm_cfg.get("llm_rpm", 0)),
    }
    if llm_cfg["provider"] not in ("openai", "nvidia", "sensenova"):
        llm_cfg["provider"] = "openai"
    voice = str(data.get("voice") or "zh-CN-YunyangNeural").strip()
    rate = str(data.get("rate") or "+0%").strip()
    if voice not in VOICE_LABELS:
        return jsonify({"error": f"不支持的配音声音: {voice}"}), 400
    if rate not in RATES:
        return jsonify({"error": f"不支持的语速: {rate}"}), 400
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
                             ("classic", "custom", "cinematic") else "classic"),
        "title_font_sizes": _title_font_sizes(data),
        "title": data.get("title", "大众电影"),
        "subtitle": data.get("subtitle", ""),
        "feature": data.get("feature", ""),
        "feature2": data.get("feature2", ""),
        "feature3": data.get("feature3", ""),
        "tagline": data.get("tagline", ""),
        "voice": voice,
        "rate": rate,
    }
    update_task(
        tid,
        stage="generating",
        progress=0.0,
        message=(f"开始生成视频：{VOICE_LABELS[voice]}，语速 {rate}"
                 "（复用已提取文字，不会重新执行 OCR）"),
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
    st = _get_download_task(tid)
    if not st:
        return jsonify({"error": "需要有效的客户端身份或下载票据"}), 401
    with TASKS_LOCK:
        if not st.get("output_ready"):
            return jsonify({"error": "not ready"}), 404
        out_path = st["output_path"]
    as_attachment = request.args.get("download") == "1"
    return send_file(out_path, mimetype="video/mp4",
                     as_attachment=as_attachment,
                     download_name="AI_PDF_video.mp4",
                     conditional=True)


@app.route("/api/download_srt/<tid>")
def api_download_srt(tid):
    st = _get_download_task(tid)
    if not st:
        return jsonify({"error": "需要有效的客户端身份或下载票据"}), 401
    with TASKS_LOCK:
        if not st.get("srt_ready"):
            return jsonify({"error": "not ready"}), 404
        srt_path = st.get("srt_path", "")
    if not srt_path or not os.path.exists(srt_path):
        return jsonify({"error": "not found"}), 404
    return send_file(srt_path, mimetype="application/x-subrip",
                     as_attachment=True,
                     download_name="AI_PDF_subtitles.srt",
                     conditional=True)


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
    print("启动服务: http://127.0.0.1:5006", flush=True)
    print("（若浏览器打不开，确认本机防火墙未拦截 5006 端口）", flush=True)
    app.run(host="127.0.0.1", port=5006, debug=False, threaded=True)

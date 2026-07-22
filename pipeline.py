#!/usr/bin/env python3
"""
参数化 <<大众电影>> PDF -> 解说视频 管线。
可被 Web 应用 (app.py) 调用，也支持命令行直接跑。

流程:
  PDF --(fitz)--> 每页图片
       --(每 pages_per_clip 页并排)--> 内容帧
       --(封面+标题)--> 标题卡
       --(ffmpeg loop)--> 静音视频 (封面 title_duration + 片段*clip_duration)
       --(edge-tts)--> 每段旁白 -> 调整到 clip_duration -> 合成音轨
       --(mux)--> 最终 MP4
"""
import os
import sys
import io
import re
import json
import base64
import time
import math
import asyncio
import subprocess
from urllib import request as urlrequest
from urllib import error as urlerror

import fitz
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import edge_tts

W, H = 1920, 1080   # 默认输出尺寸（16:9 1080p）；实际由参数计算，见 compute_dimensions


def _even(x):
    x = int(round(x))
    return x if x % 2 == 0 else x + 1


def compute_dimensions(aspect="16:9", custom_w=16, custom_h=9, quality=1080):
    """
    由「宽高比 + 清晰度」算出输出像素尺寸 (W, H)，保证为偶数（H.264 要求）。
    aspect: "16:9" / "9:16" / "4:3" / "1:1" / "custom"
    quality: 短边像素（1080 / 720 / 480 …）。
      - 横屏(宽>=高): 高=quality，宽按比例；竖屏(高>宽): 宽=quality，高按比例。
    """
    try:
        if aspect == "custom":
            aw, ah = float(custom_w), float(custom_h)
        else:
            aw, ah = (float(x) for x in aspect.split(":"))
        if aw <= 0 or ah <= 0:
            raise ValueError
    except Exception:
        aw, ah = 16.0, 9.0
    q = max(160, min(2160, int(quality)))     # 合理范围，防止极端值
    if aw >= ah:                              # 横屏 / 方形
        h = q
        w = q * aw / ah
    else:                                     # 竖屏
        w = q
        h = q * ah / aw
    w, h = _even(w), _even(h)
    # 上限保护，避免超大分辨率把机器拖垮
    if max(w, h) > 3840:
        s = 3840 / max(w, h)
        w, h = _even(w * s), _even(h * s)
    return w, h


# ----------------------------------------------------------------------------
# 基础工具
# ----------------------------------------------------------------------------
def run_ffmpeg(cmd, desc="ffmpeg"):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ERROR in {desc}:")
        print(f"  {result.stderr[-800:]}")
        return False
    return True


def get_duration(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True
    )
    return float(result.stdout.strip())


# ----------------------------------------------------------------------------
# TTS (edge-tts)
# ----------------------------------------------------------------------------
def generate_tts_edge(text, output_wav, voice, rate):
    if not text or not text.strip():
        # 空旁白 -> 生成一小段静音
        cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
               "-t", "0.1", "-c:a", "pcm_s16le", output_wav]
        return run_ffmpeg(cmd, "null wav")
    tmp_mp3 = output_wav + ".mp3"
    last_err = ""
    for attempt in range(1, 4):
        try:
            async def _run():
                comm = edge_tts.Communicate(text, voice, rate=rate)
                await comm.save(tmp_mp3)
            asyncio.run(_run())
            if os.path.exists(tmp_mp3) and os.path.getsize(tmp_mp3) > 500:
                break
        except Exception as e:
            last_err = str(e)
            print(f"    edge-tts attempt {attempt} failed: {e}")
            time.sleep(2)
    else:
        raise RuntimeError(
            "TTS 连接微软语音服务失败（edge-tts 需能访问 speech.platform.bing.com）。"
            "请检查网络 / 防火墙 / 代理，确认能联网后重试。原始错误: " + last_err)
    cmd = ["ffmpeg", "-y", "-i", tmp_mp3,
           "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", output_wav]
    ok = run_ffmpeg(cmd, "mp3->wav")
    try:
        os.remove(tmp_mp3)
    except OSError:
        pass
    return ok


# ----------------------------------------------------------------------------
# 页码选择：把 "1~10,15~20,30" 解析为页索引，并抽取子 PDF
# ----------------------------------------------------------------------------
def parse_page_range(spec, N):
    """
    解析形如 "1~10,15~20,30" 的页码表达式，返回 0-based 页索引列表（按填写顺序、去重）。
    支持分隔符：, ，  区间符：~ ～ - －  页码为 1-based。越界忽略。
    spec 为空 / 无有效项 -> 返回全部页 [0..N-1]。
    """
    if not spec or not spec.strip():
        return list(range(N))
    s = (spec.replace("，", ",").replace("～", "~")
             .replace("－", "-").replace("—", "-").replace(" ", ""))
    result, seen = [], set()

    def add(idx):
        if 0 <= idx < N and idx not in seen:
            seen.add(idx)
            result.append(idx)

    for part in s.split(","):
        if not part:
            continue
        m = re.match(r"^(\d+)[-~](\d+)$", part)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if a > b:
                a, b = b, a
            for p in range(a, b + 1):
                add(p - 1)          # 1-based -> 0-based
        elif part.isdigit():
            add(int(part) - 1)
        # 其它非法片段静默忽略
    return result if result else list(range(N))


def build_selected_pdf(src_path, out_path, pages0):
    """按 0-based 页索引（保持顺序）抽取子 PDF 到 out_path，返回 out_path。"""
    src = fitz.open(src_path)
    new = fitz.open()
    for p in pages0:
        if 0 <= p < src.page_count:
            new.insert_pdf(src, from_page=p, to_page=p)
    new.save(out_path)
    new.close()
    src.close()
    return out_path


def make_working_pdf(src_path, out_path, spec):
    """
    根据页码表达式产出“实际参与制作”的 PDF：
      - spec 选中的是全部页 -> 直接返回原 PDF 路径（不复制）。
      - 选中子集 -> 抽成子 PDF 返回其路径。
    返回 (working_pdf_path, selected_count)。
    """
    src = fitz.open(src_path)
    N = src.page_count
    src.close()
    pages0 = parse_page_range(spec, N)
    if len(pages0) == N and pages0 == list(range(N)):
        return src_path, N
    build_selected_pdf(src_path, out_path, pages0)
    return out_path, len(pages0)


# ----------------------------------------------------------------------------
# 文字提取：文字层优先，否则 OCR (子进程分批，保护主进程)
# ----------------------------------------------------------------------------
def extract_page_texts(pdf_path, use_ocr=False, progress_cb=None,
                       ocr_worker=None, py_exe=None, ocr_lang="ch_sim",
                       probe_ocr=False, ai_ocr_cfg=None,
                       ocr_engine="easyocr"):
    """返回 list[str]，每页一段文字。文字层优先；若全空且 use_ocr，则跑 OCR。
    ocr_lang: 'ch_sim'(简体) 或 'ch_tra'(繁体)，均搭配英文。"""
    doc = fitz.open(pdf_path)
    N = doc.page_count
    pages = []

    # probe_ocr=False 时走更接近原版的全量提取逻辑。
    if use_ocr and probe_ocr:
        probe_n = min(5, N)
        probe = []
        for i in range(probe_n):
            probe.append(doc[i].get_text().strip())
            if progress_cb:
                progress_cb("extract", (i + 1) / max(1, probe_n),
                            f"正在检查文字层 {i + 1}/{probe_n}")
        has_text = any(p.strip() for p in probe)
        if not has_text:
            doc.close()
            if progress_cb:
                progress_cb("ocr", 0.0, "未检测到文字层，开始 OCR")
            out_txt = os.path.join(os.path.dirname(pdf_path), "ocr.txt")
            if os.path.exists(out_txt):
                os.remove(out_txt)
            ocr_pdf_subprocess(pdf_path, out_txt, progress_cb, ocr_worker, py_exe,
                               ocr_lang, ocr_engine)
            return parse_ocr_txt(out_txt, N)

        # 样本里有文字层，再做全量提取
        if progress_cb:
            progress_cb("extract", 0.1, "检测到文字层，正在完整提取")
        doc.close()
        doc = fitz.open(pdf_path)
        for i in range(N):
            pages.append(doc[i].get_text().strip())
            if progress_cb and (i % max(1, N // 20) == 0 or i + 1 == N):
                progress_cb("extract", 0.1 + 0.9 * (i + 1) / max(1, N),
                            f"正在提取文字层 {i + 1}/{N}")
        doc.close()
        return pages

    for i in range(N):
        pages.append(doc[i].get_text().strip())
        if progress_cb and (i % max(1, N // 20) == 0 or i + 1 == N):
            progress_cb("extract", (i + 1) / max(1, N),
                        f"正在提取文字层 {i + 1}/{N}")
    doc.close()

    has_text = any(p.strip() for p in pages)
    if has_text:
        if progress_cb:
            progress_cb("extract", 1.0, f"检测到文字层，已提取 {N} 页")
        return pages

    if not use_ocr:
        if progress_cb:
            progress_cb("extract", 1.0, "未检测到文字层（纯图片），需启用 OCR")
        return pages

    if progress_cb:
        progress_cb("ai_ocr" if (ai_ocr_cfg or {}).get("enabled") else "ocr",
                    0.0, "未检测到文字层，开始 AI OCR" if
                    (ai_ocr_cfg or {}).get("enabled") else "未检测到文字层，开始 OCR")

    if (ai_ocr_cfg or {}).get("enabled"):
        return generate_ai_ocr(pdf_path, pages, ai_ocr_cfg, progress_cb)

    # OCR 结果放在任务自己的目录下（不再用进程 PID 命名的公共临时文件，
    # 否则同一 Flask 进程里并发的两个任务会写到同一个文件、互相污染）。
    out_txt = os.path.join(os.path.dirname(pdf_path), "ocr.txt")
    if os.path.exists(out_txt):
        os.remove(out_txt)
    ocr_pdf_subprocess(pdf_path, out_txt, progress_cb, ocr_worker, py_exe,
                       ocr_lang, ocr_engine)
    return parse_ocr_txt(out_txt, N)


def ocr_pdf_subprocess(pdf_path, out_txt, progress_cb, ocr_worker, py_exe,
                       ocr_lang="ch_sim", ocr_engine="easyocr"):
    """
    以子进程跑 OCR。一次子进程处理「所有剩余页」，把 torch/easyocr 的加载成本
    只付一次；子进程中途崩溃则重新拉起、从断点续跑。

    进度：子进程会把每页结果**即时**写入 out_txt，这里用 Popen + 轮询该文件，
    因此进度会随识别逐页刷新（不会像阻塞式那样一直卡在 0）。加载/下载模型阶段
    （还没有任何页完成时）会显示专门的提示。

    健壮性：若连续多次子进程都没有推进任何一页（例如 easyocr 环境损坏、
    模型下载失败/被墙、或某页永远卡死），不再无限重试，而是抛出明确错误，
    避免任务永远卡在“OCR 识别中”。
    """
    py_exe = py_exe or sys.executable
    if ocr_engine not in ("easyocr", "rapidocr", "paddleocr"):
        ocr_engine = "easyocr"
    N = fitz.open(pdf_path).page_count
    max_stalls = 3           # 连续无进展的最大次数
    stalls = 0
    last_err = ""
    err_log = out_txt + ".stderr.log"
    engine_names = {
        "easyocr": "EasyOCR",
        "rapidocr": "RapidOCR",
        "paddleocr": "PaddleOCR",
    }
    engine_label = engine_names.get(ocr_engine, "OCR")
    ocr_profiles = [
        {
            "OCR_RENDER_ZOOM": str(150 / 72.0),
            "OCR_CANVAS_SIZE": "1024",
            "OCR_MAG_RATIO": "1.0",
        },
        {
            "OCR_RENDER_ZOOM": str(120 / 72.0),
            "OCR_CANVAS_SIZE": "896",
            "OCR_MAG_RATIO": "1.0",
        },
    ]
    while True:
        done = count_ocr_pages(out_txt)
        if done >= N:
            break
        # 给足超时：按剩余页数估算（每页最多约 120s），至少 10 分钟。
        timeout = max(600, (N - done) * 120)
        deadline = time.time() + timeout
        # 用 Popen 非阻塞启动；stderr 落到日志文件，避免管道写满导致子进程卡死。
        profile = ocr_profiles[min(stalls, len(ocr_profiles) - 1)]
        env = os.environ.copy()
        env.update(profile)
        try:
            ef = open(err_log, "w", encoding="utf-8", errors="replace")
            proc = subprocess.Popen(
                [py_exe, ocr_worker, pdf_path, str(done), str(N), out_txt,
                 ocr_lang, ocr_engine],
                stdout=subprocess.DEVNULL, stderr=ef, text=True, env=env)
        except Exception as e:
            last_err = f"无法启动 OCR 子进程: {e}"
            print("  " + last_err)
            stalls += 1
            if stalls >= max_stalls:
                raise RuntimeError(last_err)
            continue

        # 轮询进度，直到子进程退出 / 卡死 / 超时。
        # 关键：单独设“无新页看门狗”——加载模型或识别单页在 STALL_SECONDS 内没有
        # 任何一页完成，就判定卡死并杀掉重试，避免整批超时（可能长达一小时）拖着不动。
        STALL_SECONDS = 300      # 5 分钟内必须出现新页，否则视为卡死
        killed = False
        t_start = time.time()
        seen = done
        t_last_advance = t_start
        while proc.poll() is None:
            cur = count_ocr_pages(out_txt)
            now = time.time()
            if cur > seen:
                seen = cur
                t_last_advance = now
            if progress_cb:
                if cur <= done:
                    el = int(now - t_start)
                    tip = f"正在加载 {engine_label} 模型并识别首页…（已 {el}s）"
                    if stalls > 0:
                        tip = (f"OCR 重试中（第 {stalls+1} 次，已 {el}s）"
                               f"{'；上次: ' + last_err[:80] if last_err else ''}")
                    progress_cb("ocr", cur / N, tip)
                else:
                    progress_cb("ocr", cur / N, f"OCR 识别中 {cur}/{N} 页")
            if now - t_last_advance > STALL_SECONDS:
                proc.kill()
                killed = True
                last_err = (f"{STALL_SECONDS}s 内无新页（疑似卡在模型加载/联网或某页），"
                            f"已终止并重试")
                print("  " + last_err)
                break
            if now > deadline:
                proc.kill()
                killed = True
                last_err = f"worker 超时（{int(timeout)}s）"
                print("  " + last_err)
                break
            time.sleep(2)
        try:
            proc.wait(timeout=30)
        except Exception:
            proc.kill()
        ef.close()
        rc = proc.returncode
        if not killed and rc not in (0, None):
            last_err = _summarize_err(_tail_file(err_log, 4000)) or \
                f"worker 异常退出（returncode={rc}）"
            if rc == 3221225477:
                last_err = "worker 异常退出（0xC0000005，Windows 原生库崩溃）"
            print(f"  OCR worker exit {rc}: {last_err}")

        new_done = count_ocr_pages(out_txt)
        if new_done <= done:                 # 本轮没有识别出任何新页
            stalls += 1
            if stalls >= max_stalls:
                hint = (f"常见原因：① {engine_label} 首次运行需要准备模型；"
                        f"② {engine_label} 依赖未安装或版本不兼容。")
                if "not enough memory" in last_err or "out of memory" in last_err.lower():
                    hint = ("内存不足：easyocr/torch 加载模型或识别大图时内存不够。"
                            "请关闭其它占内存的程序后重试，或调小 _ocr_worker.py 里的 "
                            "CANVAS_SIZE / RENDER_ZOOM。")
                raise RuntimeError(
                    f"OCR 连续 {max_stalls} 次未取得进展（已完成 {done}/{N} 页）。"
                    f"最后错误: {last_err or '子进程无输出'}。{hint}")
        else:
            stalls = 0
    if progress_cb:
        progress_cb("ocr", 1.0, f"OCR 完成 {N}/{N} 页")


def _tail_file(path, nchars):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read().strip()[-nchars:]
    except OSError:
        return ""


def _summarize_err(text):
    """从子进程 stderr 里挑出最有信息量的一行（异常类型行），去掉冗长堆栈。"""
    if not text:
        return ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for ln in reversed(lines):
        if ("Error" in ln or "error" in ln or "memory" in ln.lower()
                or "Exception" in ln):
            return ln[:300]
    return lines[-1][:300] if lines else ""






def count_ocr_pages(out_txt):
    if not os.path.exists(out_txt):
        return 0
    with open(out_txt, encoding="utf-8") as f:
        return len(re.findall(r"========== PAGE \d+", f.read()))


def parse_ocr_txt(out_txt, N):
    if not os.path.exists(out_txt):
        return [""] * N
    with open(out_txt, encoding="utf-8") as f:
        content = f.read()
    blocks = re.split(r"========== PAGE \d+ ==========", content)
    # blocks[0] 是头部，之后每段对应一页
    texts = []
    for b in blocks[1:N+1]:
        texts.append(b.strip())
    while len(texts) < N:
        texts.append("")
    return texts[:N]


def group_into_clips(page_texts, pages_per_clip):
    """把每页文字按 pages_per_clip 分组，得到每个片段的旁白候选。"""
    n = len(page_texts)
    clips = (n + pages_per_clip - 1) // pages_per_clip
    groups = []
    for c in range(clips):
        chunk = page_texts[c * pages_per_clip:(c + 1) * pages_per_clip]
        groups.append("\n".join(t for t in chunk if t.strip()))
    return groups


# ----------------------------------------------------------------------------
# 图像合成
# ----------------------------------------------------------------------------
def extract_pages(pdf_path, video_dir, progress_cb=None):
    os.makedirs(video_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    page_count = doc.page_count
    zoom = 150 / 72.0
    mat = fitz.Matrix(zoom, zoom)
    for i in range(page_count):
        pix = doc[i].get_pixmap(matrix=mat)
        out = os.path.join(video_dir, f"page_{i+1:02d}.png")
        pix.save(out)
        if progress_cb and i % 8 == 0:
            progress_cb("frames", i / page_count, f"提取页面 {i+1}/{page_count}")
    doc.close()
    return page_count


def create_combined_frames(total_pages, pages_per_clip, video_dir,
                           width=W, height=H, progress_cb=None):
    frame_paths = []
    for i in range(0, total_pages, pages_per_clip):
        imgs = []
        for j in range(i, min(i + pages_per_clip, total_pages)):
            p = os.path.join(video_dir, f"page_{j+1:02d}.png")
            if os.path.exists(p):
                imgs.append(Image.open(p).convert("RGB"))
        if not imgs:
            continue
        # 水平并排
        total_w = sum(im.width for im in imgs)
        max_h = max(im.height for im in imgs)
        combined = Image.new("RGB", (total_w, max_h), (255, 255, 255))
        x = 0
        for im in imgs:
            combined.paste(im, (x, 0))
            x += im.width
        combined = trim_white_border(combined)
        scale = min(width / combined.width, height / combined.height)
        combined = combined.resize((max(1, int(combined.width * scale)),
                                    max(1, int(combined.height * scale))), Image.LANCZOS)
        canvas = Image.new("RGB", (width, height), (20, 20, 20))
        canvas.paste(combined, ((width - combined.width) // 2, (height - combined.height) // 2))
        out = os.path.join(video_dir, f"frame_{len(frame_paths)+1:02d}.png")
        canvas.save(out, quality=95)
        frame_paths.append(out)
        if progress_cb:
            progress_cb("frames", (i + 1) / total_pages, f"合成帧 {len(frame_paths)}")
    return frame_paths


def trim_white_border(img, pad=6):
    # 用像素差异找内容边界
    gray = img.convert("L")
    bw = gray.point(lambda p: 0 if p > 240 else 255)
    bbox = bw.getbbox()
    if bbox:
        bbox = (max(0, bbox[0] - pad), max(0, bbox[1] - pad),
                min(img.width, bbox[2] + pad), min(img.height, bbox[3] + pad))
        return img.crop(bbox)
    return img


def extract_cover_page(pdf_path, video_dir):
    """Render only the first PDF page for the title-card preview."""
    os.makedirs(video_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    try:
        if doc.page_count < 1:
            raise ValueError("PDF 没有可预览页面")
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(150 / 72.0, 150 / 72.0),
                                alpha=False)
        out = os.path.join(video_dir, "page_01.png")
        pix.save(out)
        return out
    finally:
        doc.close()


def create_title_card(video_dir, font_path, title, subtitle, feature,
                      feature2, feature3, tagline, width=W, height=H,
                      title_style="classic", font_sizes=None):
    """
    自适应标题卡：随输出尺寸(width,height)缩放；
    横屏(宽>高)用「封面左·文字右」，竖屏/方形用「封面上·文字下」堆叠。
    """
    title_path = os.path.join(video_dir, "title_card.png")
    cover_path = os.path.join(video_dir, "page_01.png")
    cover = Image.open(cover_path).convert("RGB")

    Wd, Ht = width, height
    base = min(Wd, Ht)
    font_sizes = font_sizes or {}
    custom_fonts = title_style == "custom"
    canvas = Image.new("RGB", (Wd, Ht), (25, 12, 5))
    draw = ImageDraw.Draw(canvas)

    # 背景：径向渐变 + 顶部光带
    R = max(Wd, Ht)
    for r in range(R, 0, -4):
        alpha = max(0, min(255, int(55 * (1 - r / R))))
        c = (min(255, 55 + alpha), min(255, 30 + alpha), min(255, 12 + alpha))
        draw.ellipse([(Wd // 2 - r, Ht // 2 - r), (Wd // 2 + r, Ht // 2 + r)], outline=c)
    band = max(20, int(Ht * 0.093))
    for i in range(band):
        alpha = int(30 * (1 - i / band))
        c = (55 + alpha, 35 + alpha, 18 + alpha)
        draw.line([(0, i), (Wd, i)], fill=c)

    def font(px):
        try:
            return ImageFont.truetype(font_path, max(10, int(px)))
        except Exception:
            return ImageFont.load_default()

    def font_px(name, classic_ratio, default, low, high):
        if not custom_fonts:
            return base * classic_ratio
        try:
            value = float(font_sizes.get(name, default))
        except Exception:
            value = default
        value = max(low, min(high, value))
        return value * base / 1080.0

    font_large = font(font_px("title", 0.093, 100, 40, 180))
    font_mid = font(font_px("subtitle", 0.048, 52, 20, 100))
    font_badge = font(font_px("badge", 0.030, 32, 16, 72))
    if custom_fonts:
        info_px = font_px("info", 0.030, 34, 16, 72)
        font_small = font(info_px)
        font_tiny = font(info_px)
    else:
        font_small = font(base * 0.033)
        font_tiny = font(base * 0.026)
    font_tagline = font(font_px("tagline", 0.026, 28, 14, 64))

    def draw_cover(x, y, w, h):
        cov = cover.resize((w, h), Image.LANCZOS)
        so = max(6, int(base * 0.009))
        shadow = Image.new("RGBA", (w + so * 2, h + so * 2), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rectangle([so, so, w + so, h + so], fill=(0, 0, 0, 140))
        shadow = shadow.filter(ImageFilter.GaussianBlur(max(6, int(base * 0.011))))
        canvas.paste(shadow, (x - so, y - so), shadow)
        op, ip = max(4, int(base * 0.007)), max(2, int(base * 0.003))
        canvas.paste(Image.new("RGB", (w + op * 2, h + op * 2), (180, 150, 100)), (x - op, y - op))
        canvas.paste(Image.new("RGB", (w + ip * 2, h + ip * 2), (220, 190, 140)), (x - ip, y - ip))
        canvas.paste(cov, (x, y))

    def fit_text_font(text, fnt, max_width):
        if not text or not max_width:
            return fnt
        b = draw.textbbox((0, 0), text, font=fnt)
        width_now = max(1, b[2] - b[0])
        size_now = getattr(fnt, "size", 10)
        if width_now <= max_width or size_now <= 10:
            return fnt
        return font(max(10, int(size_now * max_width / width_now * 0.96)))

    def ctext(cx, y, text, fnt, fill, shadow=False, max_width=None):
        fnt = fit_text_font(text, fnt, max_width)
        b = draw.textbbox((0, 0), text, font=fnt)
        tw, th = b[2] - b[0], b[3] - b[1]
        x = int(cx - tw / 2)
        if shadow:
            off = max(2, int(base * 0.004))
            draw.text((x + off, y + off), text, font=fnt, fill=(0, 0, 0))
        draw.text((x, y), text, font=fnt, fill=fill)
        return th

    def draw_badges(cx, y, max_width):
        """在中心 cx 处从 y 起，居中堆叠 feature/feature2/feature3，返回新 y。"""
        if feature:
            badge_fnt = fit_text_font(feature, font_badge, max_width * 0.88)
            b = draw.textbbox((0, 0), feature, font=badge_fnt)
            tw, th = b[2] - b[0], b[3] - b[1]
            pad = max(8, int(base * 0.014))
            draw.rectangle([cx - tw // 2 - pad, y - 5, cx + tw // 2 + pad, y + th + 10],
                           fill=(160, 50, 40))
            ctext(cx, y, feature, badge_fnt, (255, 230, 180), max_width=max_width)
            y += th + int(base * 0.032)
        if feature2:
            y += ctext(cx, y, feature2, font_small, (255, 200, 100),
                       max_width=max_width) + int(base * 0.02)
        if feature3:
            y += ctext(cx, y, feature3, font_tiny, (200, 170, 120),
                       max_width=max_width) + int(base * 0.02)
        return y

    title = title or "大众电影"
    vertical = Ht >= Wd * 0.95      # 竖屏或近方形 -> 堆叠布局

    if not vertical:
        # ---- 横屏：封面左、文字右 ----
        margin = int(Wd * 0.026)
        target_w = int(Wd * 0.42)
        target_h = int(cover.height * (target_w / cover.width))
        max_h = int(Ht * 0.86)
        if target_h > max_h:
            target_h = max_h
            target_w = int(cover.width * (target_h / cover.height))
        y_off = (Ht - target_h) // 2
        draw_cover(margin, y_off, target_w, target_h)

        right_x = margin + target_w + int(Wd * 0.068)
        right_w = Wd - right_x - int(Wd * 0.042)
        cx = right_x + right_w // 2

        line_y1 = int(Ht * 0.167)
        draw.line([(right_x, line_y1), (right_x + right_w, line_y1)],
                  fill=(200, 170, 100), width=max(2, int(base * 0.003)))
        rr = max(3, int(base * 0.004))
        for dx in (-int(base * 0.009), int(base * 0.009)):
            draw.ellipse([(cx + dx - rr, line_y1 - rr), (cx + dx + rr, line_y1 + rr)],
                         fill=(200, 170, 100))

        y = int(Ht * 0.204)
        y += ctext(cx, y, title, font_large, (255, 210, 130), shadow=True,
                   max_width=right_w * 0.94) + int(Ht * 0.037)
        if subtitle:
            y += ctext(cx, y, subtitle, font_mid, (220, 220, 220),
                       max_width=right_w * 0.94) + int(Ht * 0.028)
            draw.line([(right_x + int(right_w * 0.1), y), (right_x + right_w - int(right_w * 0.1), y)],
                      fill=(180, 150, 90), width=2)
            y += int(Ht * 0.03)
        else:
            y += int(Ht * 0.02)
        draw_badges(cx, y, right_w * 0.94)
        tag_center = cx
        tag_lw = right_w
        tag_x0 = right_x
    else:
        # ---- 竖屏/方形：封面上、文字下（堆叠居中）----
        cx = Wd // 2
        top = int(Ht * 0.06)
        target_w = int(Wd * 0.66)
        target_h = int(cover.height * (target_w / cover.width))
        max_h = int(Ht * 0.5)
        if target_h > max_h:
            target_h = max_h
            target_w = int(cover.width * (target_h / cover.height))
        draw_cover(cx - target_w // 2, top, target_w, target_h)

        y = top + target_h + int(Ht * 0.045)
        lw = int(Wd * 0.5)
        draw.line([(cx - lw // 2, y), (cx + lw // 2, y)],
                  fill=(200, 170, 100), width=max(2, int(base * 0.003)))
        y += int(Ht * 0.02)
        y += ctext(cx, y, title, font_large, (255, 210, 130), shadow=True,
                   max_width=Wd * 0.9) + int(Ht * 0.022)
        if subtitle:
            y += ctext(cx, y, subtitle, font_mid, (220, 220, 220),
                       max_width=Wd * 0.9) + int(Ht * 0.022)
        draw_badges(cx, y, Wd * 0.9)
        tag_center = cx
        tag_lw = int(Wd * 0.7)
        tag_x0 = cx - tag_lw // 2

    if tagline:
        y_tag = Ht - int(Ht * 0.11)
        draw.line([(tag_x0 + int(tag_lw * 0.15), y_tag - int(Ht * 0.028)),
                   (tag_x0 + tag_lw - int(tag_lw * 0.15), y_tag - int(Ht * 0.028))],
                  fill=(200, 170, 100), width=2)
        ctext(tag_center, y_tag, tagline, font_tagline, (180, 160, 120),
              max_width=tag_lw * 0.9)

    canvas.save(title_path, quality=95)
    return title_path


def create_silent_video(title_path, frame_paths, title_duration, clip_durations,
                        video_dir, width=W, height=H, progress_cb=None):
    """clip_durations: 与 frame_paths 等长的每片段时长列表（秒）。"""
    video_path = os.path.join(video_dir, "silent_video.mp4")
    segments = []
    vf = (f"format=yuv420p,scale={width}:{height}:force_original_aspect_ratio=decrease,"
          f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2")
    all_files = [(title_path, title_duration)] + list(zip(frame_paths, clip_durations))
    n = len(all_files)
    for i, (img_path, dur) in enumerate(all_files):
        seg_path = os.path.join(video_dir, f"seg_{i:03d}.mp4")
        cmd = [
            "ffmpeg", "-y", "-loop", "1", "-i", img_path, "-t", str(dur),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-r", "30", seg_path
        ]
        if not run_ffmpeg(cmd, f"segment {i+1}"):
            return None
        segments.append(seg_path)
        if progress_cb:
            # 0.60~0.78 之间铺开，让“编码静音视频”有实时进度
            progress_cb("video", 0.60 + 0.18 * (i + 1) / n,
                        f"编码静音视频 {i+1}/{n} 段")

    concat_path = os.path.join(video_dir, "video_concat.txt")
    with open(concat_path, "w", encoding="utf-8") as f:
        for seg_path in segments:
            f.write(f"file '{seg_path.replace(chr(92), '/')}'\n")

    total = title_duration + sum(clip_durations)
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_path,
           "-c", "copy", "-t", str(total), video_path]
    if not run_ffmpeg(cmd, "concat video"):
        return None
    return video_path


# ----------------------------------------------------------------------------
# 音频：先合成每段旁白并测时长，再按每片段目标时长拼装
# ----------------------------------------------------------------------------
def _atempo_filters(factor):
    """把任意加速倍率拆成若干个落在 [0.5, 2.0] 区间的 atempo（ffmpeg 单次限制）。"""
    filters = []
    f = factor
    while f > 2.0:
        filters.append("atempo=2.0")
        f /= 2.0
    if f > 1.0001:
        filters.append(f"atempo={f:.6f}")
    return filters


def _write_silence(path, seconds=0.1):
    run_ffmpeg(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                "-t", str(seconds), "-ar", "44100", "-ac", "2",
                "-c:a", "pcm_s16le", path], "silence")


def _openai_chat_completions_url(base_url):
    base = (base_url or "").strip().rstrip("/")
    if not base:
        raise ValueError("LLM base_url 不能为空")
    if base.endswith("/chat/completions"):
        return base
    return base + "/chat/completions"


def _call_openai_chat(base_url, api_key, model, messages, temperature=0.4,
                      max_tokens=512, timeout=180):
    url = _openai_chat_completions_url(base_url)
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": int(max_tokens),
        "stream": False,
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key.strip()}"

    req = urlrequest.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urlerror.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        raise RuntimeError(
            f"LLM 请求失败: HTTP {e.code} {e.reason}"
            + (f" | {body[-500:]}" if body else "")
        ) from e
    except Exception as e:
        raise RuntimeError(f"LLM 请求失败: {e}") from e

    try:
        data = json.loads(raw)
    except Exception as e:
        raise RuntimeError(f"LLM 返回不是合法 JSON: {e}; 原始内容: {raw[-500:]}") from e

    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(f"LLM 返回错误: {data['error']}")

    try:
        choices = data["choices"]
        msg = choices[0]["message"]
        content = msg.get("content", "")
    except Exception as e:
        raise RuntimeError(f"LLM 返回缺少 choices/message.content: {e}") from e

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        content = "\n".join(parts)
    return str(content).strip()


def _pdf_page_data_url(page, max_size=1800):
    """Render one PDF page as a reasonably sized JPEG data URL for vision APIs."""
    pix = page.get_pixmap(matrix=fitz.Matrix(150 / 72.0, 150 / 72.0),
                          alpha=False)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    if max(img.size) > max_size:
        scale = max_size / float(max(img.size))
        img = img.resize((max(1, int(img.width * scale)),
                          max(1, int(img.height * scale))), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=86, optimize=True)
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return "data:image/jpeg;base64," + encoded


def generate_ai_ocr(pdf_path, fallback_pages, llm_cfg, progress_cb=None):
    """Recognize image-only PDF pages through an OpenAI-compatible vision model."""
    base_url = (llm_cfg or {}).get("base_url", "")
    api_key = (llm_cfg or {}).get("api_key", "")
    model = (llm_cfg or {}).get("model", "")
    provider = (llm_cfg or {}).get("provider", "openai").strip().lower()
    if not base_url or not model:
        raise RuntimeError("AI OCR 配置不完整，请填写 base_url 和 model")

    is_nvidia = provider == "nvidia"
    min_interval = 1.65 if is_nvidia else 0.0
    next_allowed_at = 0.0
    prompts = (
        "请准确识别这张 PDF 页面中的所有可见文字。按正常阅读顺序输出，"
        "尽量保留标题、段落和换行；不要补写图片中没有的内容，不要解释识别过程。"
        "如果页面主要是图片且没有文字，只输出空文本。"
    )
    doc = fitz.open(pdf_path)
    out = []
    failures = 0
    last_err = ""
    try:
        total = doc.page_count
        for i in range(total):
            if is_nvidia:
                wait = max(0.0, next_allowed_at - time.time())
                if wait > 0:
                    if progress_cb:
                        progress_cb("ai_ocr", i / max(1, total),
                                    f"NVIDIA AI OCR 节流等待 {wait:.1f}s")
                    time.sleep(wait)

            ok = False
            for attempt in range(1, 4):
                if is_nvidia:
                    next_allowed_at = max(next_allowed_at, time.time()) + min_interval
                try:
                    raw = _call_openai_chat(
                        base_url, api_key, model,
                        [{"role": "user", "content": [
                            {"type": "text", "text": prompts},
                            {"type": "image_url", "image_url": {
                                "url": _pdf_page_data_url(doc[i])}}
                        ]}],
                        temperature=0.0, max_tokens=4096, timeout=180)
                    text = _clean_ai_text(raw)
                    out.append(text)
                    ok = True
                    break
                except Exception as e:
                    last_err = str(e)
                    if is_nvidia and _is_retryable_llm_error(last_err) and attempt < 3:
                        sleep_s = min(15.0, 1.7 * (2 ** (attempt - 1)))
                        if progress_cb:
                            progress_cb("ai_ocr", i / max(1, total),
                                        f"NVIDIA AI OCR 限流，重试 {attempt + 1}/3")
                        time.sleep(sleep_s)
                        continue
                    print(f"    AI OCR 第 {i + 1}/{total} 页失败，保留原结果: {e}")
                    break
            if not ok:
                failures += 1
                out.append(fallback_pages[i] if i < len(fallback_pages) else "")
            if progress_cb:
                progress_cb("ai_ocr", (i + 1) / max(1, total),
                            f"AI OCR 识别中 {i + 1}/{total} 页")
    finally:
        doc.close()

    if failures:
        note = f"AI OCR 有 {failures} 页失败，已保留原结果"
        if failures >= len(out) and last_err:
            note = "AI OCR 全部失败，已保留原结果"
        if progress_cb:
            progress_cb("ai_ocr", 1.0, note)
    return out


def _clean_ai_text(text):
    if not text:
        return ""
    s = text.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else ""
        if s.endswith("```"):
            s = s[:-3]
    s = s.replace("\r", "\n").strip()
    lines = [ln.strip("` ").strip() for ln in s.splitlines()]
    lines = [ln for ln in lines if ln]
    s = " ".join(lines).strip()
    s = re.sub(r"\s+", " ", s)
    return s.strip(" \t\r\n\"'。")


def _is_retryable_llm_error(err_text):
    s = (err_text or "").lower()
    return any(k in s for k in (
        "http 429", "too many requests", "rate limit",
        "http 500", "http 502", "http 503", "http 504",
        "temporarily unavailable", "timeout",
    ))


def generate_ai_narration(page_texts, pages_per_clip, fallback_clips, llm_cfg,
                          progress_cb=None):
    """
    Generate narration text for each clip via an OpenAI-compatible LLM.
    NVIDIA mode is throttled to stay under the free-tier rpm limit.
    """
    enabled = bool(llm_cfg and llm_cfg.get("enabled"))
    provider = (llm_cfg or {}).get("provider", "openai").strip().lower()
    base_url = (llm_cfg or {}).get("base_url", "")
    api_key = (llm_cfg or {}).get("api_key", "")
    model = (llm_cfg or {}).get("model", "")
    if not enabled:
        return fallback_clips, ""
    if not base_url or not model:
        return fallback_clips, "AI 旁白配置不完整，已保留原始文本"

    is_nvidia = provider == "nvidia"
    min_interval = 1.65 if is_nvidia else 0.0
    next_allowed_at = 0.0

    clip_count = len(fallback_clips)
    out = []
    failures = 0
    last_err = ""
    for i in range(clip_count):
        start = i * max(1, int(pages_per_clip))
        end = min(len(page_texts), start + max(1, int(pages_per_clip)))
        pages = page_texts[start:end]
        if not pages:
            out.append(fallback_clips[i])
            failures += 1
            continue

        if is_nvidia:
            wait = max(0.0, next_allowed_at - time.time())
            if wait > 0:
                if progress_cb:
                    progress_cb("ai", 0.55 + 0.35 * i / max(1, clip_count),
                                f"NVIDIA 模式节流等待 {wait:.1f}s")
                time.sleep(wait)

        parts = []
        for j, text in enumerate(pages, start=start + 1):
            label = "封面" if j == 1 else f"第{j}页"
            txt = (text or "").strip()
            if not txt:
                txt = "（无可识别文字，主要为版面或图片）"
            parts.append(f"{label}：{txt}")

        sys_msg = (
            "你是中文杂志解说视频的旁白编写助手。"
            "请根据给定页面 OCR 文本写一段适合口播的旁白，语气自然、信息准确、简洁流畅。"
            "如果第1页是封面，只把它当作封面参考，不要逐字复述封面标题。"
            "只输出最终旁白正文，不要编号、标题、项目符号、解释或前后缀。"
        )
        user_msg = (
            f"这是第 {i + 1}/{clip_count} 个片段。"
            "请写 1 到 2 句中文旁白，长度大约 60 到 120 个汉字。"
            "页面 OCR 如下：\n" + "\n".join(parts)
        )

        ok = False
        for attempt in range(1, 4):
            if is_nvidia:
                next_allowed_at = max(next_allowed_at, time.time()) + min_interval
            try:
                raw = _call_openai_chat(
                    base_url, api_key, model,
                    [{"role": "system", "content": sys_msg},
                     {"role": "user", "content": user_msg}],
                    temperature=0.5,
                    max_tokens=512,
                    timeout=180,
                )
                text = _clean_ai_text(raw)
                if not text:
                    raise RuntimeError("LLM 返回内容为空")
                out.append(text)
                ok = True
                break
            except Exception as e:
                last_err = str(e)
                retryable = is_nvidia and _is_retryable_llm_error(last_err)
                if retryable and attempt < 3:
                    sleep_s = min(15.0, 1.7 * (2 ** (attempt - 1)))
                    print(f"    AI 旁白 {i + 1}/{clip_count} 命中限流，{sleep_s:.1f}s 后重试: {e}")
                    if progress_cb:
                        progress_cb("ai", 0.55 + 0.35 * i / max(1, clip_count),
                                    f"NVIDIA 限流，重试 {attempt + 1}/3")
                    time.sleep(sleep_s)
                    continue
                failures += 1
                print(f"    AI 旁白 {i + 1}/{clip_count} 失败，回退原文: {e}")
                out.append(fallback_clips[i])
                break

        if progress_cb:
            progress_cb("ai", 0.55 + 0.35 * (i + 1) / max(1, clip_count),
                        f"AI 生成旁白 {i + 1}/{clip_count}")

    if failures:
        note = "AI 旁白已生成，但部分片段回退为原始文本"
        if failures >= clip_count:
            note = "AI 旁白生成失败，已保留原始 OCR 文本"
            if last_err:
                print(f"  AI 旁白最终失败: {last_err}")
        return out, note
    return out, ""


def synth_narration(narration, narration_dir, voice, rate, progress_cb=None):
    """
    为每段旁白生成 wav，返回 (wav_paths, raw_durations)。

    单段 TTS 失败（多为网络问题）不会立即中断：该段退化为静音并继续，
    但会统计失败数。若**所有非空旁白**都失败（说明整体连不上语音服务），
    则抛出明确的网络错误，让前端直接看到原因。
    """
    os.makedirs(narration_dir, exist_ok=True)
    clips = len(narration)
    wavs, durs = [], []
    nonempty = 0
    failures = 0
    last_err = ""
    for i, text in enumerate(narration):
        wav_in = os.path.join(narration_dir, f"sec_{i:02d}.wav")
        has_text = bool(text and text.strip())
        if has_text:
            nonempty += 1
        try:
            generate_tts_edge(text, wav_in, voice, rate)
        except Exception as e:      # 网络等原因导致该段失败
            last_err = str(e)
            if has_text:
                failures += 1
            print(f"    旁白 {i+1} TTS 失败，改为静音: {e}")
            _write_silence(wav_in)
        if not os.path.exists(wav_in):
            _write_silence(wav_in)
        wavs.append(wav_in)
        durs.append(get_duration(wav_in))
        if progress_cb:
            progress_cb("tts", (i + 1) / max(1, clips), f"合成旁白 {i+1}/{clips}")

    if nonempty > 0 and failures >= nonempty:
        # 所有有内容的旁白都失败 -> 视为整体网络不可用，明确报错
        raise RuntimeError(last_err or
            "TTS 全部失败：无法连接微软语音服务，请检查网络/代理后重试。")
    if failures > 0:
        print(f"  警告：{failures}/{nonempty} 段旁白 TTS 失败，已用静音代替。")
    return wavs, durs


def assemble_audio(wavs, clip_durations, title_duration, narration_dir,
                   progress_cb=None):
    """把每段 wav 适配到对应的片段时长（过长则加速，过短则补静音），拼成整条音轨。"""
    clips = len(wavs)
    padded_paths = []
    for i, (wav_in, clip_duration) in enumerate(zip(wavs, clip_durations)):
        d = get_duration(wav_in)
        out = os.path.join(narration_dir, f"pad_{i:02d}.wav")
        filters = []
        if d > clip_duration + 0.05:
            filters.extend(_atempo_filters(d / clip_duration))
        filters.append(f"apad,atrim=0:{clip_duration}")
        filters.append("volume=1.5")
        cmd = ["ffmpeg", "-y", "-i", wav_in, "-af", ",".join(filters),
               "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", out]
        if not run_ffmpeg(cmd, f"pad {i+1}"):
            return None
        padded_paths.append(out)
        if progress_cb:
            progress_cb("tts", (i + 1) / max(1, clips), f"拼装旁白 {i+1}/{clips}")

    # 封面静音段
    silence = os.path.join(narration_dir, "silence_title.wav")
    run_ffmpeg(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                "-t", str(title_duration), "-c:a", "pcm_s16le", silence])

    concat_list = os.path.join(narration_dir, "concat.txt")
    with open(concat_list, "w", encoding="utf-8") as f:
        f.write(f"file '{silence.replace(chr(92), '/')}'\n")
        for p in padded_paths:
            f.write(f"file '{p.replace(chr(92), '/')}'\n")

    concat_out = os.path.join(narration_dir, "concat_out.wav")
    if not run_ffmpeg(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
                       "-c", "copy", concat_out], "concat audio"):
        return None

    final_audio = os.path.join(narration_dir, "final_audio.aac")
    total = title_duration + sum(clip_durations)
    fade_out_start = max(0.0, total - 3.0)
    cmd = ["ffmpeg", "-y", "-i", concat_out,
           "-af", f"afade=t=in:st=0:d=0.5,afade=t=out:st={fade_out_start}:d=3.0",
           "-c:a", "aac", "-b:a", "192k", "-t", str(total), final_audio]
    if not run_ffmpeg(cmd, "finalize audio"):
        return None
    return final_audio


# ----------------------------------------------------------------------------
# 字幕：由旁白文本 + 每片段时长生成 SRT，可选烧录进画面
# ----------------------------------------------------------------------------
def _srt_ts(sec):
    if sec < 0:
        sec = 0
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def split_caption(text, max_len=20):
    """把一段旁白切成适合单条字幕的小段：先按句末标点断句，过长再按次级标点/长度切。"""
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return []
    # 先按句末标点断（保留标点）
    parts = re.split(r"(?<=[。！？!?；;\.])", text)
    chunks = []
    for p in parts:
        p = p.strip()
        while len(p) > max_len:
            # 尽量在次级标点（，、,）处断，否则硬切
            cut = -1
            for sep in "，,、":
                idx = p.rfind(sep, 0, max_len + 1)
                if idx > cut:
                    cut = idx
            if cut < max_len * 0.5:
                cut = max_len - 1
            chunks.append(p[:cut + 1].strip())
            p = p[cut + 1:].strip()
        if p:
            chunks.append(p)
    return [c for c in chunks if c]


def build_caption_cues(narration, clip_durations, raw_durs, title_duration):
    """Build the shared timing cues used by SRT and bilingual ASS output."""
    cues = []
    t = float(title_duration)
    for i, text in enumerate(narration):
        dur = float(clip_durations[i])
        raw = float(raw_durs[i]) if i < len(raw_durs) else 0.0
        speak = min(raw, dur) if raw > 0.15 else 0.0
        caps = split_caption(text) if speak > 0 else []
        if caps:
            total_ch = sum(len(c) for c in caps) or 1
            cur = t
            for j, c in enumerate(caps):
                seg = speak * (len(c) / total_ch)
                s = cur
                e = t + speak if j == len(caps) - 1 else cur + seg
                if e - s < 0.3:            # 太短的给个下限
                    e = min(t + speak, s + 0.3)
                cues.append({"start": s, "end": e, "text": c})
                cur += seg
        t += dur
    return cues


def build_srt_from_cues(cues, translations=None):
    lines = []
    translations = translations or []
    for idx, cue in enumerate(cues, start=1):
        text = cue["text"]
        if idx - 1 < len(translations) and translations[idx - 1].strip():
            text += "\n" + translations[idx - 1].strip()
        lines.append(
            f"{idx}\n{_srt_ts(cue['start'])} --> {_srt_ts(cue['end'])}\n{text}\n")
    return "\n".join(lines)


def build_srt(narration, clip_durations, raw_durs, title_duration):
    """Generate the original Chinese-only SRT output."""
    cues = build_caption_cues(
        narration, clip_durations, raw_durs, title_duration)
    return build_srt_from_cues(cues)


class _TranslationCountError(RuntimeError):
    pass


def _parse_translation_json(raw, expected):
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("[")
    end = text.rfind("]")
    if start < 0 or end < start:
        raise RuntimeError("AI 翻译返回内容不是 JSON 数组")
    try:
        values = json.loads(text[start:end + 1])
    except Exception as e:
        raise RuntimeError(f"AI 翻译返回 JSON 解析失败: {e}") from e
    if not isinstance(values, list) or len(values) != expected:
        raise _TranslationCountError(
            f"AI 翻译返回数量不匹配：需要 {expected} 条，实际 {len(values) if isinstance(values, list) else 0} 条")
    return [re.sub(r"\s+", " ", str(x or "")).strip() for x in values]


def generate_ai_subtitle_translations(cues, llm_cfg, progress_cb=None):
    """Translate Chinese subtitle cues in batches through the configured LLM."""
    if not cues:
        return []
    provider = (llm_cfg or {}).get("provider", "openai").strip().lower()
    base_url = (llm_cfg or {}).get("base_url", "").strip()
    api_key = (llm_cfg or {}).get("api_key", "").strip()
    model = (llm_cfg or {}).get("model", "").strip()
    if not base_url or not model:
        raise RuntimeError("双语字幕需要填写 LLM base_url 和 model")

    is_nvidia = provider == "nvidia"
    min_interval = 1.65 if is_nvidia else 0.0
    next_allowed_at = 0.0
    batch_size = 8
    completed = 0
    system_msg = (
        "You translate Chinese video subtitles into concise, natural English. "
        "Keep names and facts accurate. Return only a JSON array of strings, "
        "with exactly one English translation for each input item, preserving order."
    )
    def translate_batch(batch, label):
        nonlocal next_allowed_at, completed
        attempts = 3
        last_err = ""
        for attempt in range(1, attempts + 1):
            if is_nvidia:
                wait = max(0.0, next_allowed_at - time.time())
                if wait > 0:
                    if progress_cb:
                        progress_cb("translate", completed / max(1, len(cues)),
                                    f"NVIDIA 翻译节流等待 {wait:.1f}s")
                    time.sleep(wait)
                next_allowed_at = max(next_allowed_at, time.time()) + min_interval
            try:
                raw = _call_openai_chat(
                    base_url, api_key, model,
                    [{"role": "system", "content": system_msg},
                     {"role": "user", "content": json.dumps(batch, ensure_ascii=False)}],
                    temperature=0.1,
                    max_tokens=min(4096, max(1024, len(batch) * 240)),
                    timeout=180,
                )
                result = _parse_translation_json(raw, len(batch))
                completed += len(result)
                if progress_cb:
                    progress_cb("translate", completed / max(1, len(cues)),
                                f"AI 翻译英文字幕 {completed}/{len(cues)} 条")
                return result
            except _TranslationCountError as e:
                last_err = str(e)
                if len(batch) > 1:
                    mid = len(batch) // 2
                    print(f"    AI 字幕翻译 {label} 返回数量不完整，拆分为 {mid}+{len(batch)-mid} 条重试")
                    return (translate_batch(batch[:mid], label + "A") +
                            translate_batch(batch[mid:], label + "B"))
            except Exception as e:
                last_err = str(e)

            if attempt < attempts:
                retryable = _is_retryable_llm_error(last_err)
                sleep_s = min(12.0, (1.7 if retryable else 0.8) * (2 ** (attempt - 1)))
                time.sleep(sleep_s)
                continue
            raise RuntimeError(f"AI 英文字幕翻译失败（{label}）: {last_err}")
        raise RuntimeError(f"AI 英文字幕翻译失败（{label}）: {last_err}")

    translated = []
    for batch_index, start in enumerate(range(0, len(cues), batch_size), start=1):
        batch = [c["text"] for c in cues[start:start + batch_size]]
        translated.extend(translate_batch(batch, f"第 {batch_index} 批"))
    return translated


def _ass_ts(sec):
    sec = max(0.0, float(sec))
    total_cs = int(round(sec * 100))
    h, total_cs = divmod(total_cs, 360000)
    m, total_cs = divmod(total_cs, 6000)
    s, cs = divmod(total_cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _ass_color(value, default):
    value = (value or "").strip()
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
        value = default
    r, g, b = value[1:3], value[3:5], value[5:7]
    return f"&H00{b}{g}{r}".upper()


def _ass_escape(text):
    return (text or "").replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")


def _wrap_english(text, max_len=52):
    words = (text or "").split()
    if not words:
        return ""
    lines = []
    current = []
    for word in words:
        candidate = " ".join(current + [word])
        if current and len(candidate) > max_len:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    if len(lines) > 2:
        lines = [lines[0], " ".join(lines[1:])]
    return r"\N".join(lines)


def build_bilingual_ass(cues, translations, width, height,
                        zh_color="#66FF7A", en_color="#FFFFFF",
                        outline_color="#101010"):
    """Create two independently styled subtitle rows: Chinese above English."""
    zh_size = max(24, int(height * 0.046))
    en_size = max(18, int(height * 0.032))
    outline = max(2, int(height * 0.0028))
    en_margin = max(24, int(height * 0.038))
    zh_margin = en_margin + en_size * 2 + max(10, int(height * 0.012))
    zh_ass = _ass_color(zh_color, "#66FF7A")
    en_ass = _ass_color(en_color, "#FFFFFF")
    outline_ass = _ass_color(outline_color, "#101010")
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {int(width)}
PlayResY: {int(height)}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Chinese,Microsoft YaHei,{zh_size},{zh_ass},{zh_ass},{outline_ass},&H70000000,-1,0,0,0,100,100,0,0,1,{outline},1,2,35,35,{zh_margin},1
Style: English,Arial,{en_size},{en_ass},{en_ass},{outline_ass},&H70000000,-1,0,0,0,100,100,0,0,1,{outline},1,2,35,35,{en_margin},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for cue, english in zip(cues, translations):
        start = _ass_ts(cue["start"])
        end = _ass_ts(cue["end"])
        zh = _ass_escape(cue["text"])
        en = _wrap_english(_ass_escape(english))
        events.append(f"Dialogue: 0,{start},{end},Chinese,,0,0,0,,{zh}")
        if en:
            events.append(f"Dialogue: 0,{start},{end},English,,0,0,0,,{en}")
    return header + "\n".join(events) + "\n"


def _copy_subtitle_fonts(target_dir, font_dir):
    import shutil
    candidates = [
        (os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "msyhbd.ttc"),
         "msyhbd.ttc"),
        (os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "arialbd.ttf"),
         "arialbd.ttf"),
        (os.path.join(font_dir, "font.ttf"), "subfont.ttf"),
    ]
    for src, name in candidates:
        try:
            if os.path.exists(src):
                shutil.copy(src, os.path.join(target_dir, name))
        except Exception:
            pass


def burn_subtitles(video_in, srt_path, video_out, font_dir, font_name, height,
                   primary_color="#FFFFFF", outline_color="#202020"):
    """
    把 SRT 硬烧进画面并重编码。
    关键：Windows 绝对路径里的 ':' '\\' 会破坏 ffmpeg 滤镜串解析，
    所以把字体拷到字幕同目录、cwd 设到该目录，滤镜里只用相对文件名和 fontsdir=. 。
    """
    srt_dir = os.path.dirname(os.path.abspath(srt_path))
    srt_name = os.path.basename(srt_path)
    _copy_subtitle_fonts(srt_dir, font_dir)
    font_size = max(14, int(height * 0.045))
    style = (f"FontName={font_name},FontSize={font_size},"
             f"PrimaryColour={_ass_color(primary_color, '#FFFFFF')},"
             f"OutlineColour={_ass_color(outline_color, '#202020')},"
             "Bold=1,BorderStyle=1,Outline=2,Shadow=1,MarginV=40")
    vf = f"subtitles={srt_name}:fontsdir=.:force_style='{style}'"
    cmd = ["ffmpeg", "-y", "-i", os.path.abspath(video_in), "-vf", vf,
           "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", "copy", "-movflags", "+faststart", os.path.abspath(video_out)]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=srt_dir)
    if result.returncode != 0:
        print("  ERROR in burn subtitles:")
        print("  " + (result.stderr or "")[-800:])
        return False
    return True


def burn_ass_subtitles(video_in, ass_path, video_out, font_dir):
    """Burn a pre-styled ASS subtitle file into the video."""
    ass_dir = os.path.dirname(os.path.abspath(ass_path))
    ass_name = os.path.basename(ass_path)
    _copy_subtitle_fonts(ass_dir, font_dir)
    vf = f"subtitles={ass_name}:fontsdir=."
    cmd = ["ffmpeg", "-y", "-i", os.path.abspath(video_in), "-vf", vf,
           "-c:v", "libx264", "-preset", "fast", "-crf", "20",
           "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart",
           os.path.abspath(video_out)]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=ass_dir)
    if result.returncode != 0:
        print("  ERROR in burn bilingual subtitles:")
        print("  " + (result.stderr or "")[-800:])
        return False
    return True


# ----------------------------------------------------------------------------
# 总入口
# ----------------------------------------------------------------------------
def build_video(pdf_path, out_path, params, narration, progress_cb=None):
    """
    params: dict(
        pages_per_clip, clip_duration, title_duration,
        title, subtitle, feature, feature2, feature3, tagline,
        voice, rate, font_path
    )
    narration: list[str] 每个内容片段的旁白 (长度应等于片段数)
    返回 out_path 或 None
    """
    pages_per_clip = max(1, int(params.get("pages_per_clip", 2)))
    clip_duration = float(params.get("clip_duration", 12.0))
    title_duration = float(params.get("title_duration", 3.0))
    voice = params.get("voice", "zh-CN-YunxiNeural")
    rate = params.get("rate", "+6%")
    font_path = params.get("font_path")
    # 新功能：根据解说词自动延长片段时长
    auto_duration = bool(params.get("auto_duration", False))
    max_clip_duration = float(params.get("max_clip_duration", 60.0))
    tail_pad = float(params.get("tail_pad", 1.0))
    # 新功能：输出宽高比 + 清晰度 -> 像素尺寸
    Wd, Ht = compute_dimensions(
        params.get("aspect", "16:9"),
        params.get("custom_w", 16), params.get("custom_h", 9),
        int(params.get("quality", 1080)))

    workdir = os.path.splitext(out_path)[0] + "_work"
    video_dir = os.path.join(workdir, "video")
    narration_dir = os.path.join(workdir, "narration")
    os.makedirs(video_dir, exist_ok=True)
    os.makedirs(narration_dir, exist_ok=True)

    # Step 1: 提取页面
    if progress_cb:
        progress_cb("frames", 0.0, "提取 PDF 页面")
    total_pages = extract_pages(pdf_path, video_dir, progress_cb)

    # 片段数（封面帧用 page_01，内容帧从全部页合成）
    clips = (total_pages + pages_per_clip - 1) // pages_per_clip
    # 对齐 narration 长度
    if narration is None:
        narration = [""] * clips
    if len(narration) < clips:
        narration = narration + [""] * (clips - len(narration))
    elif len(narration) > clips:
        narration = narration[:clips]

    # Step 2: 内容帧
    if progress_cb:
        progress_cb("frames", 0.3, "合成内容帧")
    frame_paths = create_combined_frames(total_pages, pages_per_clip, video_dir,
                                         Wd, Ht, progress_cb)
    # 以实际生成的画面帧数为准，对齐旁白与时长（避免缺页导致音画错位）
    nframes = len(frame_paths)
    if len(narration) < nframes:
        narration = narration + [""] * (nframes - len(narration))
    else:
        narration = narration[:nframes]

    # Step 3: 标题卡
    if progress_cb:
        progress_cb("title", 0.5, "生成标题卡")
    title_path = create_title_card(
        video_dir, font_path,
        params.get("title", "大众电影"), params.get("subtitle", ""),
        params.get("feature", ""), params.get("feature2", ""),
        params.get("feature3", ""), params.get("tagline", ""),
        Wd, Ht, params.get("title_card_style", "classic"),
        params.get("title_font_sizes") or {})

    # Step 4: 先合成旁白（测得每段真实时长，供“自动延长片段时长”使用）
    if progress_cb:
        progress_cb("tts", 0.55, "生成旁白音频")
    wavs, raw_durs = synth_narration(narration, narration_dir, voice, rate, progress_cb)

    # 每片段“基准时长”：优先用前端传来的逐片段时长(clip_durations)，否则用全局 clip_duration。
    base_durs = params.get("clip_durations") or []
    try:
        base_durs = [float(x) for x in base_durs]
    except Exception:
        base_durs = []
    if len(base_durs) < nframes:
        base_durs = base_durs + [clip_duration] * (nframes - len(base_durs))
    else:
        base_durs = base_durs[:nframes]
    base_durs = [b if b > 0.3 else clip_duration for b in base_durs]

    # 每片段目标时长：
    #   auto_duration=True  -> 以“基准时长”为下限，随解说词长度自动延长
    #                          （旁白结束后再留 tail_pad 秒空镜），上限 max_clip_duration。
    #   auto_duration=False -> 固定为“基准时长”（旁白过长会被加速，行为同旧版）。
    if auto_duration:
        clip_durations = []
        for i, d in enumerate(raw_durs):
            mn = base_durs[i]
            if d <= 0.15:                     # 空旁白：用基准（最短）时长
                clip_durations.append(mn)
            else:
                clip_durations.append(min(max_clip_duration, max(mn, d + tail_pad)))
    else:
        clip_durations = list(base_durs)

    # Step 5: 静音视频（按每片段时长）
    if progress_cb:
        progress_cb("video", 0.7, "编码静音视频")
    video_path = create_silent_video(title_path, frame_paths, title_duration,
                                      clip_durations, video_dir, Wd, Ht, progress_cb)
    if not video_path:
        return None

    # Step 6: 拼装音轨（按每片段时长）
    if progress_cb:
        progress_cb("tts", 0.85, "拼装旁白音轨")
    final_audio = assemble_audio(wavs, clip_durations, title_duration,
                                 narration_dir, progress_cb)
    if not final_audio:
        return None

    # 字幕：由旁白 + 每片段时长生成 SRT/ASS（可选）
    subtitle_mode = params.get("subtitle_mode", "none")
    burn_mode = subtitle_mode in ("burn", "burn_bilingual")
    srt_path = os.path.splitext(out_path)[0] + ".srt"
    ass_path = os.path.splitext(out_path)[0] + ".ass"
    cues = []
    translations = []
    if subtitle_mode in ("srt", "burn", "burn_bilingual"):
        if progress_cb:
            progress_cb("merge", 0.93, "生成字幕(SRT)")
        cues = build_caption_cues(
            narration, clip_durations, raw_durs, title_duration)
        if subtitle_mode == "burn_bilingual":
            if progress_cb:
                progress_cb("translate", 0.0, "AI 翻译英文字幕")
            translations = generate_ai_subtitle_translations(
                cues, params.get("llm_cfg") or {}, progress_cb)
            srt_text = build_srt_from_cues(cues, translations)
            ass_text = build_bilingual_ass(
                cues, translations, Wd, Ht,
                params.get("subtitle_zh_color", "#66FF7A"),
                params.get("subtitle_en_color", "#FFFFFF"),
                params.get("subtitle_outline_color", "#101010"))
            with open(ass_path, "w", encoding="utf-8-sig") as f:
                f.write(ass_text)
        else:
            srt_text = build_srt_from_cues(cues)
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_text)

    # Step 7: 合成
    if progress_cb:
        progress_cb("merge", 0.95, "合成最终视频")
    # 若要烧录字幕，先合成到临时文件，再重编码烧字幕到 out_path
    mux_out = out_path if not burn_mode else os.path.join(workdir, "muxed.mp4")
    cmd = ["ffmpeg", "-y", "-i", video_path, "-i", final_audio,
           "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
           "-map", "0:v", "-map", "1:a",
           # +faststart 把 moov 头移到文件开头：否则很多本地播放器打开“下载后的”文件会报格式错
           "-movflags", "+faststart",
           "-t", str(title_duration + sum(clip_durations)), mux_out]
    if not run_ffmpeg(cmd, "merge"):
        return None

    if burn_mode:
        if progress_cb:
            progress_cb("merge", 0.97, "烧录字幕进画面")
        font_dir = os.path.dirname(font_path) if font_path else os.path.dirname(os.path.abspath(__file__))
        if subtitle_mode == "burn_bilingual":
            ok = burn_ass_subtitles(mux_out, ass_path, out_path, font_dir)
        else:
            ok = burn_subtitles(
                mux_out, srt_path, out_path, font_dir, "Microsoft YaHei", Ht,
                params.get("subtitle_zh_color", "#FFFFFF"),
                params.get("subtitle_outline_color", "#202020"))
        if not ok:
            # 烧录失败（如字体/滤镜问题）不整体失败：退回未烧录版本 + 保留 SRT
            import shutil
            shutil.copy(mux_out, out_path)
            print("  警告：字幕烧录失败，已输出无硬字幕的视频，另存了 .srt 文件。")

    if progress_cb:
        progress_cb("done", 1.0, "完成")
    return out_path


if __name__ == "__main__":
    # 简单命令行测试
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("out")
    ap.add_argument("--pages_per_clip", type=int, default=2)
    ap.add_argument("--clip_duration", type=float, default=12.0)
    ap.add_argument("--title", default="大众电影")
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--voice", default="zh-CN-YunxiNeural")
    ap.add_argument("--rate", default="+6%")
    ap.add_argument("--font", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "font.ttf"))
    args = ap.parse_args()
    pages = extract_page_texts(args.pdf, use_ocr=True,
                               py_exe=sys.executable,
                               ocr_worker=os.path.join(os.path.dirname(os.path.abspath(__file__)), "_ocr_worker.py"))
    clips = group_into_clips(pages, args.pages_per_clip)
    print(f"clips={len(clips)}")
    build_video(args.pdf, args.out, vars(args), clips)

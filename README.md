# AI PDF解说视频生成器

把一本 PDF 杂志（尤其是《大众电影》这类扫描件）自动做成带 AI 旁白的解说视频（MP4）。
本地运行的网页工具：**上传 PDF → 自动提取文字（无文字层则 OCR）→ 编辑旁白 → 调参数 → 一键生成**。封面标题卡、配音、字幕都自动搞定。

> 详细中文文档见 **[README_解说视频生成器.md](README_解说视频生成器.md)**（安装、参数、OCR、常见问题一应俱全）。

---

## ✨ 功能

- **PDF → 视频**：自动把每页渲染成画面，按「每片段 N 页」拼成片段，加封面标题卡，合成 MP4。
- **文字提取**：有文字层的 PDF 秒级提取；纯扫描件可选择 **EasyOCR / RapidOCR / PaddleOCR**，也可勾选支持视觉输入的 **AI OCR**；本地 OCR 子进程运行、断点续跑、卡死保护、实时进度。
- **AI 配音**：微软 [edge-tts](https://github.com/rany2/edge-tts) 在线合成，6 种中文声线 + 语速可调；AI 自动生成旁白默认开启，支持 NVIDIA 免费 API 并自动节流；网络失败有清晰提示与降级。AI OCR 与 AI 旁白独立开关，共用 LLM 配置。
- **旁白可编辑**：每段旁白单独编辑，也可**逐段单独设定时长**。
- **按解说词自动延长片段时长**：旁白多长画面就停多久，不再把配音硬加速。
- **选择页码**：只做其中某些页，如 `1~10,15~20,30`。
- **输出尺寸**：画面比例 16:9 / 9:16 / 4:3 / 1:1 / 自定义，清晰度 480/720/1080/1440；标题卡横竖屏自适应。
- **封面实时预览**：保留经典自动版式，也可切换自定义字号，调整主标题、副标题、徽标、副信息和标语大小。
- **字幕**：可生成 **SRT 文件**、单语硬字幕，或生成“中文在上、AI 英译在下”的双语硬字幕；中英文和描边颜色可选。
- **兼容性**：输出 MP4 带 `+faststart`，下载后各播放器都能直接打开。

演示样例见 [`sample/`](sample/)：输入 `sample_in.pdf`（46 页扫描件）→ 输出 `sample_out.mp4`。

---

## 🧩 运行环境

- **Python 3.14**（用 `py -3.14`，或 `python`）
- **ffmpeg**（含 `ffprobe`，需在 PATH）
- Python 库：`flask` · `PyMuPDF` · `Pillow` · `edge-tts` · `numpy`；本地 OCR 引擎按需安装 `easyocr`、`rapidocr_onnxruntime` 或 `paddleocr` / `paddlepaddle`
- 联网要求：**配音**需能访问微软语音服务；**OCR 首次**需联网下载模型（之后离线）

---

## 🚀 快速开始

```bash
# 1) 安装 ffmpeg（Windows）
winget install Gyan.FFmpeg          # 装完请重开终端使 PATH 生效

# 2) 安装依赖
py -3.14 -m pip install flask PyMuPDF Pillow edge-tts numpy
py -3.14 -m pip install easyocr     # 默认本地 OCR 引擎，可选
# 也可以按需安装其它本地 OCR 引擎（二选一或都装）
py -3.14 -m pip install rapidocr_onnxruntime
py -3.14 -m pip install paddleocr paddlepaddle

# 3) 启动
py -3.14 app.py
```

启动时会打印依赖自检；随后浏览器打开 **http://127.0.0.1:5006** 即可使用（仅本机访问）。

完整安装/排错见 [README_解说视频生成器.md](README_解说视频生成器.md)。

---

## 🖱️ 使用（网页四步）

1. **选 PDF + 基本参数**：每片段时长默认 8 秒，默认按解说词自动延长；AI 自动生成旁白及去除提取文字中的换行和空格默认开启。也可设置页数、封面时长、页码范围、OCR 引擎与识别语言；需要时勾选 AI OCR 并填写视觉模型配置。
2. **载入并提取文字**：有文字层秒级；纯扫描件走 OCR，进度实时显示、可续跑。
3. **编辑旁白**：逐段改解说词，逐段可设时长。
4. **标题卡 + 配音 + 尺寸 + 字幕 → 生成**：可选择单语或 AI 中英双语字幕及颜色；点「生成视频」，页内预览并下载 MP4（/SRT）。

---

## 📁 项目结构

```
mk_dzdy/
├── app.py                     # Flask 服务与接口（程序入口）
├── pipeline.py                # 生成管线：抽页 / 合帧 / 标题卡 / OCR / TTS / 字幕 / 合成
├── index_html.py              # 前端网页（上传、调参、编辑旁白、进度、下载）
├── _ocr_worker.py             # OCR 子进程（Easy/Rapid/Paddle，简/繁，断点续跑）
├── _selftest.py               # 端到端自检脚本
├── fonts.conf / font.ttf      # 中文字体（楷体）
├── stop.bat                   # 停止服务的小脚本
├── sample/                    # 演示样例（输入 PDF / 输出 MP4）
└── tasks/                     # 运行时产物（已在 .gitignore 忽略）
```

---

## ⚠️ 说明

- **字体版权**：`font.ttf` 为华文楷体（STKaiti），属商业字体。如需公开分发，请自行确认授权，或替换为可自由分发的中文字体（同名放置即可）。
- **仅本机**：默认监听 `127.0.0.1:5006`。如需局域网访问，自行修改 `app.py` 的 `host`（注意安全）。
- 本项目为个人/学习用途的自动化小工具。

## 🙏 致谢

[PyMuPDF](https://pymupdf.readthedocs.io/) · [EasyOCR](https://github.com/JaidedAI/EasyOCR) · [edge-tts](https://github.com/rany2/edge-tts) · [FFmpeg](https://ffmpeg.org/) · [Flask](https://flask.palletsprojects.com/)

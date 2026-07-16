#!/usr/bin/env python3
"""端到端自检：构造带文字层的测试 PDF，跑通 prepare->generate->download。"""
import os, time, fitz
import app

# 1) 构造测试 PDF（带文字层，避免 OCR）
os.makedirs("tasks", exist_ok=True)
path = "tasks/_selftest.pdf"
doc = fitz.open()
for i in range(6):
    pg = doc.new_page()
    pg.insert_text((72, 120), f"这是第 {i+1} 页的测试内容，用于验证管线是否正常。", fontsize=20)
    pg.insert_text((72, 160), "大众电影 怀旧 解说 视频 生成 测试。", fontsize=20)
doc.save(path)
doc.close()
print("test pdf ->", path, os.path.getsize(path), "bytes")

c = app.app.test_client()

# 2) prepare
with open(path, "rb") as f:
    r = c.post("/api/prepare", data={
        "pdf": (f, "t.pdf"),
        "pages_per_clip": "2",
        "use_ocr": "false",
    }, content_type="multipart/form-data")
j = r.get_json()
assert "task_id" in j, j
tid = j["task_id"]
print("prepare task:", tid)

for _ in range(60):
    s = c.get("/api/status?task=" + tid).get_json()
    if s["stage"] in ("ready", "error"):
        break
    time.sleep(0.5)
print("prepare stage:", s["stage"], "| clips:", s["clips"], "| msg:", s["message"])
assert s["stage"] == "ready", s

# 3) generate (短时长，快速)
r = c.post("/api/generate", json={
    "task_id": tid,
    "narration": s["narration"],
    "pages_per_clip": 2,
    "clip_duration": 2,
    "title_duration": 1,
    "title": "测试", "subtitle": "", "feature": "", "feature2": "", "feature3": "", "tagline": "",
    "voice": "zh-CN-YunxiNeural", "rate": "+6%",
})
print("generate submit:", r.get_json())

for _ in range(180):
    s = c.get("/api/status?task=" + tid).get_json()
    if s["stage"] in ("done", "error"):
        break
    time.sleep(1)
print("gen stage:", s["stage"], "| msg:", s["message"])
assert s["stage"] == "done", s

# 4) download / verify
out = app.TASKS[tid]["output_path"]
print("output exists:", os.path.exists(out), "| size:", os.path.getsize(out) if os.path.exists(out) else 0)
assert os.path.exists(out) and os.path.getsize(out) > 10000

# verify with ffprobe
rc = os.system(f'ffprobe -v error -show_entries format=duration,size -of default=noprint_wrappers=1 "{out}"')
print("ffprobe rc:", rc)
print("SELFTEST OK")

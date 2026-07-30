# -*- coding: utf-8 -*-
"""前端页面 HTML (字符串)，由 app.py 引用为 INDEX_HTML。"""

INDEX_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI PDF解说视频生成器</title>
<style>
  * { box-sizing: border-box; }
  body { margin:0; font-family: -apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
         background:#1b1410; color:#eee; }
  .wrap { max-width:860px; margin:0 auto; padding:24px 18px 60px; }
  h1 { font-size:24px; color:#ffd28a; margin:0 0 4px; }
  .sub { color:#b8a98f; font-size:13px; margin-bottom:20px; }
  .card { background:#2a2018; border:1px solid #433426; border-radius:12px;
          padding:18px; margin-bottom:16px; }
  .card h2 { font-size:15px; margin:0 0 14px; color:#e8c89a; letter-spacing:1px; }
  label { display:block; font-size:13px; color:#cbb79a; margin:10px 0 4px; }
  input[type=text], input[type=number], select, textarea {
    width:100%; background:#1c150f; border:1px solid #4a3a2a; color:#eee;
    border-radius:8px; padding:9px 10px; font-size:14px; font-family:inherit; }
  textarea { resize:vertical; line-height:1.7; }
  input[type=color] { width:46px; height:34px; padding:2px; border:1px solid #4a3a2a;
                      border-radius:6px; background:#1c150f; cursor:pointer; }
  .seg-nar textarea { min-height:110px; font-size:15px; padding:10px 12px; }
  .row { display:flex; gap:12px; flex-wrap:wrap; }
  .row > div { flex:1; min-width:140px; }
  .grid2 { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
  .grid3 { display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px; }
  button { cursor:pointer; border:none; border-radius:9px; font-size:14px;
           font-weight:600; padding:11px 18px; transition:.15s; }
  .btn-main { background:linear-gradient(135deg,#e0a44a,#c8762e); color:#241606; }
  .btn-main:hover { filter:brightness(1.08); }
  .btn-2 { background:#3a2c1e; color:#e8c89a; border:1px solid #5a4632; }
  .btn-2:disabled { opacity:.4; cursor:not-allowed; }
  .btn-row { display:flex; gap:12px; margin-top:6px; }
  .hint { font-size:12px; color:#8c7c63; margin-top:4px; }
  #drop { border:2px dashed #5a4632; border-radius:12px; padding:26px; text-align:center;
          color:#b8a98f; cursor:pointer; transition:.15s; }
  #drop.hover { border-color:#e0a44a; background:#2e2218; color:#ffd28a; }
  #file-name { color:#e8c89a; font-size:13px; margin-top:8px; }
  .bar { height:10px; background:#1c150f; border-radius:6px; overflow:hidden; margin-top:8px;
         border:1px solid #4a3a2a; }
  .bar > i { display:block; height:100%; width:0; background:linear-gradient(90deg,#e0a44a,#c8762e);
             transition:width .3s; }
  #status { font-size:13px; color:#cbb79a; margin-top:8px; min-height:18px; }
  .seg-nar { border:1px solid #3a2c1e; border-radius:8px; padding:8px 10px; margin-bottom:8px;
             background:#211910; }
  .seg-nar b { color:#e0a44a; font-size:12px; }
  #video-preview { width:100%; border-radius:10px; margin-top:10px; background:#000; display:none; }
  .pill { display:inline-block; background:#3a2c1e; color:#e8c89a; border-radius:20px;
          padding:3px 12px; font-size:12px; margin-left:8px; }
  .ok { color:#7ed18a; }
  .err { color:#e88a7a; }
  a.dl { color:#ffd28a; text-decoration:none; font-weight:600; }
  .title-preview-layout { display:grid; grid-template-columns:minmax(260px,.85fr) minmax(320px,1.15fr);
                          gap:16px; align-items:start; margin-top:12px; }
  .title-preview-frame { min-height:190px; display:flex; align-items:center; justify-content:center;
                         background:#140f0b; border:1px solid #4a3a2a; border-radius:6px;
                         overflow:hidden; position:relative; }
  #title-preview-image { display:block; width:100%; height:auto; max-height:420px; object-fit:contain; }
  #title-preview-status { position:absolute; inset:0; display:flex; align-items:center;
                          justify-content:center; color:#8c7c63; font-size:12px; }
  @media (max-width:700px) {
    .title-preview-layout { grid-template-columns:1fr; }
    .grid2,.grid3 { grid-template-columns:1fr; }
  }
</style>
</head>
<body>
<div class="wrap">
  <h1>AI PDF解说视频生成器</h1>
  <div class="sub">上传《大众电影》式 PDF → 自动提取文字 → AI理解/生成旁白 → 生成 MP4。封面+标题卡自动生成。</div>

  <!-- 1. 上传 + 参数 -->
  <div class="card">
    <h2>① 选择 PDF 与基本参数</h2>
    <div id="drop">点击或拖拽 PDF 文件到此处
      <div id="file-name"></div>
    </div>
    <input type="file" id="pdf" accept="application/pdf" hidden>

    <div class="grid3" style="margin-top:14px;">
      <div><label>每片段时长(秒)</label>
        <input type="number" id="clip_duration" value="12" min="2" max="120" step="0.5">
        <div class="hint" id="clip_dur_hint">每个内容片段播放秒数</div></div>
      <div><label>每片段页数</label>
        <input type="number" id="pages_per_clip" value="2" min="1" max="8">
        <div class="hint">几页 PDF 拼成 1 个视频片段</div></div>
      <div><label>封面时长(秒)</label>
        <input type="number" id="title_duration" value="3" min="0" max="15" step="0.5"></div>
    </div>

    <div class="grid3" style="margin-top:8px; align-items:end;">
      <div>
        <label style="display:flex;align-items:center;gap:6px;color:#cbb79a;">
          <input type="checkbox" id="auto_duration"> 按解说词自动延长片段时长</label>
        <div class="hint">开启后「每片段时长」变为<b>最短</b>时长，旁白读完为止</div>
      </div>
      <div><label>片段最长时长(秒)</label>
        <input type="number" id="max_clip_duration" value="60" min="5" max="300" step="1"></div>
      <div><label>读完后留白(秒)</label>
        <input type="number" id="tail_pad" value="1" min="0" max="10" step="0.5"></div>
    </div>

    <div style="margin-top:10px;">
      <label>选择参与制作的页码（可选）</label>
      <input type="text" id="page_range" placeholder="如 1~10,15~20,30；留空 = 全部页">
      <div class="hint">只用这些页参与制作；支持 <b>~</b> 或 <b>-</b> 表示范围、逗号分隔，按填写顺序排列</div>
    </div>

    <div style="margin-top:10px; padding:10px 12px; border:1px solid #3a2c1e; border-radius:8px; background:#211910;">
      <label style="display:flex;align-items:center;gap:6px;color:#cbb79a;margin:0;">
        <input type="checkbox" id="use_ai_narration"> 使用AI自动生成旁白
      </label>
      <label style="display:flex;align-items:center;gap:6px;color:#cbb79a;margin:8px 0 0;">
        <input type="checkbox" id="use_ai_ocr"> 使用AI OCR识别纯图片文字
      </label>
      <div id="ai-config" style="display:none; margin-top:10px;">
        <div style="margin-bottom:8px;">
          <label>LLM 类型</label>
          <select id="llm_provider">
            <option value="openai" selected>通用 OpenAI 兼容接口</option>
            <option value="nvidia">NVIDIA 免费 API（限 40 rpm）</option>
            <option value="sensenova">SenseNova（按模型自动限速）</option>
          </select>
        </div>
        <div class="grid3">
          <div><label>LLM base_url</label><input type="text" id="llm_base_url" placeholder="https://api.openai.com/v1"></div>
          <div><label>API Key</label><input type="password" id="llm_api_key" placeholder="sk-..."></div>
          <div><label>Model</label><input type="text" id="llm_model" placeholder="gpt-4o-mini"></div>
        </div>
        <div class="grid2" style="margin-top:8px;">
          <div><label>每段AI旁白目标字数</label>
            <input type="number" id="narration_target_chars" value="200" min="40" max="400" step="10"></div>
          <div><label>LLM RPM 上限</label>
            <input type="number" id="llm_rpm" value="0" min="0" max="6000" step="1">
            <div class="hint">0 = 按供应商和模型自动设置；通用接口为不限速</div></div>
        </div>
        <div class="hint" id="ai-provider-hint">开启后，系统会先根据每个片段的 OCR 文本生成旁白，再继续后面的配音流程。</div>
      </div>
    </div>

    <div class="btn-row" style="flex-wrap:wrap;">
      <button class="btn-main" id="btn-prepare">载入并提取文字</button>
      <label style="display:flex;align-items:center;gap:6px;color:#cbb79a;font-size:13px;">
        <input type="checkbox" id="use_ocr" checked> 纯图片PDF启用OCR(更慢)</label>
      <label style="display:flex;align-items:center;gap:6px;color:#cbb79a;font-size:13px;">
        OCR引擎
        <select id="ocr_engine" style="width:auto;padding:6px 8px;">
          <option value="easyocr" selected>EasyOCR（当前默认）</option>
          <option value="rapidocr">RapidOCR（ONNX）</option>
          <option value="paddleocr">PaddleOCR（中文优化）</option>
        </select>
      </label>
      <label style="display:flex;align-items:center;gap:6px;color:#cbb79a;font-size:13px;">
        识别语言
        <select id="ocr_lang" style="width:auto;padding:6px 8px;">
          <option value="ch_sim" selected>简体中文 + 英文</option>
          <option value="ch_tra">繁体中文 + 英文</option>
        </select>
      </label>
      <label style="display:flex;align-items:center;gap:6px;color:#cbb79a;font-size:13px;">
        <input type="checkbox" id="compact_ocr_text"> 去除提取文字中的换行和空格
      </label>
    </div>
    <div class="hint">繁体材料请选「繁体中文」（简繁模型不同，不能混识别；首次用繁体需联网下载繁体模型）。</div>
    <div class="bar"><i id="bar1"></i></div>
    <div id="status1"></div>
  </div>

  <!-- 2. 旁白编辑 -->
  <div class="card" id="card-nar" style="display:none;">
    <h2>② 编辑旁白 <span class="pill" id="clip-pill">0 段</span></h2>
    <div class="hint" style="margin-bottom:10px;">每块 = 一个视频片段：左侧改旁白，右上「时长(秒)」可单独设置该片段时长（默认同步①里的每片段时长；开了「自动延长」则此值作为该片段的<b>最短</b>时长）。</div>
    <div class="btn-row" style="margin-bottom:10px;">
      <button class="btn-2" id="btn-regenerate-ai">重新生成AI旁白</button>
      <span class="hint">复用已提取文字，不会重新执行 OCR</span>
    </div>
    <div id="nar-list"></div>
  </div>

  <!-- 3. 标题与声音 -->
  <div class="card" id="card-opt" style="display:none;">
    <h2>③ 标题卡与配音设置</h2>
    <div class="grid2">
      <div><label>主标题</label><input type="text" id="title" value="人民画报"></div>
      <div><label>副标题(期号)</label><input type="text" id="subtitle" placeholder="如 1989年第11期 · 总第437期"></div>
      <div><label>徽标文字</label><input type="text" id="feature" placeholder="如 封面 青年演员 何晴"></div>
      <div><label>副信息1</label><input type="text" id="feature2" placeholder="如 首届中国电影节"></div>
      <div><label>副信息2</label><input type="text" id="feature3" placeholder="如 《开国大典》《本命年》"></div>
      <div><label>标语</label><input type="text" id="tagline" value="怀旧时光之旅"></div>
    </div>
    <div class="title-preview-layout">
      <div>
        <label>封面版式</label>
        <select id="title_card_style">
          <option value="classic" selected>经典自动版式（当前）</option>
          <option value="custom">自定义字号</option>
        </select>
        <div id="title-font-controls" class="grid2" style="display:none;margin-top:6px;">
          <div><label>主标题字号</label><input type="number" id="title_font_title" value="100" min="40" max="180" step="2"></div>
          <div><label>副标题字号</label><input type="number" id="title_font_subtitle" value="52" min="20" max="100" step="2"></div>
          <div><label>徽标字号</label><input type="number" id="title_font_badge" value="32" min="16" max="72" step="2"></div>
          <div><label>副信息字号</label><input type="number" id="title_font_info" value="34" min="16" max="72" step="2"></div>
          <div><label>标语字号</label><input type="number" id="title_font_tagline" value="28" min="14" max="64" step="2"></div>
        </div>
      </div>
      <div class="title-preview-frame">
        <img id="title-preview-image" alt="封面预览">
        <div id="title-preview-status">封面预览将在文字提取完成后显示</div>
      </div>
    </div>
    <div class="grid2" style="margin-top:8px;">
      <div><label>配音声音</label><select id="voice"></select></div>
      <div><label>语速</label><select id="rate"></select></div>
    </div>

    <div class="grid3" style="margin-top:8px; align-items:end;">
      <div><label>画面比例</label>
        <select id="aspect">
          <option value="16:9" selected>16:9（横屏）</option>
          <option value="9:16">9:16（竖屏/手机）</option>
          <option value="4:3">4:3</option>
          <option value="1:1">1:1（方形）</option>
          <option value="custom">自定义…</option>
        </select></div>
      <div id="custom-ar" style="display:none;"><label>自定义比例(宽:高)</label>
        <div style="display:flex;align-items:center;gap:6px;">
          <input type="number" id="custom_w" value="16" min="1" max="100" step="1" style="width:70px;">
          <span style="color:#cbb79a;">:</span>
          <input type="number" id="custom_h" value="9" min="1" max="100" step="1" style="width:70px;"></div></div>
      <div><label>清晰度(短边)</label>
        <select id="quality">
          <option value="1080" selected>1080（高清）</option>
          <option value="720">720（较高）</option>
          <option value="480">480（标清·更快）</option>
          <option value="1440">1440（更高·更慢）</option>
        </select></div>
    </div>
    <div class="hint" id="dim-hint">输出尺寸：1920 × 1080</div>

    <div class="grid2" style="margin-top:8px;">
      <div><label>字幕</label>
        <select id="subtitle_mode">
          <option value="none" selected>不生成字幕</option>
          <option value="srt">生成 SRT 字幕文件（随视频单独下载）</option>
          <option value="burn">把字幕烧进画面（硬字幕，始终显示）</option>
          <option value="burn_bilingual">中英双语硬字幕（英文由AI翻译）</option>
        </select>
        <div class="hint">字幕内容取自「编辑旁白」；烧录为硬字幕需重新编码，稍慢。</div>
      </div>
    </div>
    <div id="subtitle-style" class="grid3" style="display:none;margin-top:8px;">
      <div><label>中文颜色</label><input type="color" id="subtitle_zh_color" value="#66ff7a"></div>
      <div id="subtitle-en-color-wrap"><label>英文颜色</label><input type="color" id="subtitle_en_color" value="#ffffff"></div>
      <div><label>描边颜色</label><input type="color" id="subtitle_outline_color" value="#101010"></div>
    </div>
    <div class="hint" id="subtitle-style-hint" style="display:none;">粗体无衬线字幕：中文使用微软雅黑，英文使用 Arial。</div>

    <div class="btn-row">
      <button class="btn-main" id="btn-generate">生成视频</button>
    </div>
    <div class="bar"><i id="bar2"></i></div>
    <div id="status2"></div>
    <div id="applied-audio" class="hint"></div>
  </div>

  <!-- 4. 结果 -->
  <div class="card" id="card-out" style="display:none;">
    <h2>④ 成品</h2>
    <video id="video-preview" controls></video>
    <div id="out-links" style="margin-top:10px;"></div>
  </div>
</div>

<script>
let TASK_ID = null;

const $ = id => document.getElementById(id);
const AI_CFG_KEY = 'mk_dzdy_ai_cfg_v1';
const OCR_CFG_KEY = 'mk_dzdy_ocr_cfg_v1';
const SUBTITLE_CFG_KEY = 'mk_dzdy_subtitle_cfg_v1';
const TITLE_CFG_KEY = 'mk_dzdy_title_cfg_v1';
const AUDIO_CFG_KEY = 'mk_dzdy_audio_cfg_v1';

function loadAiCfg(){
  try { return JSON.parse(localStorage.getItem(AI_CFG_KEY) || '{}') || {}; }
  catch(e){ return {}; }
}
function saveAiCfg(){
  const data = {
    use_ai_narration: $('use_ai_narration').checked,
    use_ai_ocr: $('use_ai_ocr').checked,
    llm_provider: $('llm_provider').value,
    llm_base_url: $('llm_base_url').value,
    llm_api_key: $('llm_api_key').value,
    llm_model: $('llm_model').value,
    llm_rpm: $('llm_rpm').value,
    narration_target_chars: $('narration_target_chars').value,
    narration_target_chars_version: 2,
  };
  try { localStorage.setItem(AI_CFG_KEY, JSON.stringify(data)); }
  catch(e){}
}
function saveOcrCfg(){
  try { localStorage.setItem(OCR_CFG_KEY, JSON.stringify({
    ocr_engine: $('ocr_engine').value,
    compact_ocr_text: $('compact_ocr_text').checked,
  })); } catch(e){}
}
function loadOcrCfg(){
  try { return JSON.parse(localStorage.getItem(OCR_CFG_KEY) || '{}') || {}; }
  catch(e){ return {}; }
}
function saveSubtitleCfg(){
  const data = {
    subtitle_mode: $('subtitle_mode').value,
    subtitle_zh_color: $('subtitle_zh_color').value,
    subtitle_en_color: $('subtitle_en_color').value,
    subtitle_outline_color: $('subtitle_outline_color').value,
  };
  try { localStorage.setItem(SUBTITLE_CFG_KEY, JSON.stringify(data)); }
  catch(e){}
}
function loadSubtitleCfg(){
  try { return JSON.parse(localStorage.getItem(SUBTITLE_CFG_KEY) || '{}') || {}; }
  catch(e){ return {}; }
}
function loadAudioCfg(){
  try { return JSON.parse(localStorage.getItem(AUDIO_CFG_KEY) || '{}') || {}; }
  catch(e){ return {}; }
}
function saveAudioCfg(){
  try { localStorage.setItem(AUDIO_CFG_KEY, JSON.stringify({
    voice:$('voice').value, rate:$('rate').value, defaults_version:2
  })); } catch(e){}
}
function updateSubtitleUi(){
  const mode = $('subtitle_mode').value;
  const burn = mode === 'burn' || mode === 'burn_bilingual';
  $('subtitle-style').style.display = burn ? '' : 'none';
  $('subtitle-style-hint').style.display = burn ? '' : 'none';
  $('subtitle-en-color-wrap').style.display = mode === 'burn_bilingual' ? '' : 'none';
}
function saveTitleCfg(){
  const data = {title_card_style:$('title_card_style').value};
  ['title_font_title','title_font_subtitle','title_font_badge','title_font_info','title_font_tagline']
    .forEach(id=>data[id]=$(id).value);
  try { localStorage.setItem(TITLE_CFG_KEY, JSON.stringify(data)); }
  catch(e){}
}
function loadTitleCfg(){
  try { return JSON.parse(localStorage.getItem(TITLE_CFG_KEY) || '{}') || {}; }
  catch(e){ return {}; }
}
function updateTitleControls(){
  $('title-font-controls').style.display = $('title_card_style').value === 'custom' ? '' : 'none';
}
const NARR_SAVE_TIMERS = {};
function saveNarrationSegment(idx, text){
  if(!TASK_ID) return;
  fetch('/api/save_narration',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({task_id:TASK_ID, idx, text})
  }).catch(()=>{});
}
function debounceSaveNarration(idx, text){
  if(NARR_SAVE_TIMERS[idx]) clearTimeout(NARR_SAVE_TIMERS[idx]);
  NARR_SAVE_TIMERS[idx] = setTimeout(()=>saveNarrationSegment(idx, text), 450);
}
function syncAiCfgUi(){
  const on = $('use_ai_narration').checked;
  const aiOcrOn = $('use_ai_ocr').checked;
  const translateOn = $('subtitle_mode').value === 'burn_bilingual';
  const provider = $('llm_provider').value;
  const aiPipelineOn = on || aiOcrOn;
  const configOn = aiPipelineOn || translateOn;
  $('ai-config').style.display = configOn ? '' : 'none';
  if (aiPipelineOn) $('use_ocr').checked = true;
  $('use_ocr').disabled = aiPipelineOn;
  $('ocr_engine').disabled = aiOcrOn;
  ['llm_provider','llm_base_url','llm_api_key','llm_model','llm_rpm','narration_target_chars'].forEach(id=>{
    const el=$(id);
    if(el) el.disabled = !configOn;
  });
  if (provider === 'nvidia') {
    $('ai-provider-hint').textContent = 'NVIDIA 留空或填 0 时按 36 RPM 节流；也可在 RPM 上限中自行覆盖。';
  } else if (provider === 'sensenova') {
    $('ai-provider-hint').textContent = 'SenseNova 留空或填 0 时：6.7 Flash Lite/U1 Fast 按 270 RPM，DeepSeek V4 Flash 按 90 RPM；可自行覆盖。';
  } else if (translateOn && !aiPipelineOn) {
    $('ai-provider-hint').textContent = '双语字幕会使用这里的 LLM 配置批量翻译英文，不会改变旁白内容。';
  } else if (aiOcrOn && on) {
    $('ai-provider-hint').textContent = 'AI OCR 会逐页识别纯图片页面，AI 旁白再根据识别结果生成旁白；模型需要支持图片输入。';
  } else if (aiOcrOn) {
    $('ai-provider-hint').textContent = 'AI OCR 会逐页识别纯图片页面；模型需要支持图片输入，识别结果仍可在下一步编辑。';
  } else {
    $('ai-provider-hint').textContent = '开启后，系统会先根据每个片段的 OCR 文本生成旁白，再继续后面的配音流程。';
  }
}

const savedAiCfg = loadAiCfg();
if (savedAiCfg) {
  $('use_ai_narration').checked = !!savedAiCfg.use_ai_narration;
  $('use_ai_ocr').checked = !!savedAiCfg.use_ai_ocr;
  if (savedAiCfg.llm_provider !== undefined) $('llm_provider').value = savedAiCfg.llm_provider;
  if (savedAiCfg.llm_base_url !== undefined) $('llm_base_url').value = savedAiCfg.llm_base_url;
  if (savedAiCfg.llm_api_key !== undefined) $('llm_api_key').value = savedAiCfg.llm_api_key;
  if (savedAiCfg.llm_model !== undefined) $('llm_model').value = savedAiCfg.llm_model;
  if (savedAiCfg.llm_rpm !== undefined) $('llm_rpm').value = savedAiCfg.llm_rpm;
  if (savedAiCfg.narration_target_chars !== undefined &&
      !(Number(savedAiCfg.narration_target_chars) === 80 && !savedAiCfg.narration_target_chars_version)) {
    $('narration_target_chars').value = savedAiCfg.narration_target_chars;
  }
}
syncAiCfgUi();
['use_ai_narration','use_ai_ocr','llm_provider','llm_base_url','llm_api_key','llm_model','llm_rpm','narration_target_chars'].forEach(id=>{
  const el=$(id);
  if(!el) return;
  el.addEventListener('change', ()=>{ syncAiCfgUi(); saveAiCfg(); });
  el.addEventListener('input', saveAiCfg);
});
const savedOcrCfg = loadOcrCfg();
if (savedOcrCfg.ocr_engine) $('ocr_engine').value = savedOcrCfg.ocr_engine;
if (savedOcrCfg.compact_ocr_text !== undefined) $('compact_ocr_text').checked = !!savedOcrCfg.compact_ocr_text;
$('ocr_engine').addEventListener('change', saveOcrCfg);
$('compact_ocr_text').addEventListener('change', saveOcrCfg);
const savedSubtitleCfg = loadSubtitleCfg();
['subtitle_mode','subtitle_zh_color','subtitle_en_color','subtitle_outline_color'].forEach(id=>{
  if(savedSubtitleCfg[id] !== undefined) $(id).value = savedSubtitleCfg[id];
  $(id).addEventListener('change', ()=>{
    updateSubtitleUi(); syncAiCfgUi(); saveSubtitleCfg(); saveAiCfg();
  });
});
updateSubtitleUi();
syncAiCfgUi();
const savedTitleCfg = loadTitleCfg();
['title_card_style','title_font_title','title_font_subtitle','title_font_badge','title_font_info','title_font_tagline']
  .forEach(id=>{ if(savedTitleCfg[id] !== undefined) $(id).value=savedTitleCfg[id]; });
updateTitleControls();

// 填充声音/语速
fetch('/api/voices').then(r=>r.json()).then(d=>{
  const saved=loadAudioCfg();
  d.voices.forEach(v=>{ const o=document.createElement('option'); o.value=v[0]; o.textContent=v[1]; $('voice').appendChild(o); });
  d.rates.forEach(r=>{ const o=document.createElement('option'); o.value=r; o.textContent=r; $('rate').appendChild(o); });
  const voiceValues=d.voices.map(v=>v[0]);
  const savedVoice=(!saved.defaults_version && saved.voice==='zh-CN-YunxiNeural')?'zh-CN-YunyangNeural':saved.voice;
  const savedRate=(!saved.defaults_version && saved.rate==='+6%')?'+0%':saved.rate;
  $('voice').value=voiceValues.includes(savedVoice)?savedVoice:'zh-CN-YunyangNeural';
  $('rate').value=d.rates.includes(savedRate)?savedRate:'+0%';
  $('voice').addEventListener('change',saveAudioCfg);
  $('rate').addEventListener('change',saveAudioCfg);
}).catch(err=>{
  $('applied-audio').textContent='配音选项加载失败: '+(err.message||err);
});

// 文件选择
const drop=$('drop'), fileInput=$('pdf');
drop.onclick=()=>fileInput.click();
['dragover','dragenter'].forEach(e=>drop.addEventListener(e,ev=>{ev.preventDefault();drop.classList.add('hover');}));
['dragleave','drop'].forEach(e=>drop.addEventListener(e,ev=>{ev.preventDefault();drop.classList.remove('hover');}));
drop.addEventListener('drop',ev=>{ if(ev.dataTransfer.files[0]) setFile(ev.dataTransfer.files[0]); });
fileInput.onchange=()=>{ if(fileInput.files[0]) setFile(fileInput.files[0]); };
function setFile(f){ $('file-name').textContent='已选: '+f.name; window._file=f; }

// 自动时长开关：切换「每片段时长」的提示文案
$('auto_duration').addEventListener('change', e=>{
  $('clip_dur_hint').innerHTML = e.target.checked
    ? '此值为<b>最短</b>时长，旁白读完自动延长' : '每个内容片段播放秒数';
});

// 画面比例 / 清晰度：切换自定义输入 + 实时显示输出尺寸
function even(x){ x=Math.round(x); return x%2? x+1 : x; }
function calcDim(){
  const asp=$('aspect').value; let aw=16, ah=9;
  if(asp==='custom'){ aw=+$('custom_w').value||16; ah=+$('custom_h').value||9; }
  else { const p=asp.split(':'); aw=+p[0]; ah=+p[1]; }
  let q=Math.max(160,Math.min(2160,+$('quality').value||1080)), w,h;
  if(aw>=ah){ h=q; w=q*aw/ah; } else { w=q; h=q*ah/aw; }
  w=even(w); h=even(h);
  if(Math.max(w,h)>3840){ const s=3840/Math.max(w,h); w=even(w*s); h=even(h*s); }
  return [w,h];
}
function updateDimHint(){
  $('custom-ar').style.display = $('aspect').value==='custom' ? '' : 'none';
  const [w,h]=calcDim();
  $('dim-hint').textContent='输出尺寸：'+w+' × '+h+(h>w?'（竖屏）':(w>h?'（横屏）':'（方形）'));
}
['aspect','quality','custom_w','custom_h'].forEach(id=>{
  const el=$(id); if(el) el.addEventListener('change',updateDimHint);
  if(el) el.addEventListener('input',updateDimHint);
});
updateDimHint();

let TITLE_PREVIEW_TIMER=null, TITLE_PREVIEW_SEQ=0, TITLE_PREVIEW_URL='';
function titlePreviewPayload(){
  return {
    task_id:TASK_ID,
    title:$('title').value, subtitle:$('subtitle').value,
    feature:$('feature').value, feature2:$('feature2').value,
    feature3:$('feature3').value, tagline:$('tagline').value,
    aspect:$('aspect').value, custom_w:$('custom_w').value,
    custom_h:$('custom_h').value, quality:$('quality').value,
    title_card_style:$('title_card_style').value,
    title_font_title:$('title_font_title').value,
    title_font_subtitle:$('title_font_subtitle').value,
    title_font_badge:$('title_font_badge').value,
    title_font_info:$('title_font_info').value,
    title_font_tagline:$('title_font_tagline').value,
  };
}
function scheduleTitlePreview(delay=280){
  if(!TASK_ID) return;
  if(TITLE_PREVIEW_TIMER) clearTimeout(TITLE_PREVIEW_TIMER);
  TITLE_PREVIEW_TIMER=setTimeout(refreshTitlePreview,delay);
}
async function refreshTitlePreview(){
  if(!TASK_ID) return;
  const seq=++TITLE_PREVIEW_SEQ;
  const status=$('title-preview-status');
  status.style.display='flex'; status.textContent='正在生成封面预览…';
  try{
    const r=await fetch('/api/title_preview',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(titlePreviewPayload())
    });
    if(!r.ok){ const j=await r.json().catch(()=>({})); throw new Error(j.error||'预览失败'); }
    const blob=await r.blob();
    if(seq!==TITLE_PREVIEW_SEQ) return;
    if(TITLE_PREVIEW_URL) URL.revokeObjectURL(TITLE_PREVIEW_URL);
    TITLE_PREVIEW_URL=URL.createObjectURL(blob);
    $('title-preview-image').src=TITLE_PREVIEW_URL;
    status.style.display='none';
  }catch(e){
    if(seq===TITLE_PREVIEW_SEQ){ status.textContent='封面预览失败: '+e.message; }
  }
}
['title','subtitle','feature','feature2','feature3','tagline','aspect','quality','custom_w','custom_h',
 'title_card_style','title_font_title','title_font_subtitle','title_font_badge','title_font_info','title_font_tagline']
 .forEach(id=>{
   $(id).addEventListener('input',()=>{ updateTitleControls(); saveTitleCfg(); scheduleTitlePreview(); });
   $(id).addEventListener('change',()=>{ updateTitleControls(); saveTitleCfg(); scheduleTitlePreview(80); });
 });

// 载入并提取
$('btn-prepare').onclick=()=>{
  if(!window._file){ alert('请先选择 PDF 文件'); return; }
  saveAiCfg();
  const fd=new FormData();
  fd.append('pdf', window._file);
  fd.append('pages_per_clip', $('pages_per_clip').value);
  fd.append('use_ocr', $('use_ocr').checked ? 'true':'false');
  fd.append('ocr_engine', $('ocr_engine').value);
  fd.append('compact_ocr_text', $('compact_ocr_text').checked ? 'true':'false');
  fd.append('use_ai_narration', $('use_ai_narration').checked ? 'true':'false');
  fd.append('use_ai_ocr', $('use_ai_ocr').checked ? 'true':'false');
  fd.append('llm_provider', $('llm_provider').value);
  fd.append('llm_base_url', $('llm_base_url').value);
  fd.append('llm_api_key', $('llm_api_key').value);
  fd.append('llm_model', $('llm_model').value);
  fd.append('llm_rpm', $('llm_rpm').value);
  fd.append('narration_target_chars', $('narration_target_chars').value);
  fd.append('page_range', $('page_range').value);
  fd.append('ocr_lang', $('ocr_lang').value);
  $('status1').textContent='上传中…';
  fetch('/api/prepare',{method:'POST',body:fd})
    .then(r=>r.json().then(j=>({ok:r.ok, j})))
    .then(({ok, j})=>{
      if(!ok || j.error){ $('status1').textContent=(j && j.error) ? j.error : '上传失败'; return; }
      TASK_ID=j.task_id;
      pollPrepare();
    })
    .catch(err=>{
      $('status1').textContent='上传失败: '+(err && err.message ? err.message : err);
    });
};

function pollPrepare(){
  fetch('/api/status?task='+TASK_ID).then(r=>r.json()).then(st=>{
    const pct=Math.round((st.progress||0)*100);
    $('bar1').style.width=pct+'%';
    $('status1').textContent=st.message||'';
    if(st.stage==='ready'){
      renderNarration(st.narration);
      $('card-nar').style.display='block';
      $('card-opt').style.display='block';
      $('status1').textContent='';
      const ready=document.createElement('span');
      const aiFailed=(st.message||'').includes('AI 旁白') && (st.message||'').includes('失败');
      ready.className=aiFailed?'err':'ok';
      ready.textContent=(st.message||'文字提取完成')+'。可编辑旁白后点“生成视频”。';
      $('status1').appendChild(ready);
      scheduleTitlePreview(0);
      return;
    }
    if(st.stage==='error'){ $('status1').innerHTML='<span class="err">'+st.message+'</span>'; return; }
    setTimeout(pollPrepare, 1000);
  });
}

$('btn-regenerate-ai').onclick=()=>{
  if(!TASK_ID) return;
  if(!$('llm_base_url').value.trim() || !$('llm_model').value.trim()){
    alert('请先填写 LLM base_url 和 Model'); return;
  }
  if(!confirm('将使用原始提取文字覆盖当前旁白，确定重新生成吗？')) return;
  saveAiCfg();
  const payload={
    task_id:TASK_ID,
    llm_provider:$('llm_provider').value,
    llm_base_url:$('llm_base_url').value,
    llm_api_key:$('llm_api_key').value,
    llm_model:$('llm_model').value,
    llm_rpm:$('llm_rpm').value,
    narration_target_chars:$('narration_target_chars').value,
  };
  $('status1').textContent='正在提交AI旁白重写任务…';
  fetch('/api/regenerate_narration',{
    method:'POST', headers:{'Content-Type':'application/json'},
    body:JSON.stringify(payload)
  }).then(async r=>{
    const result=await r.json();
    if(!r.ok) throw new Error(result.error||'AI旁白重写请求失败');
    pollPrepare();
  }).catch(err=>{ $('status1').textContent=err.message; });
};

function renderNarration(arr){
  $('clip-pill').textContent=arr.length+' 段';
  const list=$('nar-list'); list.innerHTML='';
  const gdur=$('clip_duration').value;
  arr.forEach((t,i)=>{
    const d=document.createElement('div'); d.className='seg-nar';
    const head=document.createElement('div');
    head.style.cssText='display:flex;justify-content:space-between;align-items:center;';
    head.innerHTML='<b>片段 '+(i+1)+'</b>';
    const durWrap=document.createElement('label');
    durWrap.style.cssText='margin:0;font-size:12px;color:#cbb79a;display:flex;align-items:center;gap:5px;';
    durWrap.innerHTML='时长(秒)';
    const di=document.createElement('input');
    di.type='number'; di.min='0.5'; di.step='0.5'; di.className='seg-dur'; di.value=gdur;
    di.style.cssText='width:74px;padding:5px 7px;';
    durWrap.appendChild(di); head.appendChild(durWrap);
    d.appendChild(head);
    const ta=document.createElement('textarea'); ta.rows=5; ta.value=t; ta.dataset.idx=i;
    ta.style.marginTop='6px';
    ta.addEventListener('input', ()=>debounceSaveNarration(i, ta.value));
    d.appendChild(ta); list.appendChild(d);
  });
}

// 全局「每片段时长」改动时，同步刷新各片段的时长框
$('clip_duration').addEventListener('input',()=>{
  document.querySelectorAll('#nar-list .seg-dur').forEach(el=>{ el.value=$('clip_duration').value; });
});

// 生成视频
$('btn-generate').onclick=()=>{
  if($('subtitle_mode').value==='burn_bilingual' &&
     (!$('llm_base_url').value.trim() || !$('llm_model').value.trim())){
    alert('中英双语字幕需要填写 LLM base_url 和 Model'); return;
  }
  const selectedVoice=$('voice').value;
  const selectedVoiceLabel=$('voice').selectedOptions[0]?.textContent||selectedVoice;
  const selectedRate=$('rate').value;
  if(!selectedVoice || !selectedRate){ alert('配音声音或语速尚未加载完成'); return; }
  saveAudioCfg();
  const clip_durations=[...document.querySelectorAll('#nar-list .seg-dur')].map(t=>+t.value||+$('clip_duration').value);
  const payload={
    task_id:TASK_ID, clip_durations,
    pages_per_clip:$('pages_per_clip').value,
    clip_duration:$('clip_duration').value,
    title_duration:$('title_duration').value,
    auto_duration:$('auto_duration').checked,
    max_clip_duration:$('max_clip_duration').value,
    tail_pad:$('tail_pad').value,
    aspect:$('aspect').value,
    custom_w:$('custom_w').value, custom_h:$('custom_h').value,
    quality:$('quality').value,
    subtitle_mode:$('subtitle_mode').value,
    subtitle_zh_color:$('subtitle_zh_color').value,
    subtitle_en_color:$('subtitle_en_color').value,
    subtitle_outline_color:$('subtitle_outline_color').value,
    llm_provider:$('llm_provider').value,
    llm_base_url:$('llm_base_url').value,
    llm_api_key:$('llm_api_key').value,
    llm_model:$('llm_model').value,
    llm_rpm:$('llm_rpm').value,
    title_card_style:$('title_card_style').value,
    title_font_title:$('title_font_title').value,
    title_font_subtitle:$('title_font_subtitle').value,
    title_font_badge:$('title_font_badge').value,
    title_font_info:$('title_font_info').value,
    title_font_tagline:$('title_font_tagline').value,
    title:$('title').value, subtitle:$('subtitle').value,
    feature:$('feature').value, feature2:$('feature2').value,
    feature3:$('feature3').value, tagline:$('tagline').value,
    voice:selectedVoice, rate:selectedRate,
  };
  $('applied-audio').textContent='本次提交：'+selectedVoiceLabel+'，语速 '+selectedRate;
  $('status2').textContent='提交中…';
  fetch('/api/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
    .then(async r=>{
      const result=await r.json();
      if(!r.ok) throw new Error(result.error||'生成请求提交失败');
      pollGen();
    })
    .catch(err=>{ $('status2').textContent=err.message; });
};

function pollGen(){
  fetch('/api/status?task='+TASK_ID).then(r=>r.json()).then(st=>{
    const pct=Math.round((st.progress||0)*100);
    $('bar2').style.width=pct+'%';
    $('status2').textContent=st.message||'';
    if(st.voice_label && st.rate){
      $('applied-audio').textContent='后端实际采用：'+st.voice_label+'，语速 '+st.rate;
    }
    if(st.stage==='done'){
      $('card-out').style.display='block';
      const v=$('video-preview'); v.src='/api/download/'+TASK_ID+'?t='+Date.now(); v.style.display='block';
      let links='<a class="dl" href="/api/download/'+TASK_ID+'">⬇ 下载 MP4</a>';
      if(st.srt_ready){ links+='&nbsp;&nbsp;<a class="dl" href="/api/download_srt/'+TASK_ID+'">⬇ 下载 SRT 字幕</a>'; }
      $('out-links').innerHTML=links;
      $('status2').innerHTML='<span class="ok">完成！可预览/下载。</span>';
      return;
    }
    if(st.stage==='error'){
      $('status2').textContent='';
      const error=document.createElement('span');
      error.className='err'; error.textContent=st.message||'生成失败';
      const hint=document.createElement('div');
      hint.className='hint'; hint.textContent='可直接再次点击“生成视频”，将复用已提取文字，不会重新执行 OCR。';
      $('status2').append(error,hint);
      return;
    }
    setTimeout(pollGen, 1000);
  });
}
</script>
</body>
</html>
"""

# -*- coding: utf-8 -*-
"""前端页面 HTML (字符串)，由 app.py 引用为 INDEX_HTML。"""

INDEX_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI PDF解说视频生成器</title>
<link rel="icon" type="image/svg+xml" href="/static/favicon.svg">
<link rel="shortcut icon" href="/static/favicon.svg">
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
  input[type=text], input[type=password], input[type=number], select, textarea {
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
  .seg-content { display:grid; grid-template-columns:minmax(150px,220px) minmax(0,1fr);
                 gap:10px; align-items:start; margin-top:6px; }
  .seg-thumb-wrap { min-height:110px; display:flex; align-items:center; justify-content:center;
                    background:#140f0b; border:1px solid #4a3a2a; border-radius:6px;
                    overflow:hidden; color:#8c7c63; font-size:11px; text-align:center; }
  .seg-thumb { display:block; width:100%; height:150px; object-fit:contain; }
  .seg-thumb-empty { padding:10px; }
  .seg-ai-failure { display:flex; align-items:center; gap:8px; flex-wrap:wrap;
                    margin-top:8px; color:#e88a7a; font-size:12px; }
  .seg-ai-failure button { padding:6px 10px; font-size:12px; }
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
  .identity-row { display:grid; grid-template-columns:minmax(220px,1fr) auto; gap:10px; align-items:end; }
  .identity-row > * { min-width:0; }
  .identity-actions { display:flex; gap:8px; flex-wrap:wrap; }
  .identity-actions button { padding:9px 12px; }
  .task-list { margin-top:14px; border-top:1px solid #433426; }
  .task-row { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:12px;
              padding:12px 0; border-bottom:1px solid #3a2c1e; align-items:center; }
  .task-name { color:#eee; font-size:14px; overflow-wrap:anywhere; }
  .task-meta { color:#8c7c63; font-size:12px; margin-top:4px; }
  .task-actions { display:flex; gap:7px; flex-wrap:wrap; justify-content:flex-end; }
  .task-actions button { padding:7px 10px; font-size:12px; }
  .btn-danger { background:#4a2020; color:#f0b0a8; border:1px solid #713432; }
  @media (max-width:700px) {
    .title-preview-layout { grid-template-columns:1fr; }
    .grid2,.grid3 { grid-template-columns:1fr; }
    .seg-content { grid-template-columns:1fr; }
    .identity-row,.task-row { grid-template-columns:1fr; }
    .task-actions { justify-content:flex-start; }
    .identity-actions button { flex:1 1 calc(50% - 4px); }
  }
</style>
</head>
<body>
<div class="wrap">
  <h1>AI PDF解说视频生成器</h1>
  <div class="sub">上传《大众电影》式 PDF → 自动提取文字 → AI理解/生成旁白 → 生成 MP4。封面+标题卡自动生成。</div>

  <div class="card">
    <h2>客户端身份与我的任务</h2>
    <div class="identity-row">
      <div>
        <label>客户端恢复密钥</label>
        <input type="password" id="client-token" readonly>
      </div>
      <div class="identity-actions">
        <button class="btn-2" id="btn-copy-token">复制密钥</button>
        <button class="btn-2" id="btn-import-token">导入密钥</button>
        <button class="btn-2" id="btn-new-identity">新建身份</button>
        <button class="btn-2" id="btn-refresh-tasks">刷新任务</button>
      </div>
    </div>
    <div id="identity-status" class="hint"></div>
    <div id="task-list" class="task-list"></div>
  </div>

  <!-- 1. 上传 + 参数 -->
  <div class="card">
    <h2>① 选择 PDF 与基本参数</h2>
    <div id="drop">点击或拖拽 PDF 文件到此处
      <div id="file-name"></div>
    </div>
    <input type="file" id="pdf" accept="application/pdf" hidden>

    <div class="grid3" style="margin-top:14px;">
      <div><label>每片段时长(秒)</label>
        <input type="number" id="clip_duration" value="8" min="2" max="120" step="0.5">
        <div class="hint" id="clip_dur_hint">此值为<b>最短</b>时长，旁白读完自动延长</div></div>
      <div><label>每片段页数</label>
        <input type="number" id="pages_per_clip" value="2" min="1" max="8">
        <div class="hint">几页 PDF 拼成 1 个视频片段</div></div>
      <div><label>封面时长(秒)</label>
        <input type="number" id="title_duration" value="3" min="0" max="15" step="0.5"></div>
    </div>

    <div class="grid3" style="margin-top:8px; align-items:end;">
      <div>
        <label style="display:flex;align-items:center;gap:6px;color:#cbb79a;">
          <input type="checkbox" id="auto_duration" checked> 按解说词自动延长片段时长</label>
        <div class="hint">开启后「每片段时长」变为<b>最短</b>时长，旁白读完为止</div>
      </div>
      <div><label>片段最长时长(秒)</label>
        <input type="number" id="max_clip_duration" value="60" min="5" max="300" step="1"></div>
      <div><label>读完后留白(秒)</label>
        <input type="number" id="tail_pad" value="1" min="0" max="10" step="0.5"></div>
    </div>

    <div style="margin-top:10px;">
      <label>选择参与制作的页码（可选）
        <span id="pdf-page-count" class="hint" style="display:inline;margin-left:8px;">PDF总页数：待载入</span>
      </label>
      <input type="text" id="page_range" placeholder="如 1~10,15~20,30；留空 = 全部页">
      <div class="hint">只用这些页参与制作；支持 <b>~</b> 或 <b>-</b> 表示范围、逗号分隔，按填写顺序排列</div>
    </div>

    <div style="margin-top:10px; padding:10px 12px; border:1px solid #3a2c1e; border-radius:8px; background:#211910;">
      <label style="display:flex;align-items:center;gap:6px;color:#cbb79a;margin:0;">
        <input type="checkbox" id="use_ai_narration" checked> 使用AI自动生成旁白
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
        <input type="checkbox" id="compact_ocr_text" checked> 去除提取文字中的换行和空格
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
          <option value="cinematic">金色电影海报版式</option>
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
const ACTIVE_TASK_KEY = 'mk_dzdy_active_task_v1';
const CLIENT_TOKEN_KEY = 'mk_dzdy_client_token_v1';

function isValidClientToken(value){
  return /^[0-9a-f]{64}$/i.test(String(value||''));
}
function generateClientToken(){
  const bytes=new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join('');
}
function loadOrCreateClientToken(){
  let token='';
  try { token=localStorage.getItem(CLIENT_TOKEN_KEY)||''; } catch(e){}
  if(!isValidClientToken(token)){
    token=generateClientToken();
    try { localStorage.setItem(CLIENT_TOKEN_KEY,token); } catch(e){}
  }
  return token.toLowerCase();
}
let CLIENT_TOKEN=loadOrCreateClientToken();
const ORIGINAL_FETCH=window.fetch.bind(window);
window.fetch=(input, init={})=>{
  const requestUrl=new URL(input instanceof Request ? input.url : input, location.href);
  if(requestUrl.origin!==location.origin || !requestUrl.pathname.startsWith('/api/')){
    return ORIGINAL_FETCH(input,init);
  }
  const headers=new Headers(init.headers || (input instanceof Request ? input.headers : undefined));
  headers.set('Authorization','Bearer '+CLIENT_TOKEN);
  return ORIGINAL_FETCH(input,{...init,headers});
};

function setClientToken(token){
  token=String(token||'').trim().toLowerCase();
  if(!isValidClientToken(token)) throw new Error('恢复密钥必须是 64 位十六进制字符');
  localStorage.setItem(CLIENT_TOKEN_KEY,token);
  localStorage.removeItem(ACTIVE_TASK_KEY);
  CLIENT_TOKEN=token;
}

const TASK_STAGE_LABELS={
  preparing:'准备中', extract:'提取文字', ocr:'OCR', ai:'AI旁白',
  ready:'待生成', generating:'生成中', title:'生成封面', render:'渲染画面',
  tts:'生成配音', audio:'处理音频', mux:'合成视频', done:'已完成',
  error:'失败', cancelled:'已取消'
};
function taskStageLabel(task){
  if(task.delete_pending) return '等待删除';
  if(task.cancel_requested) return '正在取消';
  return TASK_STAGE_LABELS[task.stage] || task.stage || '未知';
}
function resumeManagedTask(task){
  TASK_ID=task.task_id;
  rememberActiveTask(task.phase==='generate' ? 'generate' : 'prepare');
  location.reload();
}
async function cancelManagedTask(task){
  if(!confirm('确定取消这个任务吗？')) return;
  const r=await fetch('/api/tasks/'+encodeURIComponent(task.task_id)+'/cancel',{method:'POST'});
  const result=await r.json().catch(()=>({}));
  if(!r.ok) throw new Error(result.error||'取消失败');
  refreshTaskList();
}
async function deleteManagedTask(task){
  if(!confirm('确定删除这个任务及其服务器文件吗？此操作不可撤销。')) return;
  const r=await fetch('/api/tasks/'+encodeURIComponent(task.task_id),{method:'DELETE'});
  const result=await r.json().catch(()=>({}));
  if(!r.ok) throw new Error(result.error||'删除失败');
  const active=loadActiveTask();
  if(active.task_id===task.task_id){ TASK_ID=null; forgetActiveTask(); }
  refreshTaskList();
}
function renderTaskList(tasks){
  const list=$('task-list'); list.innerHTML='';
  if(!tasks.length){
    const empty=document.createElement('div');
    empty.className='hint'; empty.style.padding='12px 0'; empty.textContent='暂无任务';
    list.appendChild(empty); return;
  }
  tasks.forEach(task=>{
    const row=document.createElement('div'); row.className='task-row';
    const info=document.createElement('div');
    const name=document.createElement('div'); name.className='task-name';
    name.textContent=task.file_name||'PDF 任务';
    const meta=document.createElement('div'); meta.className='task-meta';
    const pct=Math.round((task.progress||0)*100);
    meta.textContent=taskStageLabel(task)+' · '+pct+'% · '+new Date(task.updated_at*1000).toLocaleString();
    info.append(name,meta);
    const actions=document.createElement('div'); actions.className='task-actions';
    const resume=document.createElement('button'); resume.className='btn-2';
    resume.textContent=task.stage==='done'?'查看成品':'打开任务';
    resume.onclick=()=>resumeManagedTask(task); actions.appendChild(resume);
    const busy=!['ready','done','error','cancelled'].includes(task.stage);
    if(busy && !task.cancel_requested){
      const cancel=document.createElement('button'); cancel.className='btn-2'; cancel.textContent='取消';
      cancel.onclick=()=>cancelManagedTask(task).catch(e=>alert(e.message)); actions.appendChild(cancel);
    }
    const del=document.createElement('button'); del.className='btn-danger'; del.textContent='删除';
    del.onclick=()=>deleteManagedTask(task).catch(e=>alert(e.message)); actions.appendChild(del);
    row.append(info,actions); list.appendChild(row);
  });
}
async function refreshTaskList(){
  $('identity-status').textContent='正在读取任务…';
  try{
    const r=await fetch('/api/tasks',{cache:'no-store'});
    const result=await r.json().catch(()=>({}));
    if(!r.ok) throw new Error(result.error||'任务列表读取失败');
    renderTaskList(result.tasks||[]);
    $('identity-status').textContent='';
  }catch(e){ $('identity-status').textContent=e.message; }
}

$('client-token').value=CLIENT_TOKEN;
$('btn-copy-token').onclick=async()=>{
  try{
    await navigator.clipboard.writeText(CLIENT_TOKEN);
    $('identity-status').textContent='恢复密钥已复制';
  }catch(e){
    $('client-token').type='text'; $('client-token').select();
    $('identity-status').textContent='浏览器未允许自动复制，已选中密钥';
  }
};
$('btn-import-token').onclick=()=>{
  const token=prompt('输入客户端恢复密钥');
  if(token===null) return;
  try { setClientToken(token); location.reload(); }
  catch(e){ alert(e.message); }
};
$('btn-new-identity').onclick=()=>{
  if(!confirm('新建身份后，本机将不再显示当前身份的任务。请先备份恢复密钥。')) return;
  setClientToken(generateClientToken()); location.reload();
};
$('btn-refresh-tasks').onclick=refreshTaskList;

function rememberActiveTask(phase){
  if(!TASK_ID) return;
  try {
    localStorage.setItem(ACTIVE_TASK_KEY+'_'+CLIENT_TOKEN.slice(0,16), JSON.stringify({
      task_id:TASK_ID, phase:phase === 'generate' ? 'generate' : 'prepare'
    }));
  } catch(e){}
}
function loadActiveTask(){
  try {
    const scopedKey=ACTIVE_TASK_KEY+'_'+CLIENT_TOKEN.slice(0,16);
    let raw=localStorage.getItem(scopedKey);
    if(raw===null){
      raw=localStorage.getItem(ACTIVE_TASK_KEY);
      if(raw!==null){ localStorage.setItem(scopedKey,raw); localStorage.removeItem(ACTIVE_TASK_KEY); }
    }
    return JSON.parse(raw || '{}') || {};
  }
  catch(e){ return {}; }
}
function forgetActiveTask(){
  try { localStorage.removeItem(ACTIVE_TASK_KEY+'_'+CLIENT_TOKEN.slice(0,16)); } catch(e){}
}
async function fetchTaskStatus(){
  const r=await fetch('/api/status?task='+encodeURIComponent(TASK_ID), {cache:'no-store'});
  const st=await r.json().catch(()=>({}));
  if(!r.ok){
    const err=new Error(st.error || '任务状态查询失败');
    err.status=r.status;
    throw err;
  }
  return st;
}

function loadAiCfg(){
  try {
    const scopedKey=AI_CFG_KEY+'_'+CLIENT_TOKEN.slice(0,16);
    let raw=localStorage.getItem(scopedKey);
    if(raw===null){
      raw=localStorage.getItem(AI_CFG_KEY);
      if(raw!==null){
        localStorage.setItem(scopedKey,raw);
        localStorage.removeItem(AI_CFG_KEY);
      }
    }
    return JSON.parse(raw || '{}') || {};
  }
  catch(e){ return {}; }
}
function saveLocalAiCfg(data){
  localStorage.setItem(AI_CFG_KEY+'_'+CLIENT_TOKEN.slice(0,16),JSON.stringify(data));
}
function remoteApiSettingsPayload(){
  return {
    use_ai_narration:$('use_ai_narration').checked,
    use_ai_ocr:$('use_ai_ocr').checked,
    llm_provider:$('llm_provider').value,
    llm_base_url:$('llm_base_url').value,
    llm_model:$('llm_model').value,
    llm_rpm:$('llm_rpm').value,
    narration_target_chars:$('narration_target_chars').value,
  };
}
let REMOTE_API_SETTINGS_TIMER=null;
function scheduleRemoteApiSettingsSave(){
  if(REMOTE_API_SETTINGS_TIMER) clearTimeout(REMOTE_API_SETTINGS_TIMER);
  REMOTE_API_SETTINGS_TIMER=setTimeout(async()=>{
    try{
      await fetch('/api/client/settings',{
        method:'PUT',headers:{'Content-Type':'application/json'},
        body:JSON.stringify(remoteApiSettingsPayload())
      });
    }catch(e){}
  },500);
}
async function loadRemoteApiSettings(){
  try{
    const r=await fetch('/api/client/settings',{cache:'no-store'});
    const result=await r.json().catch(()=>({}));
    if(!r.ok) return;
    const cfg=result.settings||{};
    if(!Object.keys(cfg).length){ scheduleRemoteApiSettingsSave(); return; }
    if(cfg.use_ai_narration!==undefined) $('use_ai_narration').checked=!!cfg.use_ai_narration;
    if(cfg.use_ai_ocr!==undefined) $('use_ai_ocr').checked=!!cfg.use_ai_ocr;
    ['llm_provider','llm_base_url','llm_model','llm_rpm','narration_target_chars'].forEach(id=>{
      if(cfg[id]!==undefined) $(id).value=cfg[id];
    });
    syncAiCfgUi();
    const local=loadAiCfg();
    local.use_ai_narration=$('use_ai_narration').checked;
    local.use_ai_ocr=$('use_ai_ocr').checked;
    ['llm_provider','llm_base_url','llm_model','llm_rpm','narration_target_chars'].forEach(id=>local[id]=$(id).value);
    local.narration_target_chars_version=2;
    saveLocalAiCfg(local);
  }catch(e){}
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
  try { saveLocalAiCfg(data); }
  catch(e){}
  scheduleRemoteApiSettingsSave();
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
  if (savedAiCfg.use_ai_narration !== undefined) $('use_ai_narration').checked = !!savedAiCfg.use_ai_narration;
  if (savedAiCfg.use_ai_ocr !== undefined) $('use_ai_ocr').checked = !!savedAiCfg.use_ai_ocr;
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
loadRemoteApiSettings();
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
function setFile(f){
  $('file-name').textContent='已选: '+f.name;
  $('pdf-page-count').textContent='PDF总页数：上传后读取';
  window._file=f;
}

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
      rememberActiveTask('prepare');
      refreshTaskList();
      pollPrepare();
    })
    .catch(err=>{
      $('status1').textContent='上传失败: '+(err && err.message ? err.message : err);
    });
};

function showReadyTask(st){
  renderNarration(st.narration || [], st);
  $('card-nar').style.display='block';
  $('card-opt').style.display='block';
  $('status1').textContent='';
  const ready=document.createElement('span');
  const aiFailed=(st.message||'').includes('AI 旁白') && (st.message||'').includes('失败');
  ready.className=aiFailed?'err':'ok';
  ready.textContent=(st.message||'文字提取完成')+'。可编辑旁白后点“生成视频”。';
  $('status1').appendChild(ready);
  scheduleTitlePreview(0);
}
function showTaskWorkspace(st){
  if(st.narration && st.narration.length) renderNarration(st.narration, st);
  $('card-nar').style.display='block';
  $('card-opt').style.display='block';
}
function setStatusText(statusId, text, className=''){
  const target=$(statusId); target.textContent='';
  const span=document.createElement('span');
  if(className) span.className=className;
  span.textContent=text;
  target.appendChild(span);
}
function handleMissingTask(statusId){
  TASK_ID=null;
  forgetActiveTask();
  setStatusText(statusId,'上次任务在服务器上已不存在，请重新上传 PDF。','err');
  refreshTaskList();
}
function pollPrepare(){
  fetchTaskStatus().then(st=>{
    const pct=Math.round((st.progress||0)*100);
    $('bar1').style.width=pct+'%';
    $('status1').textContent=st.message||'';
    if(Number(st.pdf_page_count||0)>0){
      $('pdf-page-count').textContent='PDF总页数：'+st.pdf_page_count+' 页';
    }
    if(st.stage==='ready'){
      rememberActiveTask('prepare');
      showReadyTask(st);
      refreshTaskList();
      return;
    }
    if(st.stage==='error'){ setStatusText('status1',st.message||'任务失败','err'); return; }
    if(st.stage==='cancelled'){
      setStatusText('status1','任务已取消','err');
      refreshTaskList(); return;
    }
    setTimeout(pollPrepare, 1000);
  }).catch(err=>{
    if(err.status===404){ handleMissingTask('status1'); return; }
    $('status1').textContent='与服务器连接中断，正在自动重试…';
    setTimeout(pollPrepare, 3000);
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
    rememberActiveTask('prepare');
    pollPrepare();
  }).catch(err=>{ $('status1').textContent=err.message; });
};

function renderNarration(arr, st={}){
  $('clip-pill').textContent=arr.length+' 段';
  const list=$('nar-list'); list.innerHTML='';
  const gdur=$('clip_duration').value;
  const failedIndices=new Set((st.ai_failed_indices||[]).map(Number));
  const failureReasons=st.ai_failure_reasons||{};
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
    const body=document.createElement('div'); body.className='seg-content';
    const thumbWrap=document.createElement('div'); thumbWrap.className='seg-thumb-wrap';
    const thumb=document.createElement('img'); thumb.className='seg-thumb';
    thumb.alt='片段 '+(i+1)+' 图片预览'; thumb.loading='lazy';
    thumb.src='/api/clip_preview/'+encodeURIComponent(TASK_ID)+'/'+i+'?v='+Date.now();
    thumb.onerror=()=>{
      thumbWrap.textContent='图片预览不可用';
      thumbWrap.classList.add('seg-thumb-empty');
    };
    thumbWrap.appendChild(thumb);
    const ta=document.createElement('textarea'); ta.rows=5; ta.value=t; ta.dataset.idx=i;
    ta.style.marginTop='0';
    ta.addEventListener('input', ()=>debounceSaveNarration(i, ta.value));
    body.append(thumbWrap,ta);
    d.appendChild(body);
    if(failedIndices.has(i)){
      const failure=document.createElement('div'); failure.className='seg-ai-failure';
      const failureText=document.createElement('span');
      failureText.textContent='AI旁白生成失败，当前保留原始文本';
      const reason=failureReasons[String(i)]||'';
      if(reason) failureText.title=reason;
      const retry=document.createElement('button');
      retry.type='button'; retry.className='btn-2';
      retry.textContent='单独重试 AI 旁白';
      retry.onclick=()=>retryAiNarrationSegment(i,retry);
      failure.append(failureText,retry);
      d.appendChild(failure);
    }
    list.appendChild(d);
  });
}

function retryAiNarrationSegment(idx, button){
  if(!TASK_ID) return;
  if(!$('llm_base_url').value.trim() || !$('llm_model').value.trim()){
    alert('请先填写 LLM base_url 和 Model'); return;
  }
  saveAiCfg();
  button.disabled=true; button.textContent='重试中…';
  $('status1').textContent='正在单独重试第 '+(idx+1)+' 段 AI 旁白…';
  const payload={
    task_id:TASK_ID, idx,
    llm_provider:$('llm_provider').value,
    llm_base_url:$('llm_base_url').value,
    llm_api_key:$('llm_api_key').value,
    llm_model:$('llm_model').value,
    llm_rpm:$('llm_rpm').value,
    narration_target_chars:$('narration_target_chars').value,
  };
  fetch('/api/regenerate_narration_segment',{
    method:'POST', headers:{'Content-Type':'application/json'},
    body:JSON.stringify(payload)
  }).then(async r=>{
    const result=await r.json();
    if(!r.ok) throw new Error(result.error||'单段 AI 旁白重试失败');
    rememberActiveTask('prepare');
    pollPrepare();
  }).catch(err=>{
    button.disabled=false; button.textContent='单独重试 AI 旁白';
    $('status1').textContent=err.message;
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
      rememberActiveTask('generate');
      pollGen();
    })
    .catch(err=>{ $('status2').textContent=err.message; });
};

function showCompletedTask(st){
  showTaskWorkspace(st);
  $('bar2').style.width='100%';
  $('card-out').style.display='block';
  const downloadBase='/api/download/'+encodeURIComponent(TASK_ID);
  const previewParams=new URLSearchParams({t:String(Date.now())});
  if(st.asset_ticket) previewParams.set('ticket',st.asset_ticket);
  const v=$('video-preview'); v.src=downloadBase+'?'+previewParams.toString(); v.style.display='block';
  const links=$('out-links'); links.innerHTML='';
  const downloadParams=new URLSearchParams({download:'1'});
  if(st.asset_ticket) downloadParams.set('ticket',st.asset_ticket);
  const videoLink=document.createElement('a');
  videoLink.className='dl'; videoLink.href=downloadBase+'?'+downloadParams.toString();
  videoLink.download='AI_PDF_video.mp4';
  videoLink.textContent='下载 MP4'; links.appendChild(videoLink);
  if(st.srt_ready){
    const sep=document.createTextNode('　');
    const srtLink=document.createElement('a');
    srtLink.className='dl';
    const srtParams=new URLSearchParams();
    if(st.asset_ticket) srtParams.set('ticket',st.asset_ticket);
    srtLink.href='/api/download_srt/'+encodeURIComponent(TASK_ID)+'?'+srtParams.toString();
    srtLink.download='AI_PDF_subtitles.srt';
    srtLink.textContent='下载 SRT 字幕'; links.append(sep,srtLink);
  }
  const coverSep=document.createTextNode('　');
  const coverLink=document.createElement('a');
  coverLink.className='dl';
  const coverParams=new URLSearchParams({download:'1'});
  if(st.asset_ticket) coverParams.set('ticket',st.asset_ticket);
  coverLink.href='/api/download_cover/'+encodeURIComponent(TASK_ID)+'?'+coverParams.toString();
  coverLink.download='AI_PDF_cover.png';
  coverLink.textContent='下载封面图片';
  links.append(coverSep,coverLink);
  $('status2').innerHTML='<span class="ok">完成！可预览/下载。</span>';
}
function showGenerationError(st){
  showTaskWorkspace(st);
  $('status2').textContent='';
  const error=document.createElement('span');
  error.className='err'; error.textContent=st.message||'生成失败';
  const hint=document.createElement('div');
  hint.className='hint'; hint.textContent='可直接再次点击“生成视频”，将复用已提取文字，不会重新执行 OCR。';
  $('status2').append(error,hint);
}
function pollGen(){
  fetchTaskStatus().then(st=>{
    const pct=Math.round((st.progress||0)*100);
    $('bar2').style.width=pct+'%';
    $('status2').textContent=st.message||'';
    if(st.voice_label && st.rate){
      $('applied-audio').textContent='后端实际采用：'+st.voice_label+'，语速 '+st.rate;
    }
    if(st.stage==='done'){
      rememberActiveTask('generate');
      showCompletedTask(st);
      refreshTaskList();
      return;
    }
    if(st.stage==='error'){
      showGenerationError(st);
      return;
    }
    if(st.stage==='cancelled'){
      showGenerationError({narration:st.narration,message:'任务已取消'});
      refreshTaskList(); return;
    }
    setTimeout(pollGen, 1000);
  }).catch(err=>{
    if(err.status===404){ handleMissingTask('status2'); return; }
    $('status2').textContent='与服务器连接中断，正在自动重试…';
    setTimeout(pollGen, 3000);
  });
}

async function restoreActiveTask(){
  const saved=loadActiveTask();
  if(!saved.task_id) return;
  TASK_ID=String(saved.task_id);
  $('status1').textContent='正在恢复上次任务…';
  try{
    const st=await fetchTaskStatus();
    if(st.stage==='done'){
      rememberActiveTask('generate');
      showCompletedTask(st);
      return;
    }
    if(st.stage==='ready'){
      rememberActiveTask('prepare');
      showReadyTask(st);
      return;
    }
    const generationPhase=saved.phase==='generate' || !!st.voice;
    if(st.stage==='error'){
      if(generationPhase) showGenerationError(st);
      else setStatusText('status1',st.message||'任务失败','err');
      return;
    }
    if(generationPhase){
      rememberActiveTask('generate');
      showTaskWorkspace(st);
      $('status2').textContent='已恢复任务，正在读取生成进度…';
      pollGen();
    }else{
      rememberActiveTask('prepare');
      $('status1').textContent='已恢复任务，正在读取处理进度…';
      pollPrepare();
    }
  }catch(err){
    if(err.status===404){ handleMissingTask('status1'); return; }
    $('status1').textContent='暂时无法连接服务器；保留了任务记录，刷新页面后会继续恢复。';
  }
}

restoreActiveTask();
refreshTaskList();
</script>
</body>
</html>
"""

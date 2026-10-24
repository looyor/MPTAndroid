# -*- coding: utf-8 -*-
"""
Bootstrap for the MoneyPrinterTurbo Android app.
Run by Chaquopy from Java (MainActivity). It:
  1. Configures runtime paths (MPT_HOME, ffmpeg) via environment variables.
  2. Imports the FastAPI application (app.asgi:app).
  3. Replaces the placeholder "/" route with a mobile WebUI (served from the
     same origin so the WebView can call the REST API without CORS).
  4. Adds a small /api/v1/mpt_config endpoint so the UI can persist settings.
  5. Starts uvicorn in a background thread on 127.0.0.1:8080.
"""

import os
import threading

# These are set by Java through start_server() BEFORE anything imports app.config.
MPT_HOME = None
FFMPEG_PATH = None

# --- Mobile WebUI (single page, served by FastAPI at "/") ----------------------
UI_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>MoneyPrinterTurbo</title>
<style>
  :root{
    --bg:#0b0c10; --card:#15171e; --accent:#e50914; --accent2:#1f6feb;
    --text:#e6e6e6; --muted:#9aa0a6; --ok:#2ea043; --warn:#d29922; --err:#f85149;
    --input:#21242c; --border:#2a2e37;
  }
  *{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
  body{margin:0;background:var(--bg);color:var(--text);
       font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"PingFang SC","Microsoft YaHei",sans-serif;
       font-size:15px;line-height:1.5}
  .wrap{max-width:720px;margin:0 auto;padding:14px 14px 60px}
  h1{font-size:20px;margin:6px 0 2px}
  .sub{color:var(--muted);font-size:12px;margin-bottom:14px}
  .card{background:var(--card);border:1px solid var(--border);border-radius:14px;
        padding:14px;margin-bottom:14px}
  .card h2{font-size:15px;margin:0 0 10px;color:#fff;display:flex;align-items:center;gap:8px}
  label{display:block;font-size:12px;color:var(--muted);margin:10px 0 5px}
  input,select,textarea{width:100%;background:var(--input);border:1px solid var(--border);
        color:var(--text);border-radius:10px;padding:10px;font-size:14px;outline:none}
  textarea{min-height:110px;resize:vertical}
  .row{display:flex;gap:10px}
  .row>*{flex:1}
  button{background:var(--accent);color:#fff;border:0;border-radius:10px;
          padding:11px 14px;font-size:14px;font-weight:600;cursor:pointer}
  button.sec{background:var(--accent2)}
  button.ghost{background:transparent;border:1px solid var(--border);color:var(--text)}
  button:active{opacity:.85}
  .hint{font-size:11px;color:var(--muted);margin-top:6px}
  .log{background:#0d0f13;border:1px solid var(--border);border-radius:10px;
       padding:10px;font-size:12px;color:var(--muted);white-space:pre-wrap;
       max-height:200px;overflow:auto;margin-top:10px}
  .badge{font-size:11px;padding:2px 8px;border-radius:20px;background:#222;border:1px solid var(--border)}
  .badge.run{color:var(--warn)} .badge.done{color:var(--ok)} .badge.err{color:var(--err)}
  video{width:100%;border-radius:10px;background:#000;margin-top:8px}
  a.dl{display:inline-block;margin-top:8px;color:var(--accent2);text-decoration:none;
       font-size:13px;font-weight:600}
  .collapsed .body{display:none}
  .toggle{float:right;color:var(--muted);font-size:12px;cursor:pointer}
  .pill{display:inline-block;font-size:11px;color:var(--muted);margin-left:6px}
</style>
</head>
<body>
<div class="wrap">
  <h1>MoneyPrinterTurbo <span class="badge">Android</span></h1>
  <div class="sub">输入主题 → AI 生成文案 → 配音 + 素材 → 输出短视频</div>

  <div class="card" id="cfgCard">
    <h2>① 配置 <span class="toggle" onclick="toggleCfg()">展开/收起</span></h2>
    <div class="body" style="display:none">
      <label>大模型提供商</label>
      <select id="provider">
        <option value="openai">OpenAI</option>
        <option value="deepseek">DeepSeek</option>
        <option value="qwen">通义千问 (DashScope)</option>
        <option value="moonshot">Kimi / Moonshot</option>
        <option value="gemini">Google Gemini</option>
        <option value="groq">Groq</option>
      </select>
      <label>API Key</label>
      <input id="apiKey" type="text" placeholder="sk-...">
      <label>Base URL（可选，留空用默认）</label>
      <input id="baseUrl" type="text" placeholder="https://api.openai.com/v1">
      <label>模型名（可选，留空用默认）</label>
      <input id="modelName" type="text" placeholder="gpt-4o-mini">
      <label>Pexels 素材 Key（免费，用于视频素材，必填）</label>
      <input id="pexels" type="text" placeholder="从 pexels.com/api 获取">
      <button class="sec" onclick="saveConfig()">保存配置</button>
      <div class="hint">首次使用需配置：① 至少一个大模型 Key；② Pexels Key（免费）用于下载视频素材。保存后下方即可生成。</div>
    </div>
  </div>

  <div class="card">
    <h2>② 生成</h2>
    <label>视频主题 / 关键词</label>
    <input id="subject" type="text" placeholder="例如：春天的花海，治愈系短视频">
    <button class="ghost" onclick="genScript()">AI 生成文案</button>
    <label>文案（可手动修改）</label>
    <textarea id="script" placeholder="在此填写或自动生成视频文案..."></textarea>
    <div class="row">
      <div>
        <label>配音</label>
        <select id="voice">
          <option value="zh-CN-XiaoxiaoNeural-Female">中文·晓晓(女)</option>
          <option value="zh-CN-YunxiNeural-Male">中文·云希(男)</option>
          <option value="zh-CN-YunyangNeural-Male">中文·云扬(男)</option>
          <option value="en-US-AriaNeural-Female">English·Aria(女)</option>
          <option value="en-US-GuyNeural-Male">English·Guy(男)</option>
          <option value="ja-JP-NanamiNeural-Female">日本語·Nanami(女)</option>
        </select>
      </div>
      <div>
        <label>画面比例</label>
        <select id="aspect">
          <option value="9:16">竖屏 9:16</option>
          <option value="16:9">横屏 16:9</option>
          <option value="1:1">方形 1:1</option>
        </select>
      </div>
    </div>
    <button onclick="genVideo()">▶ 生成视频</button>
  </div>

  <div class="card">
    <h2>③ 状态 <span id="stateBadge" class="badge"></span></h2>
    <div id="progressBox" style="display:none">
      <div id="progressText" class="hint">进度：0%</div>
    </div>
    <div id="result"></div>
    <div id="log" class="log"></div>
  </div>
</div>

<script>
const API="";  // same-origin
function log(m){const e=document.getElementById('log');e.textContent+=m+"\n";e.scrollTop=e.scrollHeight;}
function toggleCfg(){const b=document.querySelector('#cfgCard .body');b.style.display=b.style.display==='none'?'block':'none';}

async function saveConfig(){
  const body={
    provider:document.getElementById('provider').value,
    api_key:document.getElementById('apiKey').value.trim(),
    base_url:document.getElementById('baseUrl').value.trim(),
    model_name:document.getElementById('modelName').value.trim(),
    pexels_api_key:document.getElementById('pexels').value.trim()
  };
  try{
    const r=await fetch(API+"/api/v1/mpt_config",{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const j=await r.json();
    if(j && (j.status===200||(j.data&&j.status===200))) alert('配置已保存 ✅');
    else alert('保存失败：'+(j.message||'未知错误'));
  }catch(e){alert('请求失败：'+e.message);}
}

async function genScript(){
  const subject=document.getElementById('subject').value.trim();
  if(!subject){alert('请先填写主题');return;}
  log('正在生成文案...');
  try{
    const r=await fetch(API+"/api/v1/scripts",{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({video_subject:subject,video_language:"",paragraph_number:1})});
    const j=await r.json();
    if(j && j.data && j.data.video_script){
      document.getElementById('script').value=j.data.video_script;
      log('文案已生成 ✅');
    }else{
      log('生成失败：'+(j.message||JSON.stringify(j)));
      alert('文案生成失败：'+(j.message||''));
    }
  }catch(e){log('错误：'+e.message);alert('请求失败：'+e.message);}
}

let pollTimer=null;
async function genVideo(){
  const subject=document.getElementById('subject').value.trim();
  const script=document.getElementById('script').value.trim();
  if(!script){alert('请先生成或填写文案');return;}
  document.getElementById('result').innerHTML='';
  document.getElementById('progressBox').style.display='block';
  setBadge('', '');
  log('正在创建视频任务...');
  try{
    const r=await fetch(API+"/api/v1/videos",{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        video_subject:subject||" ", video_script:script,
        video_aspect:document.getElementById('aspect').value,
        voice_name:document.getElementById('voice').value,
        video_language:"", subtitle_enabled:true
      })});
    const j=await r.json();
    if(j && j.data && j.data.task_id){
      log('任务已创建：'+j.data.task_id);
      pollTask(j.data.task_id);
    }else{
      log('创建失败：'+(j.message||JSON.stringify(j)));
      alert('创建失败：'+(j.message||''));
    }
  }catch(e){log('错误：'+e.message);alert('请求失败：'+e.message);}
}

function setBadge(text,cls){const b=document.getElementById('stateBadge');b.className='badge '+(cls||'');b.textContent=text;}

async function pollTask(taskId){
  if(pollTimer) clearInterval(pollTimer);
  pollTimer=setInterval(async ()=>{
    try{
      const r=await fetch(API+"/api/v1/tasks/"+taskId);
      const j=await r.json();
      const d=j.data||{};
      const state=d.state; const prog=d.progress||0;
      document.getElementById('progressText').textContent='进度：'+prog+'%';
      if(state===-1){clearInterval(pollTimer);setBadge('失败','err');log('任务失败：'+(d.error||'未知'));alert('生成失败：'+(d.error||''));}
      else if(state===1){clearInterval(pollTimer);setBadge('完成','done');showResult(d.videos||[]);log('视频生成完成 ✅');}
      else{setBadge('进行中','run');}
    }catch(e){/* ignore transient */}
  },2000);
}

function showResult(videos){
  const box=document.getElementById('result');
  if(!videos.length){box.innerHTML='<div class="hint">未返回视频文件。</div>';return;}
  let html='';
  videos.forEach(v=>{
    const url=API+v;
    html+='<video controls src="'+url+'"></video>'+
          '<a class="dl" href="'+url+'" download>⬇ 下载视频</a><br>';
  });
  box.innerHTML=html;
}

log('界面已加载，请先完成「配置」再生成。');
</script>
</body>
</html>"""


def start_server(mpt_home, ffmpeg_path):
    global MPT_HOME, FFMPEG_PATH
    MPT_HOME = mpt_home
    FFMPEG_PATH = ffmpeg_path

    # Critical: these env vars must be set BEFORE importing app.config, because
    # the config module resolves runtime_root() and the ffmpeg binary at import.
    os.environ["MPT_HOME"] = mpt_home
    if ffmpeg_path and os.path.isfile(ffmpeg_path):
        os.environ["IMAGEIO_FFMPEG_EXE"] = ffmpeg_path
        # Safety net: any code that shells out to `ffmpeg` by name (instead of
        # going through utils.get_ffmpeg_binary) will still find our binary.
        ffmpeg_dir = os.path.dirname(ffmpeg_path)
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")

    import uvicorn
    from fastapi import FastAPI, Request
    from fastapi.responses import HTMLResponse

    from app import config
    from app.config import config as cfg_module
    import app.asgi as asgi

    app = asgi.app

    # Replace the placeholder "/" StaticFiles mount with the mobile WebUI so the
    # WebView and the REST API share the same origin (no CORS needed).
    for i, route in enumerate(list(app.router.routes)):
        if getattr(route, "path", None) == "/":
            app.router.routes.pop(i)
            break

    @app.get("/")
    def index():
        return HTMLResponse(UI_HTML)

    @app.post("/api/v1/mpt_config")
    def mpt_config(payload: dict):
        provider = (payload.get("provider") or "openai").lower()
        cfg_module.app["llm_provider"] = provider
        ak = payload.get("api_key", "") or ""
        bu = payload.get("base_url", "") or ""
        mn = payload.get("model_name", "") or ""
        mapping = {
            "openai": ("openai_api_key", "openai_base_url", "openai_model_name"),
            "gemini": ("gemini_api_key", None, "gemini_model_name"),
            "qwen": ("qwen_api_key", None, "qwen_model_name"),
            "deepseek": ("deepseek_api_key", "deepseek_base_url", "deepseek_model_name"),
            "moonshot": ("moonshot_api_key", "moonshot_base_url", "moonshot_model_name"),
            "groq": ("groq_api_key", "groq_base_url", "groq_model_name"),
        }
        fields = mapping.get(provider)
        if fields:
            # All LLM keys live inside the [app] config section, read by
            # config.config_key(provider_id, suffix). Writing module attributes
            # would never be read nor persisted by save_config().
            cfg_module.app[fields[0]] = ak
            if fields[1]:
                cfg_module.app[fields[1]] = bu
            if fields[2]:
                cfg_module.app[fields[2]] = mn
        pexels = payload.get("pexels_api_key", "") or ""
        cfg_module.app["pexels_api_keys"] = [pexels] if pexels else []
        cfg_module.save_config()
        return {"status": 200, "message": "saved"}

    def _run():
        uvicorn.run(app, host="127.0.0.1", port=8080, log_level="warning")

    t = threading.Thread(target=_run, daemon=True)
    t.start()

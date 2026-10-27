# -*- coding: utf-8 -*-
"""
MoneyPrinterTurbo Android —— 轻量后端（无 FastAPI / 无 pydantic）

纯标准库 HTTP 服务 + requests 直连大模型 + edge-tts 配音（微软在线，
国内直连、可设超时，避免旧 gTTS 访问 Google 无限阻塞）+ PIL 渲染字幕 +
直接用内置 ffmpeg 合成视频。所有第三方依赖只有 requests / edge-tts / pillow，
都能在 Chaquopy(Android, aarch64) 上正常安装，规避 pydantic-core 等
无法在安卓编译的 Rust 扩展。

由 bootstrap.start_server() 在后台线程中调用 run()。

内置「模型市场」：12 家厂商、20+ 免费/低价模型。选模型时 Base URL 自动联动，
并提供「测试是否可用」按钮，用你的 Key 实测该模型能否调通。
"""

import json
import math
import os
import re
import subprocess
import tempfile
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import requests
import shutil

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except Exception as e:  # pragma: no cover
    Image = None
    ImageDraw = None
    ImageFont = None
    ImageOps = None
    _PIL_ERROR = e

# --------------------------------------------------------------------------- #
# 全局状态
# --------------------------------------------------------------------------- #
MPT_HOME = None
FFMPEG_PATH = None
CONFIG_PATH = None
ASSET_ROOT = None  # .../python/app/_assets/resource
DOWNLOAD_DIR = None  # 手机 Download/Ai视频 导出目录（由 Java 侧传入）

TASKS = {}          # task_id -> dict(state, progress, videos, error, logs)
TASKS_LOCK = threading.Lock()

# 各厂商的 OpenAI 兼容端点、模型与免费额度信息。
# free=True 表示该模型/层级当前有免费额度或永久免费（免费额度用完/过期后可能转计费）。
PROVIDERS = {
    "zhipu": {
        "name": "智谱 GLM（国内·永久免费）",
        "region": "国内",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "key_url": "https://open.bigmodel.cn/usercenter/apikeys",
        "models": [
            {"id": "glm-4.7-flash", "name": "GLM-4.7-Flash（永久免费）", "free": True},
            {"id": "glm-4-flash", "name": "GLM-4-Flash（免费）", "free": True},
            {"id": "glm-4-plus", "name": "GLM-4-Plus（强力·计费）", "free": False},
        ],
    },
    "siliconflow": {
        "name": "硅基流动 SiliconFlow（国内·免费开源）",
        "region": "国内",
        "base_url": "https://api.siliconflow.cn/v1",
        "key_url": "https://cloud.siliconflow.cn/account/ak",
        "models": [
            {"id": "deepseek-ai/DeepSeek-V3", "name": "DeepSeek-V3（免费额度）", "free": True},
            {"id": "Qwen/Qwen2.5-7B-Instruct", "name": "Qwen2.5-7B（免费）", "free": True},
            {"id": "Qwen/Qwen2.5-14B-Instruct", "name": "Qwen2.5-14B（免费额度）", "free": True},
            {"id": "Pro/deepseek-ai/DeepSeek-R1", "name": "DeepSeek-R1（强力·计费）", "free": False},
        ],
    },
    "deepseek": {
        "name": "DeepSeek（国内·赠金）",
        "region": "国内",
        "base_url": "https://api.deepseek.com/v1",
        "key_url": "https://platform.deepseek.com/api_keys",
        "models": [
            {"id": "deepseek-chat", "name": "DeepSeek-V3（deepseek-chat·赠金）", "free": True},
            {"id": "deepseek-reasoner", "name": "DeepSeek-R1（deepseek-reasoner·赠金）", "free": False},
        ],
    },
    "qwen": {
        "name": "通义千问 Qwen（国内·阿里）",
        "region": "国内",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "key_url": "https://dashscope.console.aliyun.com/apiKey",
        "models": [
            {"id": "qwen-turbo", "name": "Qwen-Turbo（便宜·免费额度）", "free": True},
            {"id": "qwen-plus", "name": "Qwen-Plus（均衡·免费额度）", "free": True},
            {"id": "qwen-max", "name": "Qwen-Max（最强·计费）", "free": False},
        ],
    },
    "moonshot": {
        "name": "Kimi / Moonshot（国内）",
        "region": "国内",
        "base_url": "https://api.moonshot.cn/v1",
        "key_url": "https://platform.moonshot.cn/console/api-keys",
        "models": [
            {"id": "moonshot-v1-8k", "name": "Kimi 8K（免费额度）", "free": True},
            {"id": "moonshot-v1-32k", "name": "Kimi 32K（免费额度）", "free": True},
            {"id": "moonshot-v1-128k", "name": "Kimi 128K（长文本·免费额度）", "free": False},
        ],
    },
    "gemini": {
        "name": "Google Gemini（海外·免费层）",
        "region": "海外",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "key_url": "https://aistudio.google.com/apikey",
        "models": [
            {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash（免费层）", "free": True},
            {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash（免费层）", "free": True},
        ],
    },
    "groq": {
        "name": "Groq（海外·免费·极快）",
        "region": "海外",
        "base_url": "https://api.groq.com/openai/v1",
        "key_url": "https://console.groq.com/keys",
        "models": [
            {"id": "llama-3.3-70b-versatile", "name": "Llama 3.3 70B（免费）", "free": True},
            {"id": "llama-3.1-8b-instant", "name": "Llama 3.1 8B（免费·极速）", "free": True},
        ],
    },
    "openrouter": {
        "name": "OpenRouter（聚合·大量免费）",
        "region": "海外",
        "base_url": "https://openrouter.ai/api/v1",
        "key_url": "https://openrouter.ai/keys",
        "models": [
            {"id": "deepseek/deepseek-chat-v3.1:free", "name": "DeepSeek V3.1 :free", "free": True},
            {"id": "meta-llama/llama-3.3-70b-instruct:free", "name": "Llama 3.3 70B :free", "free": True},
            {"id": "google/gemini-2.5-flash:free", "name": "Gemini 2.5 Flash :free", "free": True},
        ],
    },
    "openai": {
        "name": "OpenAI（海外·需绑卡）",
        "region": "海外",
        "base_url": "https://api.openai.com/v1",
        "key_url": "https://platform.openai.com/api-keys",
        "models": [
            {"id": "gpt-4o-mini", "name": "GPT-4o mini（低价·需绑卡）", "free": False},
        ],
    },
    "nvidia": {
        "name": "NVIDIA NIM（海外·免费开源）",
        "region": "海外",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "key_url": "https://build.nvidia.com/",
        "models": [
            {"id": "meta/llama-3.1-8b-instruct", "name": "Llama 3.1 8B（免费）", "free": True},
            {"id": "deepseek-ai/deepseek-r1", "name": "DeepSeek-R1（免费）", "free": True},
        ],
    },
    "mistral": {
        "name": "Mistral AI（海外·免费额度）",
        "region": "海外",
        "base_url": "https://api.mistral.ai/v1",
        "key_url": "https://console.mistral.ai/",
        "models": [
            {"id": "mistral-small-latest", "name": "Mistral Small（免费额度）", "free": True},
        ],
    },
    "local": {
        "name": "本地大模型 / 自定义（Ollama、LM Studio、vLLM…）",
        "region": "本地/自定义",
        "base_url": "http://127.0.0.1:11434/v1",
        "key_url": "",
        "models": [
            {"id": "qwen2.5:7b", "name": "示例：Ollama 本地模型（请改成你的模型名）", "free": True},
            {"id": "llama3.1:8b", "name": "示例：Llama 3.1 8B（本地）", "free": True},
        ],
    },
}

# 这些提供商通常不需要 API Key（本地/自建服务），允许留空直接运行。
NO_KEY_PROVIDERS = ("local", "custom")


def provider_needs_key(provider):
    return (provider or "").lower() not in NO_KEY_PROVIDERS


def providers_payload():
    out = []
    for k, v in PROVIDERS.items():
        item = dict(v)
        item["key"] = k
        out.append(item)
    return out


def log(task_id, msg):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    if task_id is not None:
        with TASKS_LOCK:
            t = TASKS.get(task_id)
            if t is not None:
                t["logs"].append(line)


def load_config():
    cfg = {
        "provider": "zhipu",
        "api_key": "",
        "base_url": "",
        "model_name": "",
        "pexels_api_key": "",
    }
    try:
        if CONFIG_PATH and os.path.isfile(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            cfg.update({k: data.get(k, cfg[k]) for k in cfg})
    except Exception:
        pass
    return cfg


def save_config(cfg):
    try:
        if CONFIG_PATH:
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("save_config error: %s" % e, flush=True)


def ffmpeg_bin():
    return FFMPEG_PATH or os.environ.get("MPT_FFMPEG") or "ffmpeg"


def run_ffmpeg(args, task_id=None, timeout=600):
    cmd = [ffmpeg_bin()] + args
    log(task_id, "ffmpeg " + " ".join(args[:6]) + (" ..." if len(args) > 6 else ""))
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    if p.returncode != 0:
        err = p.stderr.decode("utf-8", "ignore")
        log(task_id, "ffmpeg 返回 %d: %s" % (p.returncode, err[-500:]))
        raise RuntimeError("ffmpeg 失败(%d)" % p.returncode)
    return p


# --------------------------------------------------------------------------- #
# 大模型
# --------------------------------------------------------------------------- #
def llm_base_model(provider, cfg):
    p = PROVIDERS.get(provider, PROVIDERS["openai"])
    base = p["base_url"]
    default_model = p["models"][0]["id"]
    base = (cfg.get("base_url") or "").strip() or base
    model = (cfg.get("model_name") or "").strip() or default_model
    return base.rstrip("/"), model


def chat_complete(provider, cfg, messages, temperature=0.8, timeout=120):
    base, model = llm_base_model(provider, cfg)
    api_key = (cfg.get("api_key") or "").strip()
    url = base + "/chat/completions"
    payload = {"model": model, "messages": messages, "temperature": temperature}
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    r = requests.post(url, json=payload, headers=headers, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"].strip()


def generate_script(subject, cfg, word_count=None):
    provider = (cfg.get("provider") or "openai").lower()
    # 字数约束（仅对中文文案有意义）
    wc = None
    try:
        wc = int(word_count) if word_count not in (None, "", "0") else None
    except Exception:
        wc = None
    sys_prompt = (
        "你是一个短视频文案助手。请根据主题写一段适合配音的短视频口播文案，"
        "语言与主题一致（中文主题用中文）。要求：口语化、有节奏、"
        "不要分点、不要 markdown、不要括号里的动作提示。直接输出文案正文。"
    )
    if wc and wc > 0:
        wc = max(50, min(2000, wc))
        sys_prompt += (
            "正文严格控制在 %d 字左右（按中文字符数计），内容要充实连贯、"
            "自然成段，不要为了凑字数而重复或堆砌。" % wc
        )
    user_prompt = "主题：%s" % subject
    text = chat_complete(provider, cfg, [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_prompt},
    ])
    # 去掉可能的代码块包裹
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text).strip()
    return text


# --------------------------------------------------------------------------- #
# 配音（edge-tts，微软在线 TTS）
# --------------------------------------------------------------------------- #
def gtts_lang(voice):
    v = (voice or "").lower()
    if v.startswith("zh"):
        return "zh-CN"
    if v.startswith("ja"):
        return "ja"
    if v.startswith("ko"):
        return "ko"
    if v.startswith("en"):
        return "en"
    if v.startswith("fr"):
        return "fr"
    if v.startswith("de"):
        return "de"
    if v.startswith("es"):
        return "es"
    if v.startswith("ru"):
        return "ru"
    return "zh-CN"


def tts_to_file(text, voice, out_path, timeout=60):
    """用 edge-tts（微软在线 TTS，国内直连）生成配音。

    返回音频时长（秒）估计值；超时/失败返回 None（后续用静音兜底）。
    关键：用 asyncio.wait_for 加超时，避免像旧 gTTS 那样访问 Google
    无限阻塞，从而导致「进度一直 0%」且永不报错。
    """
    lang = gtts_lang(voice)
    try:
        import asyncio
        import edge_tts

        async def _gen():
            # voice 形如 zh-CN-XiaoxiaoNeural（不含 -Female 后缀）
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(out_path)

        asyncio.run(asyncio.wait_for(_gen(), timeout=timeout))
        if not (os.path.isfile(out_path) and os.path.getsize(out_path) > 0):
            raise RuntimeError("edge-tts 未产出有效音频")
        return estimate_duration(text, lang)
    except Exception as e:
        print("tts(edge) error: %s" % e, flush=True)
        try:
            if os.path.isfile(out_path):
                os.remove(out_path)
        except Exception:
            pass
        return None


def estimate_duration(text, lang):
    text = re.sub(r"\s+", "", text)
    if lang.startswith("zh"):
        return max(1.5, len(text) * 0.28)
    # 英文按词
    words = len(re.findall(r"[A-Za-z]+", text))
    return max(1.5, words * 0.5)


# --------------------------------------------------------------------------- #
# 画面渲染（PIL）—— 渐变背景 + 居中字幕
# --------------------------------------------------------------------------- #
def load_font(size):
    candidates = [
        os.path.join(ASSET_ROOT, "fonts", "MicrosoftYaHeiBold.ttc"),
        os.path.join(ASSET_ROOT, "fonts", "MicrosoftYaHeiNormal.ttc"),
        os.path.join(ASSET_ROOT, "fonts", "STHeitiMedium.ttc"),
        os.path.join(ASSET_ROOT, "fonts", "STHeitiLight.ttc"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                continue
    return ImageFont.load_default()


def wrap_cjk(text, font, max_w):
    """按字符换行（兼容中英文混排）。"""
    lines, cur = [], ""
    for ch in text:
        test = cur + ch
        if font.getlength(test) > max_w and cur:
            lines.append(cur)
            cur = ch
        else:
            cur = test
    if cur:
        lines.append(cur)
    return lines


# 背景渐变图缓存：用 PIL 的 C 级线性渐变 + 着色，避免逐像素 Python 循环（提速关键）
_BG_CACHE = {}


def get_bg(w, h):
    """生成一次渐变背景并缓存（按尺寸）。返回可安全 copy 的 Image。"""
    key = (w, h)
    if key in _BG_CACHE:
        return _BG_CACHE[key].copy()
    # Image.linear_gradient("L") 是 C 实现的 256x256 垂直灰度渐变，colorize 上色极快
    base = Image.linear_gradient("L").resize((w, h))
    bg = ImageOps.colorize(base, black=(18, 24, 38), white=(46, 52, 68))
    _BG_CACHE[key] = bg
    return bg.copy()


def render_frame(text, w, h, idx, total, seed=0):
    """在缓存渐变背景上叠加字幕，返回 PNG 字节（不再逐像素绘制）。"""
    img = get_bg(w, h)
    draw = ImageDraw.Draw(img)

    # 半透明暗条增强字幕可读性
    bar_h = int(h * 0.42)
    bar_y = int((h - bar_h) / 2)
    draw.rectangle([0, bar_y, w, bar_y + bar_h], fill=(0, 0, 0, 0))

    font = load_font(int(h * 0.055))
    max_w = int(w * 0.86)
    lines = wrap_cjk(text, font, max_w)
    line_h = int(font.size * 1.4)
    total_h = line_h * len(lines)
    y = int((h - total_h) / 2)
    # 白字 + 黑色描边，强对比提升清晰度（尤其小屏/压缩后）
    for line in lines:
        lw = font.getlength(line)
        x = (w - lw) / 2
        draw.text((x, y), line, font=font, fill=(255, 255, 255),
                  stroke_width=max(2, int(font.size * 0.02)), stroke_fill=(0, 0, 0))
        y += line_h

    # 进度点
    dot_y = int(h * 0.92)
    gap = 22
    start_x = int(w / 2 - (total - 1) * gap / 2)
    for i in range(total):
        color = (255, 255, 255) if i == idx else (120, 120, 120)
        draw.ellipse([start_x + i * gap - 5, dot_y - 5, start_x + i * gap + 5, dot_y + 5], fill=color)

    import io
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# --------------------------------------------------------------------------- #
# 视频合成（直接调 ffmpeg）
# --------------------------------------------------------------------------- #
def split_sentences(text):
    parts = re.split(r"[。！？!?；;\n]+", text)
    out = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # 超长句子按逗号再切
        if len(p) > 45:
            for sub in re.split(r"[，,、]+", p):
                sub = sub.strip()
                if sub:
                    out.append(sub)
        else:
            out.append(p)
    return out


def build_video(task_id, script, voice, aspect, cfg, duration_sec=0):
    sentences = split_sentences(script)
    if not sentences:
        raise RuntimeError("没有可生成的句子，请检查文案。")

    res = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080)}
    w, h = res.get(aspect, (1080, 1920))

    lang = gtts_lang(voice)
    # 时长控制：用户指定分钟数 → 视频总时长 ≈ duration_sec
    # - 文案自然时长不足：循环文案把时长凑到指定值（配音不被截断）
    # - 文案已够长：均分各句到指定总时长（超出部分截断静音）
    # 关键：配音只对「原始句子」生成一次，循环时复用音频，避免重复网络请求。
    seg_per = None
    reps = 1
    if duration_sec and duration_sec > 0:
        natural = sum(max(estimate_duration(s, lang), 1.5) * 2 for s in sentences)
        if natural < duration_sec - 2:
            reps = max(1, int(math.ceil(duration_sec / max(natural, 1))))
            seg_per = duration_sec / (len(sentences) * reps)
        else:
            seg_per = duration_sec / len(sentences)

    task_dir = os.path.join(MPT_HOME, "tasks", task_id)
    os.makedirs(task_dir, exist_ok=True)

    # 1) 仅为「原始句子」生成素材（图片+配音），并发生成以掩盖网络延迟
    originals = sentences[:]
    n_orig = len(originals)
    assets = [None] * n_orig

    def make_asset(i, sent):
        png_path = os.path.join(task_dir, "frame_%03d.png" % i)
        with open(png_path, "wb") as f:
            f.write(render_frame(sent, w, h, i, n_orig, seed=0))
        audio_path = os.path.join(task_dir, "audio_%03d.mp3" % i)
        dur = tts_to_file(sent, voice, audio_path)
        if dur is None:
            log(task_id, "⚠ 第%d句配音失败（edge-tts 不可用？），该句将以静音兜底" % (i + 1))
        assets[i] = (png_path, audio_path, dur, sent)

    log(task_id, "并行生成 %d 句素材（图片+配音）..." % n_orig)
    done_a = 0
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs_a = {ex.submit(make_asset, i, originals[i]): i for i in range(n_orig)}
        for fut in as_completed(futs_a):
            fut.result()
            done_a += 1
            with TASKS_LOCK:
                TASKS[task_id]["progress"] = int((done_a / n_orig) * 55)

    # 2) 为每个「原始句子」编码一个 clip（去重：循环文案时复用同一 clip，不重复编码）
    def clip_seg_of(asset):
        _, _, dur, sent = asset
        if seg_per:
            return max(1.0, seg_per)
        return estimate_duration(sent, lang) if dur is None else dur * 2

    def encode_asset(i):
        png_path, audio_path, dur, sent = assets[i]
        seg = clip_seg_of(assets[i])
        clip_path = os.path.join(task_dir, "clip_%03d.mp4" % i)
        # -crf 20 保证高清；-r 20 静态画面够流畅；-threads 2 防止压垮手机
        if dur is None:
            run_ffmpeg([
                "-y", "-loop", "1", "-i", png_path,
                "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                "-t", "%.2f" % seg,
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20",
                "-pix_fmt", "yuv420p", "-r", "20", "-threads", "2",
                "-c:a", "aac", "-b:a", "128k", "-shortest", clip_path,
            ], task_id)
        else:
            run_ffmpeg([
                "-y", "-loop", "1", "-i", png_path, "-i", audio_path,
                "-t", "%.2f" % seg,
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20",
                "-pix_fmt", "yuv420p", "-r", "20", "-threads", "2",
                "-c:a", "aac", "-b:a", "128k", "-af", "apad", "-shortest", clip_path,
            ], task_id)
        return clip_path

    log(task_id, "并发编码 %d 个片段（已去重，循环文案只编码原始句）..." % n_orig)
    asset_clips = [None] * n_orig
    done_c = 0
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs_c = {ex.submit(encode_asset, i): i for i in range(n_orig)}
        for fut in as_completed(futs_c):
            i = futs_c[fut]
            asset_clips[i] = fut.result()
            done_c += 1
            with TASKS_LOCK:
                TASKS[task_id]["progress"] = 55 + int((done_c / n_orig) * 30)

    # 3) 按 reps 展开最终序列（去重引用同一 clip 文件，避免重复编码）
    seq_clip_paths = [asset_clips[k % n_orig] for k in range(n_orig * reps)]
    total = len(seq_clip_paths)

    # 拼接（复制流，不重编码，极快）
    log(task_id, "拼接 %d 个片段..." % total)
    with TASKS_LOCK:
        TASKS[task_id]["progress"] = 85
    list_path = os.path.join(task_dir, "concat.txt")
    with open(list_path, "w", encoding="utf-8") as f:
        for c in seq_clip_paths:
            f.write("file '%s'\n" % c.replace("'", "'\\''"))

    final_path = os.path.join(task_dir, "final.mp4")
    run_ffmpeg([
        "-y", "-f", "concat", "-safe", "0", "-i", list_path,
        "-c", "copy", final_path,
    ], task_id)

    # 可选：叠加内置背景音乐（失败不影响成片）
    try:
        music = pick_background_music()
        if music:
            mixed = os.path.join(task_dir, "final_music.mp4")
            run_ffmpeg([
                "-y", "-i", final_path, "-i", music,
                "-filter_complex", "[1:a]volume=0.25[bg];[0:a][bg]amix=inputs=2:duration=first:dropout_transition=0[a]",
                "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-shortest",
                mixed,
            ], task_id)
            if os.path.isfile(mixed) and os.path.getsize(mixed) > 0:
                final_path = mixed
    except Exception as e:
        log(task_id, "背景音乐叠加跳过：%s" % e)

    # 导出到手机 Download/Ai视频（含视频与文案）
    saved = export_to_downloads(task_id, final_path, script)

    with TASKS_LOCK:
        TASKS[task_id]["progress"] = 100
        TASKS[task_id]["state"] = 1
        TASKS[task_id]["videos"] = ["/tasks/%s/%s" % (task_id, os.path.basename(final_path))]
        if saved:
            TASKS[task_id]["download_path"] = saved
    log(task_id, "视频生成完成 ✅ %s" % final_path)


def export_to_downloads(task_id, video_path, script):
    """把成片(mp4)与文案(txt)复制到手机 Download/Ai视频。\n    返回目标 mp4 路径；未配置目录或失败时返回 None。\n    """
    if not DOWNLOAD_DIR:
        log(task_id, "未配置导出目录（Download/Ai视频），视频仅在应用内可播放。")
        return None
    try:
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        base = "MPT视频_%s" % ts
        dst_mp4 = os.path.join(DOWNLOAD_DIR, base + ".mp4")
        shutil.copyfile(video_path, dst_mp4)
        dst_txt = os.path.join(DOWNLOAD_DIR, base + ".txt")
        try:
            with open(dst_txt, "w", encoding="utf-8") as f:
                f.write(script or "")
        except Exception as e:
            log(task_id, "文案导出跳过：%s" % e)
        log(task_id, "已导出到手机：Download/Ai视频/%s.mp4" % base)
        return dst_mp4
    except Exception as e:
        log(task_id, "导出到 Download/Ai视频 失败（请检查存储权限）：%s" % e)
        return None


def pick_background_music():
    songs_dir = os.path.join(ASSET_ROOT, "songs")
    if not os.path.isdir(songs_dir):
        return None
    files = [os.path.join(songs_dir, f) for f in os.listdir(songs_dir)
             if f.lower().endswith(".mp3")]
    if not files:
        return None
    return files[int(time.time()) % len(files)]


# --------------------------------------------------------------------------- #
# 任务调度
# --------------------------------------------------------------------------- #
def create_task(script, voice, aspect, cfg, duration_sec=0):
    task_id = uuid.uuid4().hex[:12]
    with TASKS_LOCK:
        TASKS[task_id] = {
            "state": 0, "progress": 0, "videos": [], "error": "", "logs": [],
        }
    t = threading.Thread(
        target=_run_task, args=(task_id, script, voice, aspect, cfg, duration_sec),
        daemon=True,
    )
    t.start()
    return task_id


def _run_task(task_id, script, voice, aspect, cfg, duration_sec=0):
    try:
        build_video(task_id, script, voice, aspect, cfg, duration_sec)
    except Exception as e:
        tb = traceback.format_exc()
        log(task_id, "任务失败：%s" % e)
        print(tb, flush=True)
        with TASKS_LOCK:
            TASKS[task_id]["state"] = -1
            TASKS[task_id]["error"] = str(e)


# --------------------------------------------------------------------------- #
# HTTP 服务
# --------------------------------------------------------------------------- #
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
  .card h2{font-size:15px;margin:0 0 10px;color:#fff}
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
  button.sm{padding:6px 12px;font-size:12px;font-weight:600}
  button:active{opacity:.85}
  .hint{font-size:11px;color:var(--muted);margin-top:6px}
  .log{background:#0d0f13;border:1px solid var(--border);border-radius:10px;
       padding:10px;font-size:12px;color:var(--muted);white-space:pre-wrap;
       max-height:200px;overflow:auto;margin-top:10px}
  .badge{font-size:11px;padding:2px 8px;border-radius:20px;background:#222;border:1px solid var(--border)}
  .badge.run{color:var(--warn)} .badge.done{color:var(--ok)} .badge.err{color:var(--err)}
  .badge.warn{color:var(--warn)}
  video{width:100%;border-radius:10px;background:#000;margin-top:8px}
  a.dl{display:inline-block;margin-top:4px;color:var(--accent2);text-decoration:none;
       font-size:12px;font-weight:600;word-break:break-all}
  .toggle{float:right;color:var(--muted);font-size:12px;cursor:pointer}
  .mkt-group{margin-top:10px;border-top:1px solid var(--border);padding-top:10px}
  .mkt-title{font-size:13px;color:#fff;font-weight:600;margin-bottom:6px}
  .mkt-item{display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px dashed #222}
  .mname{flex:1;font-size:13px;color:var(--text);word-break:break-all}
</style>
</head>
<body>
<div class="wrap">
  <h1>MoneyPrinterTurbo <span class="badge">Android</span></h1>
  <div class="sub">输入主题 → AI 生成文案 → 配音 + 字幕 → 输出短视频（单 APK，本地运行）</div>

  <div class="card" id="cfgCard">
    <h2>① 配置大模型 <span class="toggle" onclick="toggleCfg()">展开/收起</span></h2>
    <div class="body" style="display:none">
      <label>大模型提供商</label>
      <select id="provider" onchange="onProviderChange()"></select>
      <div class="hint" id="keyHint"></div>
      <label>API Key</label>
      <input id="apiKey" type="text" placeholder="sk-...（点上方链接去官网领取）">
      <label>Base URL（选模型自动填，可改）</label>
      <input id="baseUrl" type="text">
      <label>模型（下拉选择）</label>
      <select id="modelName"></select>
      <label>自定义模型名（本地模型必填，留空则用上方所选）</label>
      <input id="modelCustom" type="text" placeholder="例如 qwen2.5:7b / llama3.1:8b / deepseek-r1:7b">
      <div class="row">
        <button class="sec" onclick="saveConfig()">保存配置</button>
        <button class="ghost" onclick="testModel()">🔌 测试是否可用</button>
      </div>
      <div id="testResult" class="hint"></div>
      <div class="hint">只需一个大模型 Key。选好模型后 Base URL 会自动填好；点「测试」用你的 Key 实测能否调通。</div>
    </div>
  </div>

  <div class="card">
    <h2>② 免费模型市场 <span class="badge done">一键选用</span></h2>
    <div class="sub">绿标 = 免费/免费额度；点「选用」自动填好接口地址与模型名，再去官网领 Key 即可。免费额度用完/过期可能转计费，可用「测试」按钮实测。</div>
    <div id="market"></div>
  </div>

  <div class="card">
    <h2>③ 生成</h2>
    <label>视频主题 / 关键词</label>
    <input id="subject" type="text" placeholder="例如：春天的花海，治愈系短视频">
    <div class="row">
      <input id="wordCount" type="number" min="50" max="2000" step="50" placeholder="字数(留空随机，如300)" style="flex:1;min-width:0">
      <button class="ghost" onclick="genScript()">AI 生成文案</button>
    </div>
    <label>文案（可手动修改）</label>
    <textarea id="script" placeholder="在此填写或自动生成视频文案..."></textarea>
    <div class="row">
      <div>
        <label>配音语言</label>
        <select id="voice">
          <option value="zh-CN-XiaoxiaoNeural">中文·晓晓(女)</option>
          <option value="zh-CN-YunxiNeural">中文·云希(男)</option>
          <option value="zh-CN-YunyangNeural">中文·云扬(男·新闻)</option>
          <option value="en-US-AriaNeural">English·Aria</option>
          <option value="en-US-GuyNeural">English·Guy</option>
          <option value="ja-JP-NanamiNeural">日本語·七海</option>
          <option value="ja-JP-KeitaNeural">日本語・啓太</option>
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
      <div>
        <label>视频时长（分钟）</label>
        <select id="durationMin">
          <option value="0">自动</option>
          <option value="1">1</option>
          <option value="2">2</option>
          <option value="3">3</option>
          <option value="4">4</option>
          <option value="5">5</option>
          <option value="6">6</option>
          <option value="7">7</option>
          <option value="8">8</option>
          <option value="9">9</option>
          <option value="10">10</option>
        </select>
      </div>
    </div>
    <div class="hint" style="margin:6px 0 10px">时长选「自动」按配音自然长度；选 1~10 分钟会把视频拉伸/循环到指定长度（上限 10 分钟）。成片自动存到手机 <b>Download/Ai视频</b>（.mp4）。</div>
    <button onclick="genVideo()">▶ 生成视频</button>
  </div>

  <div class="card">
    <h2>④ 状态 <span id="stateBadge" class="badge"></span></h2>
    <div id="progressBox" style="display:none">
      <div id="progressText" class="hint">进度：0%</div>
    </div>
    <div id="result"></div>
    <div id="log" class="log"></div>
  </div>
</div>

<script>
const API="";
let PROVIDER_MAP={};
function log(m){const e=document.getElementById('log');e.textContent+=m+"\n";e.scrollTop=e.scrollHeight;}
function toggleCfg(){const b=document.querySelector('#cfgCard .body');b.style.display=b.style.display==='none'?'block':'none';}
function setBadge(text,cls){const b=document.getElementById('stateBadge');b.className='badge '+(cls||'');b.textContent=text;}

async function loadProviders(){
  try{
    const r=await fetch(API+"/api/v1/providers");
    const j=await r.json();
    const providers=(j.data&&j.data.providers)||[];
    const sel=document.getElementById('provider');
    sel.innerHTML='';
    for(const p of providers){
      PROVIDER_MAP[p.key]=p;
      const o=document.createElement('option');
      o.value=p.key; o.textContent=p.name;
      sel.appendChild(o);
    }
    onProviderChange();
    renderMarket(providers);
    // 启动即回填上次保存的配置（Key/URL/模型），实现「只填一次」
    loadSavedConfig();
  }catch(e){console.error(e);}
}

// 读取已保存配置并回填到表单；若保存的 provider/model 不在下拉里则临时补一个选项
async function loadSavedConfig(){
  try{
    const r=await fetch(API+"/api/v1/mpt_config");
    const j=await r.json();
    const c=(j.data)||{};
    const prov=document.getElementById('provider');
    if(c.provider){
      if(![...prov.options].some(o=>o.value===c.provider)){
        const o=document.createElement('option');o.value=c.provider;o.textContent=c.provider;prov.appendChild(o);
      }
      prov.value=c.provider;
    }
    onProviderChange(); // 重建模型列表 + 设默认 Base URL
    if(c.base_url) document.getElementById('baseUrl').value=c.base_url;
    if(c.api_key) document.getElementById('apiKey').value=c.api_key;
    if(c.model_name){
      const m=document.getElementById('modelName');
      if(![...m.options].some(o=>o.value===c.model_name)){
        const o=document.createElement('option');o.value=c.model_name;o.textContent=c.model_name;m.appendChild(o);
      }
      m.value=c.model_name;
    }
  }catch(e){console.error(e);}
}

function onProviderChange(){
  const key=document.getElementById('provider').value;
  const p=PROVIDER_MAP[key];
  if(!p) return;
  document.getElementById('baseUrl').value=p.base_url;
  const msel=document.getElementById('modelName');
  msel.innerHTML='';
  for(const m of p.models){
    const o=document.createElement('option');
    o.value=m.id;
    o.textContent=(m.free?'[免费] ':'[计费] ')+m.name;
    msel.appendChild(o);
  }
  const hint=document.getElementById('keyHint');
  if(key==='local'||key==='custom'){
    hint.innerHTML='本地/自建模型通常<b>无需 API Key</b>，可留空。Base URL 改成你电脑或服务器的地址：Ollama 用 <code>http://内网IP:11434/v1</code>，LM Studio 用 <code>http://内网IP:1234/v1</code>；手机与电脑需在同一 WiFi，模型名填你本地已加载的模型（如 qwen2.5:7b）。';
  }else{
    hint.innerHTML='官网领 Key：<a class="dl" href="'+p.key_url+'" target="_blank">'+p.key_url+'</a>（'+p.region+'）';
  }
}

function renderMarket(providers){
  const box=document.getElementById('market');
  let html='';
  for(const p of providers){
    html+='<div class="mkt-group"><div class="mkt-title">'+p.name+' <span class="badge">'+p.region+'</span> <a class="dl" href="'+p.key_url+'" target="_blank">领 Key ↗</a></div>';
    for(const m of p.models){
      const free=m.free?'<span class="badge done">免费</span>':'<span class="badge warn">计费</span>';
      html+='<div class="mkt-item">'+free+'<span class="mname">'+m.name+'</span><button class="ghost sm" onclick="useModel(\''+p.key+'\',\''+m.id+'\')">选用</button></div>';
    }
    html+='</div>';
  }
  box.innerHTML=html;
}

function useModel(pkey,mid){
  const sel=document.getElementById('provider');
  if(sel.querySelector('option[value="'+pkey+'"]')) sel.value=pkey;
  onProviderChange();
  const msel=document.getElementById('modelName');
  if(msel.querySelector('option[value="'+mid+'"]')) msel.value=mid;
  document.querySelector('#cfgCard .body').style.display='block';
  window.scrollTo({top:0,behavior:'smooth'});
  alert('已填入：'+pkey+' / '+mid+'。Base URL 已自动填好，去上方链接领 Key 后点「保存配置」即可。');
}

async function saveConfig(){
  const custom=document.getElementById('modelCustom').value.trim();
  const body={
    provider:document.getElementById('provider').value,
    api_key:document.getElementById('apiKey').value.trim(),
    base_url:document.getElementById('baseUrl').value.trim(),
    model_name:custom||document.getElementById('modelName').value.trim()
  };
  try{
    const r=await fetch(API+"/api/v1/mpt_config",{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const j=await r.json();
    if(j && j.status===200) alert('配置已保存 ✅');
    else alert('保存失败：'+(j.message||'未知错误'));
  }catch(e){alert('请求失败：'+e.message);}
}

async function testModel(){
  const res=document.getElementById('testResult');
  const prov=document.getElementById('provider').value;
  const custom=document.getElementById('modelCustom').value.trim();
  const body={
    provider:prov,
    api_key:document.getElementById('apiKey').value.trim(),
    base_url:document.getElementById('baseUrl').value.trim(),
    model_name:custom||document.getElementById('modelName').value.trim()
  };
  if(!body.api_key && prov!=='local' && prov!=='custom'){res.textContent='请先填写 API Key 再测试。';return;}
  res.textContent='正在测试连接（约几秒）...';
  try{
    const r=await fetch(API+"/api/v1/test",{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const j=await r.json();
    if(j.data && j.data.ok){res.innerHTML='✅ 可用！模型返回：'+(j.data.reply||'');}
    else{res.innerHTML='❌ 不可用：'+((j.data&&j.data.error)||j.message||'未知错误');}
  }catch(e){res.textContent='请求失败：'+e.message;}
}

async function genScript(){
  const subject=document.getElementById('subject').value.trim();
  if(!subject){alert('请先填写主题');return;}
  const wc=document.getElementById('wordCount').value.trim();
  log('正在生成文案...');
  try{
    const r=await fetch(API+"/api/v1/scripts",{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({video_subject:subject, word_count:wc})});
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
        duration_min:document.getElementById('durationMin').value
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

async function pollTask(taskId){
  if(pollTimer) clearInterval(pollTimer);
  pollTimer=setInterval(async ()=>{
    try{
      const r=await fetch(API+"/api/v1/tasks/"+taskId);
      const j=await r.json();
      const d=j.data||{};
      const state=d.state; const prog=d.progress||0;
      if(Array.isArray(d.logs)){ for(const l of d.logs){ if(!document.getElementById('log').textContent.includes(l)) log(l); } }
      document.getElementById('progressText').textContent='进度：'+prog+'%';
      if(state===-1){clearInterval(pollTimer);setBadge('失败','err');log('任务失败：'+(d.error||'未知'));alert('生成失败：'+(d.error||''));}
      else if(state===1){clearInterval(pollTimer);setBadge('完成','done');showResult(d.videos||[], d.download_path);log('视频生成完成 ✅');}
      else{setBadge('进行中','run');}
    }catch(e){/* ignore transient */}
  },2000);
}

function showResult(videos, downloadPath){
  const box=document.getElementById('result');
  if(!videos.length){box.innerHTML='<div class="hint">未返回视频文件。</div>';return;}
  let html='';
  videos.forEach(v=>{
    const url=API+v;
    html+='<video controls src="'+url+'"></video>'+
          '<a class="dl" href="'+url+'" download>⬇ 下载视频</a><br>';
  });
  if(downloadPath){
    html+='<div class="hint" style="margin-top:8px;color:var(--ok)">✅ 已保存到手机：Download/Ai视频/'+downloadPath.split('/').pop()+'<br><span style="color:var(--muted)">（用手机「文件管理」App 即可找到）</span></div>';
  }else{
    html+='<div class="hint" style="margin-top:8px;color:var(--warn)">未导出到 Download（可能未授予存储权限）。可在应用内下载，或到系统设置开启「所有文件访问」后重生成。</div>';
  }
  box.innerHTML=html;
}

window.addEventListener('DOMContentLoaded', loadProviders);
log('界面已加载，请先完成「配置」再生成。');
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # 静默

    def _send_json(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, path):
        if not os.path.isfile(path):
            self.send_error(404)
            return
        ext = os.path.splitext(path)[1].lower()
        ctype = "video/mp4" if ext in (".mp4", ".m4v") else "application/octet-stream"
        size = os.path.getsize(path)
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(size))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except Exception:
                    break

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/" or path == "":
            data = UI_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif path == "/api/v1/providers":
            self._send_json({"status": 200, "data": {"providers": providers_payload()}})
        elif path == "/api/v1/mpt_config":
            # 启动即返回已保存配置，前端据此回填表单，实现「Key 只填一次」
            self._send_json({"status": 200, "data": load_config()})
        elif path.startswith("/api/v1/tasks/"):
            self._handle_task_get(path.split("/")[-1])
        elif path.startswith("/tasks/"):
            rel = path[len("/tasks/"):]
            fpath = os.path.normpath(os.path.join(MPT_HOME, "tasks", rel))
            base = os.path.normpath(os.path.join(MPT_HOME, "tasks"))
            if not fpath.startswith(base):
                self.send_error(403)
                return
            self._send_file(fpath)
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            body = {}

        if path == "/api/v1/mpt_config":
            cfg = load_config()
            cfg["provider"] = (body.get("provider") or cfg["provider"] or "zhipu").lower()
            cfg["api_key"] = (body.get("api_key") or "").strip()
            cfg["base_url"] = (body.get("base_url") or "").strip()
            cfg["model_name"] = (body.get("model_name") or "").strip()
            save_config(cfg)
            self._send_json({"status": 200, "message": "saved"})

        elif path == "/api/v1/scripts":
            cfg = load_config()
            subject = (body.get("video_subject") or "").strip()
            word_count = body.get("word_count")
            if not subject:
                self._send_json({"status": 400, "message": "缺少主题"}, 400)
                return
            if not cfg.get("api_key") and provider_needs_key(cfg.get("provider")):
                self._send_json({"status": 400, "message": "请先在「配置」中填写 API Key"}, 400)
                return
            try:
                script = generate_script(subject, cfg, word_count)
                self._send_json({"status": 200, "data": {"video_script": script}})
            except Exception as e:
                self._send_json({"status": 500, "message": "生成失败：%s" % e})

        elif path == "/api/v1/videos":
            cfg = load_config()
            script = (body.get("video_script") or "").strip()
            subject = (body.get("video_subject") or "").strip()
            if not script:
                if subject and (cfg.get("api_key") or not provider_needs_key(cfg.get("provider"))):
                    try:
                        script = generate_script(subject, cfg)
                    except Exception as e:
                        self._send_json({"status": 500, "message": "文案生成失败：%s" % e})
                        return
                else:
                    self._send_json({"status": 400, "message": "请先填写文案或主题(并配置Key)"}, 400)
                    return
            if not cfg.get("api_key") and provider_needs_key(cfg.get("provider")):
                self._send_json({"status": 400, "message": "请先配置 API Key"}, 400)
                return
            voice = (body.get("voice_name") or "zh-CN-XiaoxiaoNeural")
            aspect = (body.get("video_aspect") or "9:16")
            # 视频时长（分钟）：0=自动，1~10 分钟；限制上限 10 分钟
            duration_min = body.get("duration_min")
            try:
                duration_min = float(duration_min) if duration_min else 0
            except Exception:
                duration_min = 0
            duration_sec = int(max(0, min(10, duration_min)) * 60)
            task_id = create_task(script, voice, aspect, cfg, duration_sec)
            self._send_json({"status": 200, "data": {"task_id": task_id}})

        elif path == "/api/v1/test":
            cfg = {
                "provider": (body.get("provider") or "openai").lower(),
                "api_key": (body.get("api_key") or "").strip(),
                "base_url": (body.get("base_url") or "").strip(),
                "model_name": (body.get("model_name") or "").strip(),
            }
            if not cfg["api_key"] and provider_needs_key(cfg["provider"]):
                self._send_json({"status": 400, "message": "请先填写 API Key"}, 400)
                return
            try:
                text = chat_complete(cfg["provider"], cfg, [
                    {"role": "system", "content": "你是测试助手，只回复两个字。"},
                    {"role": "user", "content": "请回复：可用"},
                ], temperature=0.3, timeout=30)
                self._send_json({"status": 200, "data": {"ok": True, "reply": text[:60]}})
            except Exception as e:
                self._send_json({"status": 200, "data": {"ok": False, "error": str(e)[:300]}})

        elif path.startswith("/api/v1/tasks/"):
            self._handle_task_get(path.split("/")[-1])
        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def _handle_task_get(self, task_id):
        with TASKS_LOCK:
            t = TASKS.get(task_id)
            if t is None:
                self._send_json({"status": 404, "message": "任务不存在"}, 404)
                return
            self._send_json({"status": 200, "data": dict(t)})


def run(host="127.0.0.1", port=8080):
    server = ThreadingHTTPServer((host, port), Handler)
    print("MPT Android light server on http://%s:%d" % (host, port), flush=True)
    server.serve_forever()

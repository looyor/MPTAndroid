# -*- coding: utf-8 -*-
"""
shuohao.py —— 把开源项目 eternityspring/shuohao-skills 的「AI 短剧创作工艺」
落地到 MPT Turbo 的设备端视频生成链路。

原 skill 是给 Claude Code / Codex 这类 Agent 用的（SKILL.md + Node 脚本 + 模型额度），
其核心价值是**提示词方法论**：让 LLM 产出更专业的剧本、场景图提示词与分镜。

本模块不运行 Node 引擎，而是：
  1. 从内置 assets（app/_assets/resource/shuohao/PROMPT.md）加载提炼后的工艺提示词；
  2. 在「生成简案」阶段把它注入规划 LLM，让文案/分镜更专业；
  3. 把简案里的工艺字段转成实际的电影感图提示词、TTS 语气、运镜参数。

原项目许可 Apache-2.0，署名见 shuohao/NOTICE.md。
"""

import os

# 由 mobile_server 在启动时调用：传入 ASSET_ROOT（.../app/_assets/resource）
_ASSET_ROOT = None
_CRAFT_TEXT = None  # 缓存的工艺提示词


def init(asset_root):
    """mobile_server 启动时把 ASSET_ROOT 注入进来。"""
    global _ASSET_ROOT
    _ASSET_ROOT = asset_root


def craft_text():
    """读取内置的 shuohao 工艺提示词（PROMPT.md）；读不到返回空串（优雅降级）。"""
    global _CRAFT_TEXT
    if _CRAFT_TEXT is not None:
        return _CRAFT_TEXT
    _CRAFT_TEXT = ""
    if not _ASSET_ROOT:
        return _CRAFT_TEXT
    p = os.path.join(_ASSET_ROOT, "shuohao", "PROMPT.md")
    try:
        if os.path.isfile(p):
            with open(p, "r", encoding="utf-8") as f:
                _CRAFT_TEXT = f.read().strip()
    except Exception as e:
        print("shuohao: 读取工艺提示词失败，降级为普通提示词：%s" % e, flush=True)
    return _CRAFT_TEXT


# --------------------------------------------------------------------------- #
# 1) 规划提示词注入
# --------------------------------------------------------------------------- #
def enrich_plan_prompt(base_sys_prompt):
    """把 shuohao 工艺附到基础规划提示词之后。若工艺文件缺失则原样返回。"""
    craft = craft_text()
    if not craft:
        return base_sys_prompt
    return base_sys_prompt + "\n\n---\n" + craft + "\n---\n"


def shuohao_enabled(cfg):
    return (cfg.get("shuohao") or "on") != "off"


# --------------------------------------------------------------------------- #
# 2) 电影感场景图提示词（美术圣经工艺）
# --------------------------------------------------------------------------- #
# 表面处理两档（按空间保养水平二选一，不是两种画风，是两种事实）
_SURFACE_WEATHERED = ("weathered, lived-in materials: chipped paint, water stains, "
                      "patina on metal, worn wood grain, dust in corners and light shafts")
_SURFACE_KEPT = ("well-kept, actively maintained materials: sound lacquer with even sheen, "
                 "swept stone and timber, polished metal fittings, no peeling paint")

# 氛围 → 光照状态（具体，不写「白天/夜晚」全家桶）
_MOOD_LIGHTING = {
    "tense": "harsh overhead light with deep shadows",
    "urgent": "cold fluorescent light, hard shadows",
    "gloomy": "overcast diffuse light, muted grey tones",
    "sad": "dim warm lamplight, soft shadows",
    "warm": "golden hour warm sunlight through window",
    "hopeful": "soft morning light, gentle haze",
    "calm": "even soft daylight, balanced tones",
    "serious": "neutral institutional lighting",
    "romantic": "warm candlelight, shallow depth of field",
    "mysterious": "low-key lighting, single practical lamp",
    "cold": "blue dawn light, crisp edges",
}

# 氛围 → 表面处理档（clean/bright 用 B，其余默认 A 更有电影质感）
_WELL_KEPT_MOODS = {"warm", "hopeful", "clean", "modern", "calm", "romantic"}

# 统一负向（画质类——本 App 不另行合成角色，画面需要有人/主体，故不再禁人）
_NEGATIVE = ("文字水印, 低质量, 模糊, 变形, 多余手指, 畸变透视, 漂浮物体, "
             "卡通, 插画, 油画, 3d 渲染, 过饱和色彩, 拼接痕迹")


def _lighting_for(mood):
    return _MOOD_LIGHTING.get((mood or "").lower(), "natural cinematic lighting")


def visual_prompt_for(seg, style_anchor=""):
    """由简案的一句 segment 生成电影感、可含人物/主体的中文场景图提示词。

    优先用模型给的 visual_prompt；缺失则用 keyword/action/text 兜底。
    统一追加：表面处理 + 光照 + 一致性锚点 + 画质负向。

    说明：原 shuohao 工艺要求「空景禁人」，那是给「先出空背景、再单独合成角色」
    的工作流用的。本 App 不另行合成角色，每一句直接生成一张含主体/人物的实拍风
    画面，所以这里**允许并鼓励画面中出现人物与主体**，只保留画质类负向。
    """
    seg = seg or {}
    base = (seg.get("visual_prompt") or "").strip()
    if not base:
        base = (seg.get("keyword") or seg.get("action") or seg.get("text") or "scenery").strip()
    mood = (seg.get("mood") or "").strip()
    surface = _SURFACE_KEPT if mood.lower() in _WELL_KEPT_MOODS else _SURFACE_WEATHERED
    lighting = _lighting_for(mood)
    anchor = (style_anchor or "").strip()

    # 中文为主（魔搭 Z-Image-Turbo 中文原生理解最佳），并附英文画质词兼顾 Flux
    parts = [base, "电影感镜头, 真实摄影, 4k, 浅景深, 自然光", surface, lighting]
    if anchor:
        parts.append(anchor)
    parts.append("人物与场景协调构图")
    parts.append(_NEGATIVE)
    return ", ".join(parts)


# --------------------------------------------------------------------------- #
# 3) delivery（语气）→ edge-tts 朗读风格
# --------------------------------------------------------------------------- #
# 中文 delivery 标签 → 微软 SSML express-as style（不支持的会被 tts_to_file 自动回退）
_DELIVERY_STYLE = {
    "平静": "calm", "讲述": "narration-relaxed", "旁白": "narration-relaxed",
    "紧张": "serious", "严肃": "serious", "urgent": "serious", "急切": "serious",
    "激昂": "angry", "愤怒": "angry", "生气": "angry",
    "温柔": "gentle", "轻柔": "gentle", "亲切": "affectionate",
    "忧伤": "sad", "忧郁": "sad", "难过": "sad", "失望": "sad",
    "开心": "cheerful", "高兴": "cheerful", "兴奋": "cheerful", "欢快": "cheerful",
    "害怕": "fearful", "恐惧": "fearful",
    "神秘": "whisper", "低语": "whisper",
}


def style_for_delivery(delivery, lang="zh-CN"):
    """把中文语气标签映射成 edge-tts 风格；非中文或未知返回空串（不强制风格）。"""
    d = (delivery or "").strip()
    if not d:
        return ""
    if lang.startswith("zh"):
        return _DELIVERY_STYLE.get(d, "")
    return ""


# --------------------------------------------------------------------------- #
# 4) 景别（shot）→ Ken Burns 运镜参数
# --------------------------------------------------------------------------- #
# 返回 (zoom 倍率, 横向漂移幅度px, 纵向漂移幅度px, 相位偏移) —— 喂给 compose_offline 的 vf
def shot_motion(shot, idx=0):
    shot = (shot or "").strip().lower()
    # 相位随序号错位，避免相邻片段运动完全同步
    phase = (idx % 4) * 0.5
    if shot == "wide":
        # 大景/定场：更大漂移、稍慢，营造环境呼吸感
        return (1.16, 26, 18, phase)
    if shot == "close":
        # 近景/特写：几乎不动，稳定焦点
        return (1.08, 8, 6, phase)
    # 中景：默认
    return (1.12, 18, 14, phase)


if __name__ == "__main__":
    print("craft_text bytes:", len(craft_text()))
    print(visual_prompt_for({"keyword": "rainy city street", "mood": "gloomy"}, "a quiet late-night street"))
    print(style_for_delivery("紧张"))
    print(shot_motion("wide", 1))

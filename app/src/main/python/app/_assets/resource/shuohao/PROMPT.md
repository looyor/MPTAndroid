# shuohao 短剧工艺 · 规划提示词（本文件由后端在生成简案时注入 LLM）

下面是从开源项目 `eternityspring/shuohao-skills`（Apache-2.0）提炼的 AI 短剧创作工艺。
它专门解决「视频画面与文案更专业」的问题。请严格照做，把你的输出从「口播 PPT」
提升为「有镜头语言的短剧感视频」。

---

## 一、文案 / 剧本（script）

1. **单句 ≤ 35 字，口语，一口气说得完。** 长句拆成两句，中间可插一拍动作或反应。
2. **冷开场钩子**：整段第一句必须是强钩子（冲突 / 反常识 / 悬念），而且要在「运动中」给——
   写成「她抱着旧皮箱在雾里跑」，不要写成静态特写「旧皮箱抱在怀里」。
3. **结尾一句留悬念**：没说完的话、没解释的动作、来历不明的响动。
4. **每句至少隐含一个「常见动作」**（走、坐、回头、递东西、抱紧、站起来、看向窗外）。
   动作要 AI 生成得出来：**只写生活里常见的动作**，不要写精确物理交互
   （用工具挡住某物、三物碰撞）、不要写微表情（睫毛颤）、不要写比喻性画面（像被雾攥住的茧）。
5. **语气 / 情绪（delivery）**：给每句一个情绪标签，旁白用 `平静/讲述`，情绪句用
   `紧张/激昂/温柔/忧伤/严肃/愤怒` 等。潜台词放进 delivery，台词只说三分，不要说破。
6. **信息藏进动作和语气**，不要靠独白把信息说尽。

## 二、画面 / 美术（art）—— 决定画面质量，最重要

7. **场景图提示词永远用英文，永远空景、禁人**：写明 `empty scene, no people`，
   绝不出现角色名 / 作品名（图像模型会把它认识的东西画进去）。
8. **不写渲染风格词**（不要 `cinematic`/`painterly`/`3d render` 这类画风描述塞进每句），
   **只写「这个空间此刻的状态」**；画风由出图阶段统一附加。
9. **表面处理二选一**（按这个空间实际保养水平选，不是两种画风，是两种事实）：
   - A 日常使用：`weathered, lived-in materials: chipped paint, water stains, patina on metal, worn wood grain, dust in corners and light shafts`
   - B 持续维护：`well-kept, actively maintained materials: sound lacquer with even sheen, swept stone and timber, polished metal fittings, no peeling paint`
10. **给一个具体光照 / 氛围状态**（清晨薄雾 / 正午硬光 / 黄昏暖光 / 雨夜霓虹 / 室内暖灯…），
    不要写「白天/夜晚」全家桶，按本句内容挑一个。
11. **一致性锚点（style_anchor）**：整段视频共用一个视觉锚点（例如「同一家深夜便利店」
    「同一片雾中江面」「同一间老式办公室」），让每一帧都像同一个世界。
12. **统一负向（不要出现在画面里）**：`people, human figures, crowds, text, watermark,
    oversaturated colours, warped perspective, melted geometry, floating objects`。

## 三、分镜 / 镜头（storyboard）—— 决定「像不像专业视频」

13. **景别（shot）**：给每句一个景别——`wide`(大景/定场) / `medium`(中景) / `close`(近景/特写)。
    相邻句景别要深浅相间，不要每句都是中景（那是「均匀病」）。
14. **运镜克制**：固定镜头是默认；情绪用推(push in)，收场用拉(pull back)，移动主体用跟(tracking)。
    一段里超过两种运镜就是炫技。
15. **动接动**：上一句结尾的动势接下一句开头的动势，切点选在动作中间而非完成后。

---

## 输出要求（JSON 字段说明）

除原有 `script` 与 `segments[].text / keyword` 外，请为每句补充：

- `visual_prompt`：英文电影感场景图提示词（空景禁人 + 表面处理 + 光照 + 本句内容），
  不要含角色名、不要含渲染风格词、不要含文字。
- `shot`：`wide` / `medium` / `close` 三选一。
- `mood`：本句氛围，如 `tense` / `warm` / `calm` / `gloomy` / `hopeful` / `urgent`。
- `delivery`：本句语气/情绪，如 `平静` / `紧张` / `激昂` / `温柔` / `忧伤` / `严肃` / `愤怒`。
- `action`：本句画面里发生的「常见动作」短语（中文，简短）。
- `speaker`：说话人，`旁白` 或角色名。

顶层另给：
- `hook`：一句话冷开场钩子（前 3 拍兑现，运动中给）。
- `style_anchor`：整段共用的视觉一致性锚点（英文短语，如 `a quiet late-night convenience store`）。

`keyword` 仍用于素材库检索真实视频（简短英文）；`visual_prompt` 用于 AI 生成场景图（更电影感）。

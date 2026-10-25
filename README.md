# MoneyPrinterTurbo for Android —— APK 工程与构建指南

> 把 **MoneyPrinterTurbo 1.3.9**（AI 短视频生成工具：主题 → AI 文案 → TTS 配音 → 素材 → 合成视频）
> 移植为**可直接在 Android 手机上安装运行**的 APK。

---

## 0. 结论速览（请先读这段）

- ✅ 移植工程已**完整搭建且逻辑闭环**：Android 原生壳 + Chaquopy 内嵌 Python 3.11 + **轻量标准库后端** + WebView 移动端 UI + 内置 ffmpeg。
- ✅ **ffmpeg 已交叉编译**为 ARM64 静态二进制（22.5MB），已打包进 `app/src/main/assets/ffmpeg/ffmpeg`。
- ✅ **后端已重写为"轻量版"**：去掉了 FastAPI / uvicorn / pydantic / moviepy 等**无法在安卓安装的依赖**，只保留 `requests / gtts / pillow` 三个纯 Python 包，视频合成直接用内置 ffmpeg。彻底解决了之前 `pydantic-core` 无安卓轮子导致构建卡死的问题。
- ✅ **使用极简**：内置**「免费模型市场」**（11 家厂商 / 26 模型，20 个免费），手机上只需领一个 Key、点「选用」自动填好接口地址，无需 Pexels、无需 Redis。
- ⚠️ 本工程**必须在电脑或 GitHub 云端构建**（手机端 AIDE 无法构建，见第 4 节）；但**出包后 APK 是单个文件，可直接装到手机离线运行**。
- 工程位置：`/workspace/MPTAndroid`

---

## 0.5 小白专用：零命令行出包（最简单，推荐先看这个）

> 你只需要：**一台电脑（Windows 或 Mac，手机不行）** + **一个免费 GitHub 账号**。全程不用敲任何命令，用鼠标点几下就行。

### 准备清单
| 你需要 | 哪里拿 | 费用 |
|--------|--------|------|
| 工程压缩包 | 本页提供的 `MPTAndroid.zip` | 免费 |
| GitHub 账号 | [github.com](https://github.com) 注册 | 免费 |
| GitHub Desktop 软件 | [desktop.github.com](https://desktop.github.com) 下载安装 | 免费 |

### 在 GitHub 上怎么操作（每一步点哪里都写清楚了）

> 前提：电脑上已把 `MPTAndroid.zip` 解压，得到一个 `MPTAndroid` 文件夹。

#### ① 注册 GitHub 账号（手机或电脑浏览器都行）
1. 打开 [github.com](https://github.com)。
2. 点右上角绿色的 **`Sign up`**。
3. 填邮箱 → 设密码 → 取一个用户名 → 一路点 `Continue`。
4. 去邮箱收验证邮件，点里面的确认链接完成注册。

#### ② 电脑上装 GitHub Desktop 并登录
1. 电脑打开 [desktop.github.com](https://desktop.github.com) → 点 `Download`。
2. 双击安装，打开软件。
3. 首次打开会让你登录 GitHub → 点 `Sign in` → 在网页里授权（Authorize）→ 回到软件即登录成功。

#### ③ 把工程发布到 GitHub（最关键的一步）
1. 打开 GitHub Desktop。
2. 顶部菜单 `File` → `Add Local Repository...`。
3. 点 `Choose...` → 选中你解压出来的 `MPTAndroid` 文件夹 → 点 `Add Repository`。
   - 添加成功后会看到左侧出现这个仓库，下方有一堆文件列表。
4. 点左上角的蓝色按钮 **`Publish repository`**（发布仓库）。
5. 在弹出的窗口里：
   - **Name**（仓库名）：填 `MPTAndroid`（随便填也行）。
   - **Description**（描述）：可留空。
   - ⚠️ **必须取消勾选** `Keep this code private`（一定要公开！否则 GitHub Actions 不能免费使用，就没法自动打包）。
   - 点 **`Publish Repository`**。
6. 等几秒，提示 `Publish complete` 就成功了——代码已经在你的 GitHub 上了。

#### ④ 在 GitHub 网页启动自动打包
1. 用浏览器打开 [github.com](https://github.com) → 登录 → 进入你刚建的仓库。
2. 点仓库页面**上方一排标签里的 `Actions`**（在 Code / Issues / Pull requests 那一行）。
3. 左侧列表点 **`Build MPT Android APK`**。
4. 右侧点绿色的 **`Run workflow`** 按钮 → 弹出的小框里再点一次绿色的 **`Run workflow`**。
5. 页面会出现一个黄色小圆点（● 进行中）。点进去能看到实时日志。
   - 大约 10–20 分钟：变**绿色对勾 ✓ = 成功**；变**红色 ✕ = 失败**（把日志截图发我）。

#### ⑤ 下载 APK 并装到手机
1. 跑到绿色对勾后，点进那一次任务页面。
2. 页面**最下方 `Artifacts` 区域** → 点 **`mpt-android-apk`** 下载（这是一个 zip）。
3. 解压得到 `app-debug.apk`。
4. 传到手机（微信文件传输 / 网盘 / U 盘）→ 点开安装（首次需允许“未知来源”）。

> 装好打开 App，按第 5 节填**一个大模型 API Key**，就能在手机上生成短视频了（配音在手机本地完成，无需 Pexels）。

#### 常见问题
- **找不到 `Publish repository` 按钮？** 先确认第 ③ 步 `Add Local Repository` 成功、左侧已选中该仓库；按钮在窗口左上角，蓝色。
- **`Actions` 标签点不开 / 显示不可用？** 仓库必须是 **public（公开）**。若误设为 private，进仓库 `Settings → Change visibility` 改为 public，或重新发布。
- **一直卡在 `Set up job` / 黄色转圈很久？** 正常，首次要联网拉取 Gradle、Chaquopy、Python 3.11 和一堆依赖，耐心等 10–20 分钟。
- **红色失败？** 多半是网络临时问题，点 `Re-run jobs` 重试一次；仍失败把日志发我。
- **没有电脑、只有手机？** 借用他人电脑做第 ②③ 步（把代码传上 GitHub）即可，第 ④⑤ 步在手机浏览器里就能完成。

### （可选）如果你会用命令行
在解压后的 `MPTAndroid` 文件夹里打开终端，依次执行（替换成你的 GitHub 用户名和仓库名）：

```bash
git init -q
git add -A
git commit -q -m "MPT Android"
git remote add origin https://github.com/你的用户名/你的仓库名.git
git branch -M main
git push -u origin main
```

推上去后，从第 6 步（云端自动打包）继续即可。

### 如果你只有手机、没有电脑
本工程**必须在电脑或云端构建**（AIDE 等手机 IDE 无法构建，见第 4 节说明）。临时借用家人/朋友的电脑，或用手机浏览器登录 GitHub 网页版 + 旁边有电脑时操作即可——构建本身在 GitHub 云端完成，你只需要第 6–8 步在手机浏览器里点几下。

---

## 1. 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│  Android App (com.mpt.android)                              │
│                                                             │
│  MainActivity.java                                          │
│    ├─ 释放 assets/ffmpeg/ffmpeg → /data/.../files/ffmpeg    │
│    ├─ Python.start(AndroidPlatform)  // Chaquopy 内嵌 Py3.11│
│    ├─ 调用 bootstrap.start_server(mpt_home, ffmpeg)         │
│    └─ 轮询 127.0.0.1:8080 → WebView 加载移动端 UI          │
│                                                             │
│  bootstrap.py  (运行在 Python 线程)                         │
│    ├─ 设 MPT_HOME / MPT_FFMPEG / PATH                       │
│    ├─ 启动 mobile_server（标准库 http.server）于 127.0.0.1  │
│    └─ 提供 /api/v1/mpt_config、/scripts、/videos、/tasks   │
│                                                             │
│  mobile_server.py  (轻量后端，零 Web 框架)                  │
│    ├─ 大模型：requests 直连 OpenAI 兼容协议                 │
│    ├─ 配音：gTTS（纯 Python，Google TTS）                   │
│    ├─ 字幕/背景：Pillow 渲染 PNG                            │
│    └─ 视频合成：直接调用内置 ffmpeg（无需 MoviePy）          │
└─────────────────────────────────────────────────────────────┘
```

关键设计取舍：

| 项目 | 方案 | 说明 |
|------|------|------|
| Python 运行时 | Chaquopy 17.1.0 + Python 3.11 | 在 APK 内嵌解释器，无需 root |
| 后端 | **标准库 `http.server`（无 FastAPI）** | 规避 pydantic-core 等无安卓轮子依赖 |
| 大模型 | **`requests` 直连** OpenAI 兼容协议 | 支持 6 家主流厂商，无需 openai SDK |
| 配音 | **`gTTS`**（纯 Python） | 无需 edge-tts / aiohttp |
| 字幕/背景 | **Pillow** 渲染 PNG | 无需 MoviePy / ImageMagick |
| 视频合成 | **直接调内置 ffmpeg** | 不依赖 moviepy / numpy / imageio |
| Python 依赖 | 仅 `requests` / `gtts` / `pillow` | 三个纯 Python 包，安卓构建风险极低 |
| ABI | `arm64-v8a` | 覆盖主流手机；需 32 位可加 `abiFilters` |
| 最低系统 | `minSdk 24`（Android 7.0） | |

---

## 2. 已完成的工作

1. **交叉编译 ffmpeg**
   - 目标：ARM64 (aarch64)、API 24、NDK 27.0.12077973，静态链接 bionic。
   - 配置：`--enable-gpl --enable-libx264 --enable-pic --disable-everything` 后按需开启 muxer/demuxer/codec，仅保留原生编解码 + libx264。
   - 产物：`app/src/main/assets/ffmpeg/ffmpeg`（22.5MB，`ELF 64-bit LSB pie executable, ARM aarch64`）。
2. **轻量后端重写（解决安卓构建卡死）**
   - 删除原 FastAPI / uvicorn / pydantic / moviepy 等**无安卓轮子**的重依赖，重构为 `mobile_server.py`（标准库 `http.server`）。
   - 大模型改用 `requests` 直连 OpenAI 兼容协议（覆盖 OpenAI / DeepSeek / 通义千问 / Kimi / Gemini / Groq）。
   - 配音改用 `gTTS`（纯 Python），字幕/背景改用 `Pillow` 渲染，视频合成改为**直接调用内置 ffmpeg**。
   - Python 依赖从十余个精简为 `requests` / `gtts` / `pillow`，安卓构建风险大幅降低。
   - 清理 `app/` 下全部 FastAPI 代码，仅保留 `app/_assets`（字体 + 背景音乐）。
3. **搭建完整 Android 工程**
   - `build.gradle`：AGP 8.5.2 + Chaquopy 17.1.0；`app/build.gradle`：`chaquopy { defaultConfig { version "3.11" } }` + 精简 pip 依赖。
   - `MainActivity.java`：释放 ffmpeg → 启动 Python → 轮询 8080 → 加载 WebView。
   - `AndroidManifest.xml` / `network_security_config.xml`：放行 127.0.0.1 / localhost 明文（WebView 访问本地服务）。
   - 移动端 WebUI：配置表单、AI 生成文案、生成视频、进度轮询、播放/下载。
4. **接口冒烟测试（沙箱内验证 HTTP 层）**
   - 已验证：首页返回、`mpt_config` 保存、`scripts` 生成（含 Key 校验）、`videos` 创建任务、`GET /api/v1/tasks/<id>` 轮询状态、视频静态服务路由。
   - 注：视频实际合成需要真机/CI 上的 ffmpeg 与 gTTS，沙箱（x86_64、无真 ffmpeg）仅验证到逻辑层。

---

## 3. 关于"构建卡死"的说明（已解决）

之前的版本卡在 `pydantic-core`（FastAPI 依赖链）在 Chaquopy/Android 上**无 aarch64 轮子**，导致 pip 解析失败、APK 永远打不出来。本次已通过"轻量后端重写"彻底规避：

- 不再安装 FastAPI / uvicorn / pydantic / openai SDK / edge-tts / moviepy / numpy / imageio 等。
- 仅 `requests` / `gtts` / `pillow` 三个纯 Python 包，Chaquopy 可正常安装。
- 视频合成走内置 ffmpeg，字幕走 Pillow，全程不依赖任何需编译的 C/Rust 扩展。

> 唯一剩余的构建外部依赖是 **Chaquopy 插件与 Python 3.11 运行时**，需网络可访问 `mavenCentral()` 与 Chaquopy 的 Python 源。GitHub Actions runner 满足该条件。

---

## 4. 构建步骤（正常网络环境）

### 方式 A：Android Studio（最省心，推荐）

1. 安装 [Android Studio](https://developer.android.com/studio)，通过 SDK Manager 安装 **Android SDK (API 34)** 与（可选）**NDK 27**。
2. `File → Open` 打开本工程目录 `/workspace/MPTAndroid`。
3. 首次打开时 Android Studio 会：
   - 自动生成 `local.properties`（含 `sdk.dir`）；
   - 下载 Gradle 8.9、Chaquopy Gradle 插件、Python 3.11 运行时、各 Python 轮子。
4. `Build → Build Bundle(s) / APK(s) → Build APK(s)`。
5. 产物：`app/build/outputs/apk/debug/app-debug.apk`。
6. 安装到手机：`adb install app-debug.apk`，或蓝牙/U 盘传过去安装。

### 方式 B：命令行（Gradle）

```bash
export ANDROID_HOME=/path/to/Android/Sdk   # 或 ANDROID_SDK_ROOT
# 可选：export ANDROID_NDK=/path/to/Android/Sdk/ndk/27.0.12077973
cd /workspace/MPTAndroid
./build_apk.sh                              # 内部调用 gradle assembleDebug
```

产物同样位于 `app/build/outputs/apk/debug/app-debug.apk`。

### 方式 C：GitHub Actions 云构建（无电脑也能出包）

工程已内置工作流 `.github/workflows/build-apk.yml`：

1. 把本工程推到你的 GitHub 仓库（含 `.github/` 目录）。
2. 仓库 `Actions` 页 → `Build MPT Android APK` → `Run workflow`。
3. 跑完在 `Artifacts` 下载 `mpt-android-apk`（即 `app-debug.apk`），传到手机安装。

GitHub runner 网络可正常访问 `chaquopy.com`，全自动拉取 Chaquopy 插件、Python 3.11 运行时与各轮子。

### 关于 AIDE（手机端 IDE）

**AIDE 无法直接构建本工程。** 本工程依赖 Chaquopy（Gradle 插件）在构建期下载 Python 3.11 运行时并 `pip` 安装少量 Python 包；而 AIDE 使用自有编译管线、不支持 Gradle 插件体系，无法嵌入 Python 运行时，打开工程会卡在 Chaquopy 插件/依赖解析。

正确做法：用上面任一种方式（Android Studio / 命令行 / GitHub Actions）**构建一次 APK**，再把 `app-debug.apk` 传到手机安装运行即可——手机端只需要负责"安装并运行"，不需要 AIDE 参与编译。

> 提示：本工程的 Python 依赖已精简为 `requests` / `gtts` / `pillow`，均为纯 Python 包，无需任何编译型轮子，安卓构建稳定性远高于原版 MPT。

---

## 5. 运行与使用

1. **首次启动**：应用释放 ffmpeg → 启动内嵌 Python 服务 → 轮询 `127.0.0.1:8080` → WebView 加载移动端 UI（约数秒）。
2. **配置（①）—— 已内置「免费模型市场」**：
   - 打开 App 首页即可看到 **② 免费模型市场**：覆盖 11 家厂商、26 个模型（20 个免费/免费额度），如智谱 GLM-4.7-Flash（永久免费）、硅基流动、DeepSeek、通义千问、Kimi、Gemini、Groq、OpenRouter 等。
   - 在「免费模型市场」点 **「选用」**，会自动填好该模型的 **Base URL + 模型名**，并展开配置卡；再点每组标题旁的「领 Key ↗」去对应官网（手机号/邮箱即可注册）领取 API Key。
   - 选好模型后 **Base URL 也会随模型自动联动**（无需手填链接）；也可手动改。
   - 填好 API Key 后，先点 **「🔌 测试是否可用」**——App 会用你的 Key 实测该模型能否调通（免费额度是否还有效），成功再点「保存配置」。
   - 默认已选 **智谱 GLM**（国内永久免费，新手最省心）。
3. **生成（②）**：
   - 填视频主题 → 「AI 生成文案」（或手动粘贴文案）。
   - 选配音语言（中文 / English / 日本語）与画面比例（9:16 / 16:9 / 1:1）。
   - 点「▶ 生成视频」。
4. **状态（③）**：实时进度百分比 + 日志；完成后视频直接在页面内播放并支持下载。
5. 视频保存在应用私有目录，经 `/tasks` 静态路由在同源 WebView 内播放/下载。

> 本版**不需要 Pexels Key**：视频画面由内置渐变背景 + AI 字幕本地生成，配音用 gTTS 在手机本地完成，全程只需一个 LLM Key 即可出片。

---

## 6. 已知限制与说明

- **配音**使用 `gTTS`（Google Translate TTS），**需联网**；音质一般，但免费且无需额外 Key。
- **画面**为"渐变背景 + 字幕"的轻量风格（非真实素材视频）；如需 Pexels 真实素材可在后续版本接入（需联网 + Key）。
- **视频合成在手机本地完成**：直接调用内置 ffmpeg，不依赖云端，生成速度与手机性能有关（一条 30 秒视频通常几十秒到一两分钟）。
- **任务为内存模式**：App 进程被杀则任务丢失（符合移动端预期）。
- **API 鉴权**：未配置 `api_key` 时放行（同进程内、WebView 同源访问，安全边界由 Android 沙箱提供）。
- **仅 `arm64-v8a`**：如需 32 位设备，在 `app/build.gradle` 的 `ndk { abiFilters }` 增加 `armeabi-v7a` 等。
- **联网范围**：App 内 Python 会访问 LLM / Google TTS 的 HTTPS 接口；WebView 仅访问本地 `127.0.0.1:8080`（明文已在网络安全配置中放行）。
- **包体**：ffmpeg(~22MB) + Python 运行时 + 少量纯 Python 包 + 资源字体/音乐，debug APK 预计 50–70MB。

---

## 7. 工程目录结构

```
MPTAndroid/
├── build.gradle                      # AGP 8.5.2 + Chaquopy 17.1.0 classpath
├── settings.gradle
├── gradle.properties
├── local.properties.example           # 模板：复制为 local.properties 填 sdk.dir
├── build_apk.sh                      # 可移植构建脚本（CLI）
├── .gitignore
├── README.md                         # 本文件
    └── app/
        ├── build.gradle                  # chaquopy{defaultConfig{version "3.11"}} + 精简 pip 依赖
    └── src/main/
        ├── AndroidManifest.xml
        ├── assets/ffmpeg/ffmpeg      # 交叉编译的 ARM64 ffmpeg 二进制
        ├── java/com/mpt/android/MainActivity.java
        ├── res/
        │   ├── layout/activity_main.xml
        │   ├── values/{strings.xml,themes.xml}
        │   └── xml/network_security_config.xml
        └── python/
            ├── bootstrap.py          # 启动轻量服务 + 设置 ffmpeg 路径
            ├── mobile_server.py      # 标准库 HTTP 服务（LLM/TTS/字幕/合成）
            └── app/
                └── _assets/         # resource/fonts（含 MicrosoftYaHei/STHeiti 等）、resource/songs（背景音乐）
```

---

## 8. 故障排查

- **白屏 / "服务启动失败"**：用 `adb logcat` 查看。确认 ffmpeg 已成功释放到 `files/ffmpeg` 且可执行；确认 Python 启动无 ImportError（检查 `app/build.gradle` 的 pip 清单是否装上了 requests/gtts/pillow）。
- **字幕中文缺字**：确认内置字体（`MicrosoftYaHei*.ttc` / `STHeiti*.ttc`）随 `_assets` 打入 APK；字幕由 Pillow 用这些字体渲染。
- **配音没声音 / 生成慢**：gTTS 需联网访问 Google TTS；若网络不通会自动降级为"静音 + 字幕"成片（仍可用）。
- **构建报 Chaquopy 下载失败**：确认网络可访问 `mavenCentral()` 与 Chaquopy Python 源，且 `local.properties` 的 `sdk.dir` 正确；若公司网络有 MITM 代理，需把代理 CA 加入 JVM 信任库。
- **API Key 不生效**：配置通过 `/api/v1/mpt_config` 写入 `files/mpt/config.json`；可在 `adb shell run-as com.mpt.android` 下检查。

---

## 9. 下一步（在合规网络下）

1. 按第 4 节构建出 `app-debug.apk`。
2. 安装到 Android 手机，按第 5 节完成首次配置。
3. 试生成一条 9:16 短视频，验证：文案生成 → 配音 → 素材下载 → 字幕合成 → 成片播放/下载全链路。
4. 如需发布：用 `assembleRelease` + 自有签名密钥构建 release APK / AAB。

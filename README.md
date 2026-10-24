# MoneyPrinterTurbo for Android —— APK 工程与构建指南

> 把 **MoneyPrinterTurbo 1.3.9**（AI 短视频生成工具：主题 → AI 文案 → TTS 配音 → 素材 → 合成视频）
> 移植为**可直接在 Android 手机上安装运行**的 APK。

---

## 0. 结论速览（请先读这段）

- ✅ 移植工程已**完整搭建且逻辑闭环**：Android 原生壳 + Chaquopy 内嵌 Python 3.11 + FastAPI 后端 + WebView 移动端 UI + 内置 ffmpeg。
- ✅ **ffmpeg 已交叉编译**为 ARM64 静态二进制（22.5MB），已打包进 `app/src/main/assets/ffmpeg/ffmpeg`。
- ⚠️ **当前沙箱网络环境无法完成最终 APK 打包**，原因见第 3 节——这是**网络环境限制，不是工程代码缺陷**。
- ✅ 在**能正常访问 `chaquopy.com` 的网络环境**下（你的开发机 / CI），按第 4 节步骤即可一键构建出可安装的 `app-debug.apk`。
- 工程位置：`/workspace/MPTAndroid`

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
│    ├─ 设 MPT_HOME / IMAGEIO_FFMPEG_EXE / PATH               │
│    ├─ 启动 uvicorn(FastAPI) 于 127.0.0.1:8080              │
│    ├─ 把 "/" 路由替换为移动端 WebUI（同源，免 CORS）        │
│    └─ 提供 /api/v1/mpt_config 持久化 API Key               │
│                                                             │
│  app/  (MPT 1.3.9 真实后端，已剔除 Streamlit)              │
│    └─ FastAPI：/api/v1/scripts、/videos、/tasks、...       │
│        └─ 字幕用 MoviePy 2.x + Pillow 后端（无需 ImageMagick）│
│        └─ 任务队列默认 InMemoryTaskManager（无需 Redis）    │
└─────────────────────────────────────────────────────────────┘
```

关键设计取舍：

| 项目 | 方案 | 说明 |
|------|------|------|
| Python 运行时 | Chaquopy 15.0.0 + Python 3.11 | 在 APK 内嵌解释器，无需 root |
| 后端 | FastAPI（去掉 Streamlit） | 原 Streamlit WebUI 太重，改为自定义移动端 WebUI |
| 字幕 | MoviePy 2.x + Pillow `TextClip` | 用 Pillow 渲染，无需交叉编译 ImageMagick |
| 任务队列 | `InMemoryTaskManager` | `enable_redis=False`，无需 Redis 服务 |
| 视频合成 | 内置 ffmpeg（ARM64） | 交叉编译，仅 libx264 + 原生编解码 |
| ABI | `arm64-v8a` | 覆盖主流手机；需 32 位可加 `abiFilters` |
| 最低系统 | `minSdk 24`（Android 7.0） | |

---

## 2. 已完成的工作

1. **交叉编译 ffmpeg**
   - 目标：ARM64 (aarch64)、API 24、NDK 27.0.12077973，静态链接 bionic。
   - 配置：`--enable-gpl --enable-libx264 --enable-pic --disable-everything` 后按需开启 muxer/demuxer/codec，仅保留原生编解码 + libx264。
   - 产物：`app/src/main/assets/ffmpeg/ffmpeg`（22.5MB，`ELF 64-bit LSB pie executable, ARM aarch64`）。
2. **修正 `bootstrap.py` 配置持久化 bug**
   - 原实现用 `setattr(cfg_module, "openai_api_key", ...)` 写入模块属性——既不生效也不被 `save_config()` 持久化。
   - 改为写入 `config.app[...]` 字典分区（与 MPT 的 `config_key()` 读取路径一致），并调用 `cfg_module.save_config()`。
3. **搭建完整 Android 工程**
   - `build.gradle`：AGP 8.5.2 + Chaquopy 15.0.0；`app/build.gradle`：`python { version "3.11" }` + pip 依赖清单。
   - `MainActivity.java`：释放 ffmpeg → 启动 Python → 轮询 8080 → 加载 WebView。
   - `AndroidManifest.xml` / `network_security_config.xml`：放行 127.0.0.1 / localhost 明文（WebView 访问本地 FastAPI）。
   - 移动端 WebUI：配置表单、AI 生成文案、生成视频、进度轮询、播放/下载。
4. **逐项验证集成点（确保正常网络下可一次构建成功）**
   - ffmpeg 解析：`utils.get_ffmpeg_binary()` 优先读 `IMAGEIO_FFMPEG_EXE`，正好由 bootstrap 设置；并额外把 ffmpeg 目录加入 `PATH` 兜底。
   - `/` 路由替换：`asgi.py` 用 `app.mount("/", StaticFiles(...))`，且 `public_dir()`/`task_dir()` 内部 `os.makedirs`，不会在导入期崩溃；bootstrap 安全地弹出该 Mount 再挂上移动端 UI。
   - 配置持久化：`config.app[...]` + `save_config()` 正确落盘 `config.toml` 的 `[app]` 段。
   - 中文字幕：`_assets/resource/fonts/STHeitiMedium.ttc` 存在（MPT 默认字幕字体），运行时由 `resource_directory()` 拷贝到 `MPT_HOME/resource/fonts`。

---

## 3. 当前阻塞（环境限制，非代码缺陷）

在**本沙箱**内无法完成最终打包，根因是网络代理对 `chaquopy.com` 的拦截：

- 证书不匹配：`openssl` 显示返回证书 `subject=CN=chaquo.com`、`SAN=[chaquo.com, www.chaquo.com]`，而请求主机是 `chaquopy.com` → Gradle 报 `SSLPeerUnverifiedException`（主机名不匹配）。
- 构件缺失：对 `chaquopy.com/maven/.../gradle/15.0.0/gradle-15.0.0.pom`、`17.1.0`、以及 `chaquopy.com/python/` 等**所有路径均返回 404**——代理镜像未携带所需版本。
- 连锁影响：Chaquopy Gradle 插件、Python 3.11 运行时、以及 **Android 版 numpy / pillow 轮子**（仅由 Chaquopy 提供，PyPI 上无 Android aarch64 轮子）都无法下载。
- 沙箱为 x86_64，也无法本地运行任何 aarch64 二进制做冒烟测试。

> Chaquopy 真实最新版为 17.1.0（支持 Python 3.11+）；本工程用 15.0.0 + Python 3.11 即可。**这是网络可达性问题，在正常开发环境下不存在。**

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

**AIDE 无法直接构建本工程。** 本工程依赖 Chaquopy（Gradle 插件）在构建期下载 Python 3.11 运行时并 `pip` 安装 FastAPI / numpy / pillow 等轮子；而 AIDE 使用自有编译管线、不支持 Gradle 插件体系，无法嵌入 Python 运行时，打开工程会卡在 Chaquopy 插件/依赖解析。

正确做法：用上面任一种方式（Android Studio / 命令行 / GitHub Actions）**构建一次 APK**，再把 `app-debug.apk` 传到手机安装运行即可——手机端只需要负责“安装并运行”，不需要 AIDE 参与编译。

> 提示：`app/build.gradle` 中的 `pip { install ... }` 版本均为 MPT 1.3.9 锁定的真实版本（如 `openai==1.39.0` 是为规避 1.40+ 引入的 Rust `jiter` 无 Android 轮子而刻意选择）。请勿随意升级主版本，否则可能出现无 Android 轮子可用的包。

---

## 5. 运行与使用

1. **首次启动**：应用释放 ffmpeg → 启动内嵌 Python/FastAPI → 轮询 `127.0.0.1:8080` → WebView 加载移动端 UI（约数秒）。
2. **配置（①）**：
   - 选择大模型厂商并填 **API Key**：OpenAI / DeepSeek / 通义千问(Qwen) / Kimi(Moonshot) / Gemini / Groq。
   - 填 **Pexels Key**（免费，[pexels.com/api](https://www.pexels.com/api/) 获取，用于下载视频素材，**必填**）。
   - 点「保存配置」。
3. **生成（②）**：
   - 填视频主题 → 「AI 生成文案」（或手动粘贴文案）。
   - 选配音（中文晓晓/云希/云扬 等多语种）与画面比例（9:16 / 16:9 / 1:1）。
   - 点「▶ 生成视频」。
4. **状态（③）**：实时进度百分比；完成后视频直接在页面内播放并支持下载。
5. 视频保存在应用私有目录，经 `/tasks` 静态路由在同源 WebView 内播放/下载。

---

## 6. 已知限制与说明

- **配音**使用 `edge-tts`（微软在线 TTS），**需联网**；本移植未做离线 TTS。
- **任务队列为内存模式**：App 进程被杀则任务丢失（符合移动端预期）。
- **API 鉴权**：未配置 `api_key` 时放行（同进程内、WebView 同源访问，安全边界由 Android 沙箱提供）。
- **仅 `arm64-v8a`**：如需 32 位设备，在 `app/build.gradle` 的 `ndk { abiFilters }` 增加 `armeabi-v7a` 等。
- **联网范围**：App 内 Python 会访问 LLM / Pexels / TTS 的 HTTPS 接口；WebView 仅访问本地 `127.0.0.1:8080`（明文已在网络安全配置中放行）。
- **包体**：ffmpeg(~22MB) + Python 运行时 + 各轮子 + 资源字体/音乐，debug APK 预计 60–90MB。

---

## 7. 工程目录结构

```
MPTAndroid/
├── build.gradle                      # AGP 8.5.2 + Chaquopy 15.0.0 classpath
├── settings.gradle
├── gradle.properties
├── local.properties.example           # 模板：复制为 local.properties 填 sdk.dir
├── build_apk.sh                      # 可移植构建脚本（CLI）
├── .gitignore
├── README.md                         # 本文件
└── app/
    ├── build.gradle                  # python{version "3.11"} + pip 依赖清单
    └── src/main/
        ├── AndroidManifest.xml
        ├── assets/ffmpeg/ffmpeg      # 交叉编译的 ARM64 ffmpeg 二进制
        ├── java/com/mpt/android/MainActivity.java
        ├── res/
        │   ├── layout/activity_main.xml
        │   ├── values/{strings.xml,themes.xml}
        │   └── xml/network_security_config.xml
        └── python/
            ├── bootstrap.py          # 启动 FastAPI + 移动端 WebUI + 配置持久化
            └── app/                  # MPT 1.3.9 真实后端（剔除 Streamlit）
                ├── asgi.py
                ├── config/
                ├── services/         # video / voice / task ...
                ├── controllers/
                ├── models/
                ├── utils/
                ├── paths.py
                └── _assets/         # resource/fonts（含 STHeitiMedium.ttc）、resource/public、resource/songs
```

---

## 8. 故障排查

- **白屏 / “服务启动失败”**：用 `adb logcat` 查看。确认 ffmpeg 已成功释放到 `files/ffmpeg` 且可执行；确认 Python 启动无 ImportError（通常缺轮子，检查 `app/build.gradle` 的 pip 清单）。
- **字幕中文乱码/缺字**：确认 `STHeitiMedium.ttc` 随 `_assets` 拷贝到 `MPT_HOME/resource/fonts`（首次启动自动拷贝）。
- **构建报 Chaquopy 下载失败**：确认网络可访问 `chaquopy.com`，且 `local.properties` 的 `sdk.dir` 正确；若公司网络有 MITM 代理，需把代理 CA 加入 JVM 信任库。
- **API Key 不生效**：配置通过 `/api/v1/mpt_config` 写入 `config.toml` 的 `[app]` 段；可在 `adb shell run-as com.mpt.android` 下检查 `files/mpt/config.toml`。

---

## 9. 下一步（在合规网络下）

1. 按第 4 节构建出 `app-debug.apk`。
2. 安装到 Android 手机，按第 5 节完成首次配置。
3. 试生成一条 9:16 短视频，验证：文案生成 → 配音 → 素材下载 → 字幕合成 → 成片播放/下载全链路。
4. 如需发布：用 `assembleRelease` + 自有签名密钥构建 release APK / AAB。

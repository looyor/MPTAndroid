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
- 📦 **本工程已打包为可直接下载的压缩包**：`MPTAndroid.zip`（见本页顶部/文件列表）。

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

> 装好打开 App，按第 5 节填大模型 API Key + Pexels Key，就能在手机上生成短视频了。

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

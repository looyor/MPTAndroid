#!/bin/bash
# 构建 MoneyPrinterTurbo Android APK（debug）。
# 前置条件：
#   - 已安装 Android SDK（建议 API 34），并设置 ANDROID_HOME 或 ANDROID_SDK_ROOT
#   - 已安装 Gradle 8.9（或用 Android Studio 自带的 gradle wrapper）
#   - 能正常访问 chaquopy.com（用于下载 Chaquopy 插件、Python 3.11 运行时与 Android 轮子）
#   - （可选）NDK 27
# 用法：
#   export ANDROID_HOME=/path/to/Android/Sdk
#   ./build_apk.sh
set -e

cd "$(dirname "$0")"

: "${ANDROID_HOME:=$ANDROID_SDK_ROOT}"
if [ -z "$ANDROID_HOME" ]; then
  echo "ERROR: 请先设置 ANDROID_HOME（或 ANDROID_SDK_ROOT）指向 Android SDK。" >&2
  exit 1
fi
export ANDROID_HOME
[ -n "$ANDROID_NDK" ] && export ANDROID_NDK

# 优先使用工程内的 gradle wrapper，否则使用系统 gradle
GRADLE_BIN="$(command -v gradle || true)"
if [ -x ./gradlew ]; then
  GRADLE_BIN=./gradlew
fi
if [ -z "$GRADLE_BIN" ]; then
  echo "ERROR: 未找到 gradle（也没有 ./gradlew）。请安装 Gradle 8.9 或用 Android Studio 打开本工程。" >&2
  exit 1
fi

echo "Gradle: $($GRADLE_BIN --version 2>/dev/null | grep -i Gradle || echo unknown)"
echo "ANDROID_HOME=$ANDROID_HOME"

"$GRADLE_BIN" assembleDebug --no-daemon "$@"

echo ""
echo "构建完成。APK 位于："
echo "  app/build/outputs/apk/debug/app-debug.apk"

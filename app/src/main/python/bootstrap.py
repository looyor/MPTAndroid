# -*- coding: utf-8 -*-
"""
Bootstrap for the MoneyPrinterTurbo Android app (light edition).

由 Java (MainActivity) 调用 start_server(mpt_home, ffmpeg_path)：
  1. 设置运行时路径（MPT_HOME、ffmpeg）。
  2. 启动标准库 HTTP 服务（mobile_server），监听 127.0.0.1:8080。
  3. WebView 与 REST API 同源，无需 CORS。

不再依赖 FastAPI / uvicorn / pydantic，所有 Python 第三方依赖仅
requests / gtts / pillow，均可在 Chaquopy(Android aarch64) 上安装。
"""

import os
import threading

# 由 Java 在导入前通过 start_server() 注入。
MPT_HOME = None
FFMPEG_PATH = None


def start_server(mpt_home, ffmpeg_path):
    global MPT_HOME, FFMPEG_PATH
    MPT_HOME = mpt_home
    FFMPEG_PATH = ffmpeg_path

    os.environ["MPT_HOME"] = mpt_home
    if ffmpeg_path and os.path.isfile(ffmpeg_path):
        os.environ["MPT_FFMPEG"] = ffmpeg_path
        ffmpeg_dir = os.path.dirname(ffmpeg_path)
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")

    # 设置全局路径（mobile_server 在导入时会读取这些全局变量）。
    import mobile_server
    mobile_server.MPT_HOME = mpt_home
    mobile_server.FFMPEG_PATH = ffmpeg_path
    mobile_server.CONFIG_PATH = os.path.join(mpt_home, "config.json")
    # 资源目录：python 源码根下的 app/_assets/resource
    here = os.path.dirname(os.path.abspath(__file__))
    mobile_server.ASSET_ROOT = os.path.join(here, "app", "_assets", "resource")

    if mobile_server.Image is None:
        print("WARNING: PIL 未就绪，字幕渲染将不可用：%s" % mobile_server._PIL_ERROR, flush=True)

    def _run():
        mobile_server.run(host="127.0.0.1", port=8080)

    t = threading.Thread(target=_run, daemon=True)
    t.start()

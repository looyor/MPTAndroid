package com.mpt.android;

import android.Manifest;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.Settings;
import android.webkit.WebChromeClient;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;

import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;

public class MainActivity extends AppCompatActivity {

    private static final int PORT = 8080;
    private WebView webView;
    private File ffmpegBin;

    private static final String LOADING_HTML =
            "<!doctype html><html><head><meta charset='utf-8'>"
            + "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            + "<style>html,body{margin:0;height:100%;background:#0b0c10;color:#e8e8ef;"
            + "font-family:-apple-system,Segoe UI,Roboto,sans-serif;display:flex;"
            + "flex-direction:column;align-items:center;justify-content:center}"
            + ".t{font-size:20px;font-weight:700;letter-spacing:.5px}"
            + ".s{margin-top:14px;font-size:13px;color:#9aa0b4}"
            + ".ring{margin-top:26px;width:38px;height:38px;border:4px solid #2b2f4a;"
            + "border-top-color:#7c5cff;border-radius:50%;animation:spin 1s linear infinite}"
            + "@keyframes spin{to{transform:rotate(360deg)}}</style></head>"
            + "<body><div class='t'>MPT&nbsp;Turbo</div><div class='s'>正在启动本地服务…</div>"
            + "<div class='ring'></div></body></html>";

    private static final String ERROR_HTML =
            "<!doctype html><html><head><meta charset='utf-8'>"
            + "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            + "<style>html,body{margin:0;height:100%;background:#0b0c10;color:#e8e8ef;"
            + "font-family:-apple-system,Segoe UI,Roboto,sans-serif;display:flex;"
            + "flex-direction:column;align-items:center;justify-content:center;padding:24px;text-align:center}"
            + ".t{font-size:19px;font-weight:700;color:#ff6b6b}"
            + ".s{margin-top:12px;font-size:13px;color:#9aa0b4;line-height:1.6}</style></head>"
            + "<body><div class='t'>服务启动失败</div>"
            + "<div class='s'>Python 本地服务未能在 60 秒内就绪。<br>"
            + "请重启应用；若仍失败，用电脑执行 adb logcat 查看详细错误。</div></body></html>";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        webView = findViewById(R.id.webview);
        webView.getSettings().setJavaScriptEnabled(true);
        webView.getSettings().setDomStorageEnabled(true);
        webView.getSettings().setAllowFileAccess(false);
        webView.getSettings().setMediaPlaybackRequiresUserGesture(false);
        webView.setWebViewClient(new WebViewClient());
        webView.setWebChromeClient(new WebChromeClient());

        // 先展示启动加载页，避免服务未就绪时出现空白白屏。
        webView.loadDataWithBaseURL(null, LOADING_HTML, "text/html", "utf-8", null);

        // 0) 申请存储权限（导出视频到 Download/Ai视频 需要）
        ensureStoragePermission();

        // 1) 解析可执行的 ffmpeg（安装时释放到 nativeLibraryDir 的 libffmpeg.so）。
        ffmpegBin = resolveFfmpeg();

        // 2) Start the embedded Python (FastAPI) server in a background thread.
        startPythonServer();

        // 3) Wait for the server, then load the WebUI inside the WebView.
        new Thread(() -> {
            boolean up = false;
            for (int i = 0; i < 120; i++) {
                try {
                    java.net.Socket s = new java.net.Socket("127.0.0.1", PORT);
                    s.close();
                    up = true;
                    break;
                } catch (Exception e) {
                    try {
                        Thread.sleep(500);
                    } catch (InterruptedException ignored) {
                    }
                }
            }
            final boolean serverUp = up;
            runOnUiThread(() -> {
                if (serverUp) {
                    webView.loadUrl("http://127.0.0.1:" + PORT + "/");
                } else {
                    webView.loadDataWithBaseURL(null, ERROR_HTML, "text/html", "utf-8", null);
                    Toast.makeText(MainActivity.this,
                            "服务启动失败，请查看 logcat", Toast.LENGTH_LONG).show();
                }
            });
        }).start();
    }

    /**
     * 返回可执行的 ffmpeg 路径。
     * 关键：Android 10+ 禁止执行应用私有可写目录（/data/user/0/.../files）里的
     * 二进制，会报 [Errno 13] Permission denied。只有安装时由系统释放到
     * nativeLibraryDir 的 libffmpeg.so 才具有可执行权限，因此这里优先用它。
     * 老系统（Android 9 及以下）退回 files 目录解压的老路径作兜底。
     */
    private File resolveFfmpeg() {
        try {
            File lib = new File(getApplicationInfo().nativeLibraryDir, "libffmpeg.so");
            if (lib.exists()) {
                //noinspection ResultOfMethodCallIgnored
                lib.setExecutable(true, false);
                return lib;
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
        return new File(getFilesDir(), "ffmpeg");
    }

    private void startPythonServer() {
        if (!Python.isStarted()) {
            Python.start(new AndroidPlatform(this));
        }
        File mptHome = new File(getFilesDir(), "mpt");
        //noinspection ResultOfMethodCallIgnored
        mptHome.mkdirs();
        File ffmpeg = (ffmpegBin != null) ? ffmpegBin : resolveFfmpeg();

        // 导出目录：手机「下载 / Download」下的 Ai视频 文件夹
        File downloadDir = new File(
                Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS),
                "Ai视频");

        Thread serverThread = new Thread(() -> {
            try {
                Python py = Python.getInstance();
                py.getModule("bootstrap").callAttr(
                        "start_server",
                        mptHome.getAbsolutePath(),
                        ffmpeg.getAbsolutePath(),
                        downloadDir.getAbsolutePath()
                );
            } catch (Exception e) {
                e.printStackTrace();
            }
        });
        serverThread.setDaemon(true);
        serverThread.start();
    }

    /**
     * 确保应用有权把视频写入 Download/Ai视频。
     * - Android 11+：引导用户开启「所有文件访问」权限（MANAGE_EXTERNAL_STORAGE）。
     * - Android 6~10：请求 READ/WRITE_EXTERNAL_STORAGE。
     */
    private void ensureStoragePermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            if (!Environment.isExternalStorageManager()) {
                try {
                    Intent intent = new Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION);
                    intent.setData(Uri.parse("package:" + getPackageName()));
                    startActivity(intent);
                    Toast.makeText(this,
                            "请开启「允许访问所有文件」，视频才能保存到 Download/Ai视频",
                            Toast.LENGTH_LONG).show();
                } catch (Exception e) {
                    Toast.makeText(this,
                            "请在系统设置中授予「所有文件访问」权限", Toast.LENGTH_LONG).show();
                }
            }
        } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            if (checkSelfPermission(Manifest.permission.WRITE_EXTERNAL_STORAGE)
                    != PackageManager.PERMISSION_GRANTED) {
                ActivityCompat.requestPermissions(this,
                        new String[]{
                                Manifest.permission.WRITE_EXTERNAL_STORAGE,
                                Manifest.permission.READ_EXTERNAL_STORAGE
                        }, 1001);
            }
        }
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }
}

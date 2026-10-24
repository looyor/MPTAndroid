package com.mpt.android;

import android.os.Bundle;
import android.webkit.WebChromeClient;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;

public class MainActivity extends AppCompatActivity {

    private static final int PORT = 8080;
    private WebView webView;

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

        // 1) Extract the bundled ffmpeg binary to a writable location.
        extractFfmpeg();

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
                    Toast.makeText(MainActivity.this,
                            "服务启动失败，请查看 logcat", Toast.LENGTH_LONG).show();
                }
            });
        }).start();
    }

    private void extractFfmpeg() {
        try {
            File out = new File(getFilesDir(), "ffmpeg");
            // Re-extract if missing or suspiciously small.
            if (!out.exists() || out.length() < 5_000_000L) {
                InputStream in = getAssets().open("ffmpeg/ffmpeg");
                OutputStream os = new FileOutputStream(out);
                byte[] buf = new byte[8192];
                int n;
                while ((n = in.read(buf)) > 0) {
                    os.write(buf, 0, n);
                }
                in.close();
                os.close();
                //noinspection ResultOfMethodCallIgnored
                out.setExecutable(true, false);
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    private void startPythonServer() {
        if (!Python.isStarted()) {
            Python.start(new AndroidPlatform(this));
        }
        File mptHome = new File(getFilesDir(), "mpt");
        //noinspection ResultOfMethodCallIgnored
        mptHome.mkdirs();
        File ffmpeg = new File(getFilesDir(), "ffmpeg");

        Thread serverThread = new Thread(() -> {
            try {
                Python py = Python.getInstance();
                py.getModule("bootstrap").callAttr(
                        "start_server",
                        mptHome.getAbsolutePath(),
                        ffmpeg.getAbsolutePath()
                );
            } catch (Exception e) {
                e.printStackTrace();
            }
        });
        serverThread.setDaemon(true);
        serverThread.start();
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

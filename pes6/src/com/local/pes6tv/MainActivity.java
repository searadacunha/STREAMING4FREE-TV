package com.local.pes6tv;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.view.InputDevice;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import android.webkit.CookieManager;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.Toast;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.Locale;

/** An independent Android TV tile for the PES 6 browser port. Does not bundle game data. */
public final class MainActivity extends Activity {
    private static final String HOME = "https://pes6.optijuegos.net/";
    private FrameLayout root;
    private WebView web;
    private View fullscreen;
    private WebChromeClient.CustomViewCallback fullscreenCallback;
    private String bridge = "";
    private boolean ready;

    @Override public void onCreate(Bundle b) {
        super.onCreate(b);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        immersive();
        root = new FrameLayout(this);
        root.setBackgroundColor(Color.BLACK);
        web = new WebView(this);
        web.setBackgroundColor(Color.BLACK);
        web.setFocusable(true);
        web.setFocusableInTouchMode(true);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true); // Game assets, saved settings and saves stay in browser storage.
        s.setDatabaseEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setUseWideViewPort(true);
        s.setLoadWithOverviewMode(true);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, false);
        bridge = readBridge();
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest request) {
                if (!request.isForMainFrame()) return false;
                Uri u = request.getUrl();
                return !("https".equalsIgnoreCase(u.getScheme())
                    && "pes6.optijuegos.net".equalsIgnoreCase(u.getHost()));
            }
            @Override public void onPageStarted(WebView v, String url, android.graphics.Bitmap icon) {
                ready = false;
            }
            @Override public void onPageFinished(WebView v, String url) {
                if (url.startsWith(HOME) && !bridge.isEmpty()) {
                    v.evaluateJavascript(bridge, new android.webkit.ValueCallback<String>() {
                        @Override public void onReceiveValue(String ignored) { ready = true; }
                    });
                }
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override public void onPermissionRequest(PermissionRequest request) {
                request.deny(); // Gamepads do not need camera/microphone permissions.
            }
            @Override public void onShowCustomView(View view, CustomViewCallback callback) {
                if (fullscreen != null) { callback.onCustomViewHidden(); return; }
                fullscreen = view; fullscreenCallback = callback;
                root.addView(view, new FrameLayout.LayoutParams(-1, -1));
                web.setVisibility(View.GONE);
                view.requestFocus();
            }
            @Override public void onHideCustomView() { hideFullscreen(); }
        });
        root.addView(web, new FrameLayout.LayoutParams(-1, -1));
        setContentView(root);
        boolean restored = b != null && web.restoreState(b) != null;
        if (!restored) web.loadUrl(HOME);
        web.requestFocus();
    }

    private String readBridge() {
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(
                getAssets().open("gamepad-bridge.js"), StandardCharsets.UTF_8))) {
            StringBuilder out = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) out.append(line).append('\n');
            return out.toString();
        } catch (Exception ignored) {
            return ""; // Native Gamepad API can still operate.
        }
    }

    private void immersive() {
        getWindow().getDecorView().setSystemUiVisibility(
            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY | View.SYSTEM_UI_FLAG_FULLSCREEN
            | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
            | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_LAYOUT_STABLE);
    }
    @Override public void onWindowFocusChanged(boolean focused) {
        super.onWindowFocusChanged(focused);
        if (focused) immersive();
    }

    private boolean fromPad(KeyEvent event) {
        int source = event.getSource();
        InputDevice dev = event.getDevice();
        if (dev != null) source |= dev.getSources();
        return (source & InputDevice.SOURCE_GAMEPAD) == InputDevice.SOURCE_GAMEPAD
            || (source & InputDevice.SOURCE_JOYSTICK) == InputDevice.SOURCE_JOYSTICK;
    }

    /** W3C standard Gamepad mapping for Android key events, including gamepad BACK fallback. */
    static int button(int key) {
        switch (key) {
            case KeyEvent.KEYCODE_BUTTON_A: return 0;
            case KeyEvent.KEYCODE_BUTTON_B: case KeyEvent.KEYCODE_BACK: return 1;
            case KeyEvent.KEYCODE_BUTTON_X: return 2;
            case KeyEvent.KEYCODE_BUTTON_Y: return 3;
            case KeyEvent.KEYCODE_BUTTON_L1: return 4;
            case KeyEvent.KEYCODE_BUTTON_R1: return 5;
            case KeyEvent.KEYCODE_BUTTON_L2: return 6;
            case KeyEvent.KEYCODE_BUTTON_R2: return 7;
            case KeyEvent.KEYCODE_BUTTON_SELECT: return 8;
            case KeyEvent.KEYCODE_BUTTON_START: return 9;
            case KeyEvent.KEYCODE_BUTTON_THUMBL: return 10;
            case KeyEvent.KEYCODE_BUTTON_THUMBR: return 11;
            case KeyEvent.KEYCODE_DPAD_UP: return 12;
            case KeyEvent.KEYCODE_DPAD_DOWN: return 13;
            case KeyEvent.KEYCODE_DPAD_LEFT: return 14;
            case KeyEvent.KEYCODE_DPAD_RIGHT: return 15;
            case KeyEvent.KEYCODE_BUTTON_MODE: return 16;
            default: return -1;
        }
    }
    private void js(String code) {
        if (ready && web != null) web.evaluateJavascript(code, null);
    }
    @Override public boolean dispatchKeyEvent(KeyEvent event) {
        int key = event.getKeyCode();
        if (fromPad(event)) {
            int index = button(key);
            if (index >= 0) {
                boolean pressed = event.getAction() == KeyEvent.ACTION_DOWN;
                js("window.__pes6PadBridge&&window.__pes6PadBridge.button("
                    + index + "," + pressed + ")");
                // Pass through to native WebView input, without letting controller B exit the app.
                if (key != KeyEvent.KEYCODE_BACK) {
                    (fullscreen != null ? fullscreen : web).dispatchKeyEvent(event);
                }
                return true;
            }
        }
        if (key == KeyEvent.KEYCODE_MENU) {
            if (event.getAction() == KeyEvent.ACTION_UP) showMenu();
            return true;
        }
        if (key == KeyEvent.KEYCODE_BACK) {
            if (event.getAction() == KeyEvent.ACTION_UP) onBackPressed();
            return true;
        }
        return super.dispatchKeyEvent(event);
    }

    private static float axis(MotionEvent e, int primary, int alternate) {
        float value = e.getAxisValue(primary);
        if (Math.abs(value) < .001f && alternate >= 0) value = e.getAxisValue(alternate);
        return Math.max(-1, Math.min(1, value));
    }
    @Override public boolean dispatchGenericMotionEvent(MotionEvent e) {
        if ((e.getSource() & InputDevice.SOURCE_JOYSTICK) == InputDevice.SOURCE_JOYSTICK
            && e.getAction() == MotionEvent.ACTION_MOVE) {
            float x = axis(e, MotionEvent.AXIS_X, -1);
            float y = axis(e, MotionEvent.AXIS_Y, -1);
            float rx = axis(e, MotionEvent.AXIS_Z, MotionEvent.AXIS_RX);
            float ry = axis(e, MotionEvent.AXIS_RZ, MotionEvent.AXIS_RY);
            float lt = Math.max(0, axis(e, MotionEvent.AXIS_LTRIGGER, MotionEvent.AXIS_BRAKE));
            float rt = Math.max(0, axis(e, MotionEvent.AXIS_RTRIGGER, MotionEvent.AXIS_GAS));
            float hx = axis(e, MotionEvent.AXIS_HAT_X, -1);
            float hy = axis(e, MotionEvent.AXIS_HAT_Y, -1);
            js(String.format(Locale.US,
                "window.__pes6PadBridge&&window.__pes6PadBridge.axes([%.3f,%.3f,%.3f,%.3f],%.3f,%.3f,%.3f,%.3f)",
                x, y, rx, ry, lt, rt, hx, hy));
        }
        return super.dispatchGenericMotionEvent(e);
    }

    private void showMenu() {
        new AlertDialog.Builder(this).setTitle("PES 2006")
            .setItems(new String[]{"Recharger", "Diagnostic TV / manette", "Ouvrir dans le navigateur"},
                new android.content.DialogInterface.OnClickListener() {
                    @Override public void onClick(android.content.DialogInterface dialog, int choice) {
                        if (choice == 0) web.reload();
                        else if (choice == 1) diagnostic();
                        else openBrowser();
                    }
                }).show();
    }
    private void diagnostic() {
        StringBuilder names = new StringBuilder();
        for (int id : InputDevice.getDeviceIds()) {
            InputDevice d = InputDevice.getDevice(id);
            if (d == null) continue;
            if ((d.getSources() & InputDevice.SOURCE_GAMEPAD) == InputDevice.SOURCE_GAMEPAD
                || (d.getSources() & InputDevice.SOURCE_JOYSTICK) == InputDevice.SOURCE_JOYSTICK) {
                if (names.length() > 0) names.append(", ");
                names.append(d.getName());
            }
        }
        final String devices = names.length() == 0 ? "aucune manette Android" : names.toString();
        web.evaluateJavascript("(function(){var c=document.createElement('canvas');return JSON.stringify({webgl2:!!c.getContext('webgl2'),pads:((navigator.getGamepads&&navigator.getGamepads())||[]).filter(Boolean).length})})()",
            new android.webkit.ValueCallback<String>() {
                @Override public void onReceiveValue(String result) {
                    new AlertDialog.Builder(MainActivity.this).setTitle("Diagnostic PES 2006")
                        .setMessage("Appareil(s) : " + devices + "\\nWebView : " + result
                            + "\\n\\nTester ensuite boutons et sticks dans un match.")
                        .setPositiveButton("OK", null).show();
                }
            });
    }
    private void openBrowser() {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(HOME))
                .addCategory(Intent.CATEGORY_BROWSABLE));
        } catch (ActivityNotFoundException e) {
            Toast.makeText(this, "Aucun navigateur trouvé sur la TV", Toast.LENGTH_LONG).show();
        }
    }
    private void hideFullscreen() {
        if (fullscreen == null) return;
        root.removeView(fullscreen); fullscreen = null;
        web.setVisibility(View.VISIBLE); web.requestFocus();
        if (fullscreenCallback != null) {
            fullscreenCallback.onCustomViewHidden();
            fullscreenCallback = null;
        }
    }
    @Override public void onBackPressed() {
        if (fullscreen != null) hideFullscreen();
        else if (web.canGoBack()) web.goBack();
        else super.onBackPressed();
    }
    @Override protected void onNewIntent(Intent i) { super.onNewIntent(i); web.loadUrl(HOME); }
    @Override protected void onPause() {
        super.onPause(); web.onPause(); CookieManager.getInstance().flush();
    }
    @Override protected void onResume() { super.onResume(); web.onResume(); }
    @Override protected void onSaveInstanceState(Bundle b) {
        super.onSaveInstanceState(b); web.saveState(b);
    }
    @Override protected void onDestroy() {
        root.removeAllViews(); web.destroy(); super.onDestroy();
    }
}

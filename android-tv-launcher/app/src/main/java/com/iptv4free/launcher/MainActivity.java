package com.iptv4free.launcher;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.res.ColorStateList;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.PixelFormat;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.provider.Settings;
import android.util.Log;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.charset.StandardCharsets;

/**
 * One user-initiated Android TV tile -> official Kodi -> installed IPTV4FREE Kodi add-on.
 * While Kodi starts, an IPTV4FREE cover (official logo on black) sits above every window, so Kodi's
 * splash and its skin never show; it fades out once the add-on window is on screen.
 * Does not replace Kodi, edit its files, change its skin, or touch other applications.
 */
public final class MainActivity extends Activity {
    private static final String TAG = "IPTV4FREE-Launcher";
    private static final String KODI = "org.xbmc.kodi";
    private static final String ADDON = "script.iptv4free";
    private static final int PORT = 9090;
    private static final long DEADLINE_MS = 30000;
    private static final long WINDOW_DEADLINE_MS = 15000;
    private static final long FADE_MS = 300;
    private static final int MAX_REPLY = 65536;
    private static final String SHOW_ERROR = "com.iptv4free.launcher.SHOW_ERROR";
    // The add-on stores its window id on Kodi's Home window as soon as that window opens.
    private static final String WINDOW_ID = "Window(Home).Property(iptv4free.window)";

    private final Handler main = new Handler(Looper.getMainLooper());
    private LinearLayout errorPanel;
    private ProgressBar progress;
    private TextView status;
    private Button retry;
    private Button openKodi;
    private volatile View cover;
    private boolean watchingHome;
    private volatile boolean launching;
    private volatile boolean cancelled;

    private final BroadcastReceiver homeKey = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            String reason = intent.getStringExtra("reason");
            // TV home or recents opened during the start: never leave the cover over another app.
            if ("homekey".equals(reason) || "recentapps".equals(reason)) {
                cancelled = true;
                launching = false;
                hideCover();
                finish();
            }
        }
    };

    @Override
    protected void onCreate(Bundle saved) {
        super.onCreate(saved);
        createScreen();
        beginLaunch();
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        if (!launching && !intent.getBooleanExtra(SHOW_ERROR, false)) beginLaunch();
    }

    @Override
    protected void onDestroy() {
        hideCover();
        super.onDestroy();
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    /** Same drawable as the window background (theme), so the logo never moves between screens. */
    private ProgressBar fillSplash(FrameLayout root) {
        root.setBackgroundResource(R.drawable.iptv4free_splash);
        ProgressBar bar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        bar.setIndeterminate(true);
        bar.setIndeterminateTintList(ColorStateList.valueOf(Color.rgb(169, 179, 201)));
        // Where the add-on writes "Chargement des chaînes…" under the same logo.
        FrameLayout.LayoutParams params = new FrameLayout.LayoutParams(dp(160), -2,
                Gravity.TOP | Gravity.CENTER_HORIZONTAL);
        params.topMargin = dp(448);
        root.addView(bar, params);
        return bar;
    }

    private void createScreen() {
        getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);
        FrameLayout root = new FrameLayout(this);
        progress = fillSplash(root);

        errorPanel = new LinearLayout(this);
        errorPanel.setOrientation(LinearLayout.VERTICAL);
        errorPanel.setGravity(Gravity.CENTER);
        errorPanel.setPadding(dp(22), dp(15), dp(22), dp(15));
        errorPanel.setBackgroundColor(Color.BLACK);
        errorPanel.setVisibility(View.GONE);
        root.addView(errorPanel, new FrameLayout.LayoutParams(-1, -1));

        ImageView logo = new ImageView(this);
        logo.setImageResource(R.drawable.iptv4free_logo_original);
        logo.setAdjustViewBounds(true);
        logo.setScaleType(ImageView.ScaleType.FIT_CENTER);
        errorPanel.addView(logo, new LinearLayout.LayoutParams(dp(270), dp(180)));

        status = new TextView(this);
        status.setTextColor(Color.WHITE);
        status.setTextSize(19);
        status.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams textParams = new LinearLayout.LayoutParams(-1, -2);
        textParams.topMargin = dp(9);
        errorPanel.addView(status, textParams);

        retry = new Button(this);
        retry.setText("Réessayer");
        retry.setOnClickListener(v -> beginLaunch());
        LinearLayout.LayoutParams buttonParams = new LinearLayout.LayoutParams(dp(125), -2);
        buttonParams.topMargin = dp(11);
        buttonParams.gravity = Gravity.CENTER;
        errorPanel.addView(retry, buttonParams);

        openKodi = new Button(this);
        openKodi.setText("Ouvrir Kodi uniquement");
        openKodi.setOnClickListener(v -> {
            try {
                launchKodi();
                finish();
            } catch (Exception e) {
                showError("Kodi est introuvable sur cet appareil.");
            }
        });
        LinearLayout.LayoutParams otherParams = new LinearLayout.LayoutParams(dp(150), -2);
        otherParams.topMargin = dp(5);
        otherParams.gravity = Gravity.CENTER;
        errorPanel.addView(openKodi, otherParams);

        setContentView(root);
    }

    private Intent kodiIntent() {
        Intent intent = getPackageManager().getLeanbackLaunchIntentForPackage(KODI);
        if (intent == null) intent = getPackageManager().getLaunchIntentForPackage(KODI);
        if (intent == null) throw new ActivityNotFoundException("Kodi non installé");
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        return intent;
    }

    private void launchKodi() {
        startActivity(kodiIntent());
    }

    private WindowManager windows() {
        return (WindowManager) getApplicationContext().getSystemService(WINDOW_SERVICE);
    }

    /**
     * Puts the splash above every app, Kodi included, then runs {@code afterFirstFrame} once it is
     * drawn. False without the "display over other apps" access (granted once by ADB, see docs).
     */
    private boolean showCover(Runnable afterFirstFrame) {
        if (!Settings.canDrawOverlays(this)) {
            Log.w(TAG, "No overlay access: Kodi's own screens will show while it starts");
            return false;
        }
        Runnable once = new Runnable() {
            private boolean done;

            @Override
            public void run() {
                if (!done) {
                    done = true;
                    afterFirstFrame.run();
                }
            }
        };
        FrameLayout view = new FrameLayout(this) {
            private boolean drawn;

            @Override
            protected void dispatchDraw(Canvas canvas) {
                super.dispatchDraw(canvas);
                if (!drawn) {
                    drawn = true;
                    main.postDelayed(once, 50);  // a few frames: the cover is composed before Kodi
                }
            }

            @Override
            public boolean dispatchKeyEvent(KeyEvent event) {
                return true;  // presses during the start would otherwise drive Kodi's menus unseen
            }
        };
        fillSplash(view);
        WindowManager.LayoutParams params = new WindowManager.LayoutParams(-1, -1,
                Build.VERSION.SDK_INT >= 26 ? WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
                        : WindowManager.LayoutParams.TYPE_PHONE,
                WindowManager.LayoutParams.FLAG_FULLSCREEN
                        | WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
                PixelFormat.TRANSLUCENT);  // translucent so that the fade shows the add-on below
        try {
            windows().addView(view, params);
        } catch (RuntimeException e) {  // access withdrawn meanwhile, or refused by the system
            Log.w(TAG, "Overlay refused", e);
            return false;
        }
        cover = view;
        registerReceiver(homeKey, new IntentFilter(Intent.ACTION_CLOSE_SYSTEM_DIALOGS));
        watchingHome = true;
        main.postDelayed(once, 1000);  // never wait for a frame that does not come
        return true;
    }

    private void hideCover() {
        View view = cover;
        cover = null;
        if (watchingHome) {
            watchingHome = false;
            unregisterReceiver(homeKey);
        }
        if (view != null) removeCover(view);
    }

    private void removeCover(View view) {
        try {
            windows().removeViewImmediate(view);
        } catch (IllegalArgumentException e) {
            Log.d(TAG, "Cover already removed", e);
        }
    }

    /** The add-on window is on screen under the cover: fade the cover out, then close this screen. */
    private void revealAndFinish() {
        View view = cover;
        cover = null;
        if (watchingHome) {
            watchingHome = false;
            unregisterReceiver(homeKey);
        }
        if (view == null) {
            finish();
            return;
        }
        view.animate().alpha(0f).setDuration(FADE_MS).withEndAction(() -> {
            removeCover(view);
            finish();
        });
    }

    private void beginLaunch() {
        if (launching) return;
        launching = true;
        cancelled = false;
        hideCover();  // a cover left by a failed start
        errorPanel.setVisibility(View.GONE);
        progress.setVisibility(View.VISIBLE);
        // Kodi is opened only under a drawn cover: its splash and MegaNexus never reach the screen.
        if (!showCover(this::startKodi)) startKodi();
    }

    private void startKodi() {
        if (cancelled) return;
        try {
            launchKodi();
        } catch (Exception e) {
            launching = false;
            hideCover();
            showError("Kodi est introuvable. Installe Kodi et l'extension IPTV4FREE.");
            return;
        }
        new Thread(this::bridge, "iptv4free-kodi-bridge").start();
    }

    private void bridge() {
        final long until = SystemClock.elapsedRealtime() + DEADLINE_MS;
        boolean connected = false;
        while (SystemClock.elapsedRealtime() < until && !isFinishing() && !cancelled) {
            try {
                JSONObject ping = call("JSONRPC.Ping", new JSONObject(), 1);
                if (!"pong".equalsIgnoreCase(ping.optString("result"))) {
                    throw new IOException("Kodi JSON-RPC n'est pas encore prêt");
                }
                connected = true;
                JSONObject addonArgs = new JSONObject();
                addonArgs.put("addonid", ADDON);
                addonArgs.put("properties", new JSONArray().put("enabled"));
                JSONObject details = call("Addons.GetAddonDetails", addonArgs, 2);
                // Kodi also returns the details of a disabled add-on, then refuses to run it.
                JSONObject found = details.optJSONObject("result");
                found = found == null ? null : found.optJSONObject("addon");
                if (found == null || !found.optBoolean("enabled")) {
                    fail("L'extension IPTV4FREE n'est pas installée ou activée dans Kodi.");
                    return;
                }
                if (cancelled) return;
                JSONObject launchArgs = new JSONObject();
                launchArgs.put("addonid", ADDON);
                launchArgs.put("wait", false);
                // Tells the add-on to return to the TV home, not Kodi's menus, when it is closed.
                launchArgs.put("params", new JSONArray().put("android"));
                JSONObject execution = call("Addons.ExecuteAddon", launchArgs, 3);
                if (execution.has("error")) {
                    fail("Kodi refuse l'ouverture d'IPTV4FREE : " + execution.optJSONObject("error"));
                    return;
                }
                if (cover != null && !waitForWindow()) {
                    if (cancelled) return;
                    Log.w(TAG, "IPTV4FREE window not seen in time: cover removed anyway");
                }
                runOnUiThread(() -> {
                    launching = false;
                    revealAndFinish();
                });
                return;
            } catch (IOException | JSONException e) {
                Log.d(TAG, "Waiting for Kodi JSON-RPC", e);
                SystemClock.sleep(700);
            }
        }
        if (cancelled || isFinishing()) return;
        if (connected) {
            fail("Impossible de lancer l'extension. Vérifie Kodi et IPTV4FREE.");
        } else {
            fail("Kodi n'autorise pas le contrôle TCP local (port 9090). Dans Kodi : "
                    + "Paramètres > Services > Contrôle > Autoriser le contrôle par "
                    + "des applications sur ce système, puis réessaie.");
        }
    }

    /**
     * True once the add-on window is the active Kodi window: its loading view (the same logo on
     * black) or its channel list. Without the loading view, wait 3 polls so Kodi has drawn it.
     */
    private boolean waitForWindow() {
        final long until = SystemClock.elapsedRealtime() + WINDOW_DEADLINE_MS;
        int seen = 0;
        while (SystemClock.elapsedRealtime() < until && !isFinishing() && !cancelled) {
            try {
                JSONObject labels = new JSONObject().put("labels", new JSONArray().put(WINDOW_ID));
                String id = call("XBMC.GetInfoLabels", labels, 4)
                        .getJSONObject("result").optString(WINDOW_ID);
                if (!id.isEmpty()) {
                    String active = "Window.IsActive(" + id + ")";
                    String loading = "String.IsEqual(Window(" + id + ").Property(Loading),true)";
                    JSONObject booleans = new JSONObject().put("booleans",
                            new JSONArray().put(active).put(loading));
                    JSONObject state = call("XBMC.GetInfoBooleans", booleans, 5)
                            .getJSONObject("result");
                    seen = state.optBoolean(active) ? seen + 1 : 0;
                    if (seen > 0 && (state.optBoolean(loading) || seen >= 3)) return true;
                }
            } catch (IOException | JSONException e) {
                Log.d(TAG, "Waiting for the IPTV4FREE window", e);
            }
            SystemClock.sleep(150);
        }
        return false;
    }

    private void fail(String message) {
        runOnUiThread(() -> {
            launching = false;
            showError(message);
            // Kodi was opened on top of this screen: bring the diagnostic back in front of it.
            // Without the cover's overlay access, Android may refuse that after the 30 s wait:
            // the toast still shows.
            Toast.makeText(this, message, Toast.LENGTH_LONG).show();
            startActivity(new Intent(this, MainActivity.class).putExtra(SHOW_ERROR, true)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));
            View shown = cover;  // diagnostic in front first, then the cover goes: Kodi never flashes
            main.postDelayed(() -> {
                if (cover == shown) hideCover();
            }, 400);
        });
    }

    private void showError(String message) {
        status.setText(message);
        progress.setVisibility(View.GONE);
        errorPanel.setVisibility(View.VISIBLE);
        retry.requestFocus();
    }


    /**
     * Kodi's raw TCP JSON-RPC can send unsolicited notifications before the reply.
     * Read complete, quoted-string-aware JSON objects and match request id.
     */
    private JSONObject call(String method, JSONObject params, int id)
            throws IOException, JSONException {
        JSONObject request = new JSONObject();
        request.put("jsonrpc", "2.0");
        request.put("id", id);
        request.put("method", method);
        request.put("params", params);

        try (Socket socket = new Socket()) {
            socket.connect(new InetSocketAddress("127.0.0.1", PORT), 900);
            socket.setSoTimeout(1400);
            OutputStream out = socket.getOutputStream();
            out.write(request.toString().getBytes(StandardCharsets.UTF_8));
            out.flush();

            InputStream in = socket.getInputStream();
            ByteArrayOutputStream received = new ByteArrayOutputStream();
            byte[] buffer = new byte[4096];
            while (received.size() < MAX_REPLY) {
                int count = in.read(buffer);
                if (count < 0) break;
                received.write(buffer, 0, count);
                JSONObject reply = findResponse(received.toString("UTF-8"), id);
                if (reply != null) return reply;
            }
        }
        throw new IOException("Pas de réponse JSON-RPC pour " + method);
    }

    static JSONObject findResponse(String input, int expectedId) throws JSONException {
        int depth = 0, start = -1;
        boolean quoted = false, escaped = false;
        for (int i = 0; i < input.length(); i++) {
            char c = input.charAt(i);
            if (quoted) {
                if (escaped) escaped = false;
                else if (c == '\\') escaped = true;
                else if (c == '"') quoted = false;
            } else if (c == '"') {
                quoted = true;
            } else if (c == '{') {
                if (depth == 0) start = i;
                depth++;
            } else if (c == '}' && depth > 0) {
                depth--;
                if (depth == 0 && start >= 0) {
                    JSONObject object = new JSONObject(input.substring(start, i + 1));
                    if (object.optInt("id", -1) == expectedId) return object;
                    start = -1;
                }
            }
        }
        return null;
    }
}

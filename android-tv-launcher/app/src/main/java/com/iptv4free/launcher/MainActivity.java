package com.iptv4free.launcher;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.graphics.Color;
import android.os.Bundle;
import android.os.SystemClock;
import android.util.Log;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

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
 * Does not replace Kodi, edit its files, change its skin, or touch other applications.
 */
public final class MainActivity extends Activity {
    private static final String TAG = "IPTV4FREE-Launcher";
    private static final String KODI = "org.xbmc.kodi";
    private static final String ADDON = "script.iptv4free";
    private static final int PORT = 9090;
    private static final long DEADLINE_MS = 30000;
    private static final int MAX_REPLY = 65536;

    private TextView status;
    private Button retry;
    private Button openKodi;
    private volatile boolean launching;

    @Override
    protected void onCreate(Bundle saved) {
        super.onCreate(saved);
        createScreen();
        beginLaunch();
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        if (!launching) beginLaunch();
    }

    private void createScreen() {
        getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER);
        root.setPadding(44, 30, 44, 30);
        root.setBackgroundColor(Color.rgb(5, 8, 23));

        ImageView logo = new ImageView(this);
        logo.setImageResource(R.drawable.iptv4free_launcher_icon);
        logo.setAdjustViewBounds(true);
        logo.setScaleType(ImageView.ScaleType.FIT_CENTER);
        root.addView(logo, new LinearLayout.LayoutParams(360, 245));

        status = new TextView(this);
        status.setTextColor(Color.WHITE);
        status.setTextSize(19);
        status.setGravity(Gravity.CENTER);
        status.setText("IPTV4FREE");
        LinearLayout.LayoutParams textParams = new LinearLayout.LayoutParams(-1, -2);
        textParams.topMargin = 18;
        root.addView(status, textParams);

        retry = new Button(this);
        retry.setText("Réessayer");
        retry.setOnClickListener(v -> beginLaunch());
        retry.setVisibility(View.GONE);
        LinearLayout.LayoutParams buttonParams = new LinearLayout.LayoutParams(250, -2);
        buttonParams.topMargin = 22;
        buttonParams.gravity = Gravity.CENTER;
        root.addView(retry, buttonParams);

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
        openKodi.setVisibility(View.GONE);
        LinearLayout.LayoutParams otherParams = new LinearLayout.LayoutParams(300, -2);
        otherParams.topMargin = 10;
        otherParams.gravity = Gravity.CENTER;
        root.addView(openKodi, otherParams);

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

    private void beginLaunch() {
        if (launching) return;
        launching = true;
        retry.setVisibility(View.GONE);
        openKodi.setVisibility(View.GONE);
        status.setText("Ouverture d'IPTV4FREE…");
        try {
            launchKodi();
        } catch (Exception e) {
            launching = false;
            showError("Kodi est introuvable. Installe Kodi et l'extension IPTV4FREE.");
            return;
        }

        Thread worker = new Thread(() -> {
            final long until = SystemClock.elapsedRealtime() + DEADLINE_MS;
            boolean connected = false;
            while (SystemClock.elapsedRealtime() < until && !isFinishing()) {
                try {
                    JSONObject ping = call("JSONRPC.Ping", new JSONObject(), 1);
                    if (!"pong".equalsIgnoreCase(ping.optString("result"))) {
                        throw new IOException("Kodi JSON-RPC n'est pas encore prêt");
                    }
                    connected = true;
                    JSONObject addonArgs = new JSONObject();
                    addonArgs.put("addonid", ADDON);
                    JSONObject details = call("Addons.GetAddonDetails", addonArgs, 2);
                    if (details.has("error")) {
                        fail("L'extension IPTV4FREE n'est pas installée ou activée dans Kodi.");
                        return;
                    }
                    JSONObject launchArgs = new JSONObject();
                    launchArgs.put("addonid", ADDON);
                    launchArgs.put("wait", false);
                    JSONObject execution = call("Addons.ExecuteAddon", launchArgs, 3);
                    if (execution.has("error")) {
                        fail("Kodi refuse l'ouverture d'IPTV4FREE : " + execution.optJSONObject("error"));
                        return;
                    }
                    runOnUiThread(() -> {
                        launching = false;
                        finish();
                    });
                    return;
                } catch (IOException | JSONException e) {
                    Log.d(TAG, "Waiting for Kodi JSON-RPC", e);
                    SystemClock.sleep(700);
                }
            }
            if (connected) {
                fail("Impossible de lancer l'extension. Vérifie Kodi et IPTV4FREE.");
            } else {
                fail("Kodi n'autorise pas le contrôle TCP local (port 9090). Dans Kodi : "
                        + "Paramètres > Services > Contrôle > Autoriser le contrôle par "
                        + "des applications sur ce système, puis réessaie.");
            }
        }, "iptv4free-kodi-bridge");
        worker.start();
    }

    private void fail(String message) {
        runOnUiThread(() -> {
            launching = false;
            showError(message);
        });
    }

    private void showError(String message) {
        status.setText(message);
        retry.setVisibility(View.VISIBLE);
        openKodi.setVisibility(View.VISIBLE);
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

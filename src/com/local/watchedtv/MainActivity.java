package com.local.watchedtv;

import android.app.Activity;
import android.content.Intent;
import android.content.pm.ApplicationInfo;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.CookieManager;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;

/** Opens https://watched.cx full screen; Back = previous page, then the TV home screen. */
public class MainActivity extends Activity {
    static final String HOME = "https://watched.cx";
    FrameLayout root;
    WebView web;
    View fullscreen;
    WebChromeClient.CustomViewCallback fullscreenDone;
    WebChromeClient chrome;

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        root = new FrameLayout(this);
        root.setBackgroundColor(Color.BLACK);
        web = new WebView(this);
        web.setBackgroundColor(Color.BLACK);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, true); // players embedded in iframes
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
                String scheme = r.getUrl().getScheme();
                if ("http".equals(scheme) || "https".equals(scheme)) return false;
                return true; // intent:, market:... are ignored: stay on the site
            }
        });
        web.setWebChromeClient(chrome = new WebChromeClient() {
            @Override public void onPermissionRequest(PermissionRequest r) { // Widevine DRM, as in Chrome; nothing else (microphone, camera) is granted
                for (String res : r.getResources())
                    if (PermissionRequest.RESOURCE_PROTECTED_MEDIA_ID.equals(res)) { r.grant(new String[]{res}); return; }
                r.deny();
            }
            @Override public void onShowCustomView(View v, CustomViewCallback cb) {
                if (fullscreen != null) { cb.onCustomViewHidden(); return; }
                fullscreen = v; fullscreenDone = cb;
                root.addView(v, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
                web.setVisibility(View.GONE);
                v.requestFocus();
            }
            @Override public void onHideCustomView() {
                if (fullscreen == null) return;
                root.removeView(fullscreen);
                fullscreen = null;
                web.setVisibility(View.VISIBLE);
                web.requestFocus();
                fullscreenDone.onCustomViewHidden();
            }
        });
        root.addView(web);
        setContentView(root);
        if (b != null) web.restoreState(b);
        else {
            Uri u = testUrl(getIntent());
            web.loadUrl(u != null ? u.toString() : HOME);
        }
        web.requestFocus();
    }

    /** URL passed with "am start -d <url>": honoured by DEBUG=1 builds only, because any installed app can send this intent. */
    Uri testUrl(Intent i) {
        boolean debuggable = (getApplicationInfo().flags & ApplicationInfo.FLAG_DEBUGGABLE) != 0;
        return debuggable ? i.getData() : null;
    }

    @Override public void onBackPressed() {
        if (fullscreen != null) chrome.onHideCustomView();
        else if (web.canGoBack()) web.goBack();
        else super.onBackPressed();
    }

    /** Remote Play/Pause keys: the WebView does not apply them by itself. */
    @Override public boolean dispatchKeyEvent(KeyEvent e) {
        int k = e.getKeyCode();
        if (k != KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE && k != KeyEvent.KEYCODE_MEDIA_PLAY && k != KeyEvent.KEYCODE_MEDIA_PAUSE)
            return super.dispatchKeyEvent(e);
        if (e.getAction() == KeyEvent.ACTION_UP) {
            String op = k == KeyEvent.KEYCODE_MEDIA_PLAY ? "v.play()" : k == KeyEvent.KEYCODE_MEDIA_PAUSE ? "v.pause()" : "v.paused?v.play():v.pause()";
            // shortcut: first loaded video of the main page only, a video inside a third-party iframe is not reached; upgrade if the site moves its player into an iframe
            web.evaluateJavascript("(function(){var v=[].filter.call(document.querySelectorAll('video'),function(x){return x.readyState>0})[0];if(v)" + op + "})()", null);
        }
        return true; // consumed: avoids a double toggle if the site also handles the key
    }

    @Override protected void onNewIntent(Intent i) {
        super.onNewIntent(i);
        Uri u = testUrl(i);
        if (u != null) web.loadUrl(u.toString());
    }

    @Override protected void onPause() { super.onPause(); web.onPause(); CookieManager.getInstance().flush(); } // stops the sound when leaving
    @Override protected void onResume() { super.onResume(); web.onResume(); }
    @Override protected void onSaveInstanceState(Bundle b) { super.onSaveInstanceState(b); web.saveState(b); }
    @Override protected void onDestroy() { root.removeAllViews(); web.destroy(); super.onDestroy(); }
}

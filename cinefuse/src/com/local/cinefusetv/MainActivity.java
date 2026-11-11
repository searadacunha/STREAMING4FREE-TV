package com.local.cinefusetv;

import android.app.Activity;
import android.content.Intent;
import android.content.pm.ApplicationInfo;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.os.SystemClock;
import android.view.InputDevice;
import android.view.KeyEvent;
import android.view.MotionEvent;
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
import android.widget.Toast;

/** Opens https://cinefuse.cc full screen; Back = previous page, then the TV home screen. */
public class MainActivity extends Activity {
    static final String HOME = "https://cinefuse.cc"; // reference address: the site redirects it to its current domain
    /** The site's TV stylesheet sets position:relative on every focused element, so the player (fixed inset-0)
     * collapses to 0 px high as soon as the remote focuses it: the video plays but is invisible. Keep the site's own position. */
    static final String TV_CSS_FIX = "(function(){if(document.getElementById('cinefuse-tv-fix'))return;"
        + "var s=document.createElement('style');s.id='cinefuse-tv-fix';s.textContent="
        + "'html.is-tv .fixed:focus-visible{position:fixed!important}html.is-tv .absolute:focus-visible{position:absolute!important}"
        + "html.is-tv .sticky:focus-visible{position:sticky!important}';(document.head||document.documentElement).appendChild(s)})()";
    FrameLayout root;
    WebView web;
    View fullscreen;
    WebChromeClient.CustomViewCallback fullscreenDone;
    WebChromeClient chrome;
    View cursor;
    KeyEvent okDown; // OK pressed, not yet known to be short or long
    boolean failed; // the main page failed to load

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
        // the site serves its TV mode (TV pre-roll instead of three ad popups) only to user agents naming a TV; WebView's says "Mobile"
        s.setUserAgentString(s.getUserAgentString() + " Android TV");
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, true); // players embedded in iframes
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
                Uri u = r.getUrl();
                String scheme = u.getScheme();
                if (!"http".equals(scheme) && !"https".equals(scheme)) return true; // intent:, market:... are ignored: stay on the site
                if (!r.isForMainFrame() || isSite(u.getHost())) return false; // video players in iframes keep their own hosts
                Toast.makeText(MainActivity.this, "Lien externe bloqué : " + u.getHost(), Toast.LENGTH_SHORT).show(); // ads, popups
                return true;
            }
            @Override public void onPageStarted(WebView v, String url, android.graphics.Bitmap icon) { failed = false; }
            @Override public void onReceivedError(WebView v, WebResourceRequest r, android.webkit.WebResourceError err) {
                if (r.isForMainFrame()) failed = true; // TV offline: Chromium's error page, retried by onResume
            }
            @Override public void onPageFinished(WebView v, String url) {
                if (isSite(Uri.parse(url).getHost())) v.evaluateJavascript(TV_CSS_FIX, null);
            }
            @Override public boolean onRenderProcessGone(WebView v, android.webkit.RenderProcessGoneDetail d) {
                return restart(v);
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
        cursor = new View(this); // virtual pointer for what the D-pad cannot reach: search results, player buttons
        GradientDrawable dot = new GradientDrawable();
        dot.setShape(GradientDrawable.OVAL);
        dot.setColor(Color.WHITE);
        dot.setStroke(px(3), Color.rgb(30, 120, 255));
        cursor.setBackground(dot);
        cursor.setVisibility(View.INVISIBLE); // laid out, so its size is known
        root.addView(cursor, new FrameLayout.LayoutParams(px(22), px(22)));
        setContentView(root);
        if (b == null || web.restoreState(b) == null) { // restoreState returns null when nothing could be restored: black page otherwise
            Uri u = b == null ? testUrl(getIntent()) : null;
            web.loadUrl(u != null ? u.toString() : HOME);
        }
        web.requestFocus();
    }

    /** The page's renderer crashed, or the TV killed it to free memory: without this Android closes the app.
     * The dead WebView is only detached here (it is destroyed with this activity) and the app starts again on its home page. */
    boolean restart(WebView dead) {
        root.removeView(dead);
        startActivity(new Intent(this, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK));
        return true;
    }

    /** URL passed with "am start -d <url>": honoured by DEBUG=1 builds only, because any installed app can send this intent. */
    Uri testUrl(Intent i) {
        boolean debuggable = (getApplicationInfo().flags & ApplicationInfo.FLAG_DEBUGGABLE) != 0;
        return debuggable ? i.getData() : null;
    }

    /** cinefuse.<any TLD> and its subdomains: the site moves to a new TLD every few months (cc, icu, mom, sbs in Nov 2026).
     * shortcut: trusts any cinefuse.* domain the site links or redirects to; pin the list if a look-alike domain ever shows up. */
    public static boolean isSite(String host) {
        if (host == null) return false;
        String[] l = host.toLowerCase(java.util.Locale.ROOT).split("\\.");
        return l.length >= 2 && "cinefuse".equals(l[l.length - 2]);
    }

    @Override public void onBackPressed() {
        if (cursor.getVisibility() == View.VISIBLE) showCursor(false);
        else if (fullscreen != null) chrome.onHideCustomView();
        else if (web.canGoBack()) web.goBack();
        else super.onBackPressed();
    }

    /** Long press on OK shows or hides the cursor; while it is shown, arrows move it and OK taps under it.
     * Remote Play/Pause keys: the WebView does not apply them by itself. */
    @Override public boolean dispatchKeyEvent(KeyEvent e) {
        int k = e.getKeyCode();
        boolean down = e.getAction() == KeyEvent.ACTION_DOWN, pointing = cursor.getVisibility() == View.VISIBLE;
        if (k == KeyEvent.KEYCODE_DPAD_CENTER || k == KeyEvent.KEYCODE_ENTER) {
            if (down) { // a short press is held back until release: only then is it known not to be a long press
                if (e.getRepeatCount() == 0) okDown = e;
                else if (okDown != null) { okDown = null; showCursor(!pointing); }
                return true;
            }
            if (okDown == null) return true; // release of a long press
            KeyEvent press = okDown;
            okDown = null;
            if (pointing) tap();
            else { super.dispatchKeyEvent(press); super.dispatchKeyEvent(e); }
            return true;
        }
        if (pointing && (k == KeyEvent.KEYCODE_DPAD_UP || k == KeyEvent.KEYCODE_DPAD_DOWN || k == KeyEvent.KEYCODE_DPAD_LEFT || k == KeyEvent.KEYCODE_DPAD_RIGHT)) {
            int st = px(e.getRepeatCount() > 0 ? 24 : 12); // faster while held
            if (down) move(k == KeyEvent.KEYCODE_DPAD_LEFT ? -st : k == KeyEvent.KEYCODE_DPAD_RIGHT ? st : 0,
                           k == KeyEvent.KEYCODE_DPAD_UP ? -st : k == KeyEvent.KEYCODE_DPAD_DOWN ? st : 0);
            return true;
        }
        if (k != KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE && k != KeyEvent.KEYCODE_MEDIA_PLAY && k != KeyEvent.KEYCODE_MEDIA_PAUSE)
            return super.dispatchKeyEvent(e);
        if (e.getAction() == KeyEvent.ACTION_UP) {
            String op = k == KeyEvent.KEYCODE_MEDIA_PLAY ? "v.play()" : k == KeyEvent.KEYCODE_MEDIA_PAUSE ? "v.pause()" : "v.paused?v.play():v.pause()";
            // shortcut: first loaded video of the main page only, a video inside a third-party iframe is not reached; upgrade if the site moves its player into an iframe
            web.evaluateJavascript("(function(){var v=[].filter.call(document.querySelectorAll('video'),function(x){return x.readyState>0})[0];if(v)" + op + "})()", null);
        }
        return true; // consumed: avoids a double toggle if the site also handles the key
    }

    void showCursor(boolean on) {
        if (on && cursor.getTranslationX() == 0 && cursor.getTranslationY() == 0) { // first time: centre of the screen
            cursor.setTranslationX((root.getWidth() - cursor.getWidth()) / 2f);
            cursor.setTranslationY((root.getHeight() - cursor.getHeight()) / 2f);
        }
        cursor.bringToFront(); // above the fullscreen video view too
        cursor.setVisibility(on ? View.VISIBLE : View.INVISIBLE);
        Toast.makeText(this, on ? "Curseur : flèches pour le déplacer, OK pour cliquer, Retour pour le masquer" : "Curseur masqué",
            Toast.LENGTH_SHORT).show();
    }

    void move(int dx, int dy) {
        float x = cursor.getTranslationX() + dx, y = cursor.getTranslationY() + dy;
        float cx = Math.max(0, Math.min(root.getWidth() - cursor.getWidth(), x));
        float cy = Math.max(0, Math.min(root.getHeight() - cursor.getHeight(), y));
        cursor.setTranslationX(cx);
        cursor.setTranslationY(cy);
        mouse(MotionEvent.ACTION_HOVER_MOVE, 0, 0); // the page sees a mouse move: the player shows its controls, hover styles apply
        if (cx != x || cy != y) mouse(MotionEvent.ACTION_SCROLL, Math.signum(x - cx), -Math.signum(y - cy)); // pushed against an edge: scroll what is under it
    }

    /** Touch tap at the cursor's centre; it reaches iframes too, as a finger would. The cursor view itself is not clickable. */
    void tap() {
        long t = SystemClock.uptimeMillis();
        float x = cursor.getTranslationX() + cursor.getWidth() / 2f, y = cursor.getTranslationY() + cursor.getHeight() / 2f;
        for (int a : new int[]{MotionEvent.ACTION_DOWN, MotionEvent.ACTION_UP}) {
            MotionEvent m = MotionEvent.obtain(t, a == MotionEvent.ACTION_DOWN ? t : t + 50, a, x, y, 0);
            m.setSource(InputDevice.SOURCE_TOUCHSCREEN);
            root.dispatchTouchEvent(m);
            m.recycle();
        }
    }

    /** Mouse event at the cursor: hover, or wheel (scrolls the page or the inner list under it). */
    void mouse(int action, float h, float v) {
        MotionEvent.PointerProperties[] pp = {new MotionEvent.PointerProperties()};
        pp[0].toolType = MotionEvent.TOOL_TYPE_MOUSE;
        MotionEvent.PointerCoords[] pc = {new MotionEvent.PointerCoords()};
        pc[0].x = cursor.getTranslationX() + cursor.getWidth() / 2f;
        pc[0].y = cursor.getTranslationY() + cursor.getHeight() / 2f;
        pc[0].setAxisValue(MotionEvent.AXIS_HSCROLL, h);
        pc[0].setAxisValue(MotionEvent.AXIS_VSCROLL, v);
        long t = SystemClock.uptimeMillis();
        MotionEvent m = MotionEvent.obtain(t, t, action, 1, pp, pc, 0, 0, 1, 1, 0, 0, InputDevice.SOURCE_MOUSE, 0);
        root.dispatchGenericMotionEvent(m);
        m.recycle();
    }

    int px(int dp) { return Math.round(dp * getResources().getDisplayMetrics().density); }

    @Override protected void onNewIntent(Intent i) {
        super.onNewIntent(i);
        Uri u = testUrl(i);
        if (u != null) { failed = false; web.loadUrl(u.toString()); } // onResume follows: no retry of the old page
    }

    @Override protected void onPause() { super.onPause(); web.onPause(); CookieManager.getInstance().flush(); } // stops the sound when leaving
    @Override protected void onResume() { super.onResume(); web.onResume(); if (failed) web.reload(); } // reopening never shows a stale error page
    @Override protected void onSaveInstanceState(Bundle b) { super.onSaveInstanceState(b); web.saveState(b); }
    @Override protected void onDestroy() { root.removeAllViews(); web.destroy(); super.onDestroy(); }
}

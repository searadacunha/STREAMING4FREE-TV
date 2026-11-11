package com.local.streaming4free

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.KeyEvent
import android.view.View
import android.view.WindowManager
import android.widget.TextView
import androidx.annotation.OptIn
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.MimeTypes
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.datasource.DefaultDataSource
import androidx.media3.datasource.DefaultHttpDataSource
import androidx.media3.datasource.HttpDataSource
import androidx.media3.exoplayer.upstream.LoadErrorHandlingPolicy
import androidx.media3.exoplayer.DefaultRenderersFactory
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import androidx.media3.exoplayer.upstream.DefaultLoadErrorHandlingPolicy
import androidx.media3.ui.PlayerView
import java.util.Locale

/**
 * Full-screen player for one stream (HLS, DASH, MPEG-TS, MP4). Hardware decoders first, quality chosen from the
 * bandwidth, audio and subtitle tracks in the player's settings. Back returns to the hub at once.
 * No browser user agent, no Referer, no DRM: a stream that needs them is reported as unavailable.
 */
@OptIn(UnstableApi::class)
class PlayerActivity : Activity() {
    companion object {
        fun intent(c: Context, ch: Channel): Intent = Intent(c, PlayerActivity::class.java)
            .putExtra("n", ch.title).putExtra("u", ch.url).putExtra("l", ch.logo).putExtra("g", ch.group)
            .putExtra("s", ch.source).putExtra("id", ch.id).putExtra("q", ch.quality)
        private const val MAX_RETRIES = 3

        /** A playlist refused (403) or missing (404) fails at once; network errors and segments keep their 6 tries. */
        private val LOAD_ERRORS = object : DefaultLoadErrorHandlingPolicy(6) {
            override fun getRetryDelayMsFor(info: LoadErrorHandlingPolicy.LoadErrorInfo): Long {
                val code = (info.exception as? HttpDataSource.InvalidResponseCodeException)?.responseCode
                return if (code != null && code in 400..499 && info.mediaLoadData.dataType == C.DATA_TYPE_MANIFEST) C.TIME_UNSET
                    else super.getRetryDelayMsFor(info)
            }
        }
        private val TRANSIENT = setOf(PlaybackException.ERROR_CODE_IO_UNSPECIFIED, PlaybackException.ERROR_CODE_IO_NETWORK_CONNECTION_FAILED,
            PlaybackException.ERROR_CODE_IO_NETWORK_CONNECTION_TIMEOUT, PlaybackException.ERROR_CODE_TIMEOUT)
    }

    private lateinit var channel: Channel
    private lateinit var view: PlayerView
    private lateinit var message: TextView
    private var player: ExoPlayer? = null
    private var mime: String? = null // forced to HLS when the URL does not tell the format
    private var retries = 0
    private var started = false // has played at least once
    private var failed = false
    private val handler = Handler(Looper.getMainLooper())

    override fun attachBaseContext(base: Context) = super.attachBaseContext(Store.localized(base))

    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        setContentView(R.layout.player)
        view = findViewById(R.id.player_view)
        message = findViewById(R.id.message)
        val i = intent
        channel = Channel(i.getStringExtra("n").orEmpty(), i.getStringExtra("u").orEmpty(), i.getStringExtra("l").orEmpty(),
            i.getStringExtra("g").orEmpty(), i.getStringExtra("s").orEmpty(), i.getStringExtra("id").orEmpty(), i.getStringExtra("q").orEmpty())
        view.setShowBuffering(PlayerView.SHOW_BUFFERING_ALWAYS)
        view.setShowSubtitleButton(true)
        view.controllerAutoShow = false
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
    }

    override fun onStart() {
        super.onStart()
        play()
    }

    override fun onStop() {
        release()
        super.onStop()
    }

    private fun play() {
        failed = false
        show(getString(R.string.opening, channel.title))
        val http = DefaultHttpDataSource.Factory()
            .setAllowCrossProtocolRedirects(true) // many lists still point to http:// that redirects to https://
            .setConnectTimeoutMs(10_000).setReadTimeoutMs(15_000)
        val sources = DefaultMediaSourceFactory(DefaultDataSource.Factory(this, http))
            .setLoadErrorHandlingPolicy(LOAD_ERRORS)
        val p = ExoPlayer.Builder(this, DefaultRenderersFactory(this).setEnableDecoderFallback(true))
            .setMediaSourceFactory(sources).build()
        val langs = listOf(Store.lang, Locale.getDefault().language, "pt", "fr").filter { it.isNotEmpty() }
        p.trackSelectionParameters = p.trackSelectionParameters.buildUpon()
            .setPreferredAudioLanguages(*langs.distinct().toTypedArray())
            .apply { if (Store.maxHeight > 0) setMaxVideoSize(Int.MAX_VALUE, Store.maxHeight) }
            .build()
        p.addListener(listener)
        view.player = p
        player = p
        val item = MediaItem.Builder().setUri(channel.url).setMimeType(mime).build()
        val resume = Store.position(channel.url)
        if (resume > 0) p.setMediaItem(item, resume) else p.setMediaItem(item)
        p.prepare()
        p.playWhenReady = true
    }

    private fun release() {
        handler.removeCallbacksAndMessages(null)
        val p = player ?: return
        // films and replays resume where they stopped; live channels have no position
        if (started && !p.isCurrentMediaItemLive && p.duration != C.TIME_UNSET && p.duration > 60_000) {
            val pos = p.currentPosition
            Store.setPosition(channel.url, if (pos > 10_000 && pos < p.duration - 60_000) pos else 0)
        }
        p.removeListener(listener)
        p.release()
        player = null
        view.player = null
    }

    private val listener = object : Player.Listener {
        override fun onPlaybackStateChanged(state: Int) {
            if (state == Player.STATE_READY) {
                message.visibility = View.GONE
                retries = 0
                if (!started) {
                    started = true
                    Store.addHistory(channel)
                    Store.markDead(channel.url, false)
                }
            } else if (state == Player.STATE_ENDED) {
                Store.setPosition(channel.url, 0)
                finish()
            }
        }

        override fun onPlayerError(e: PlaybackException) {
            val p = player ?: return
            when {
                e.errorCode == PlaybackException.ERROR_CODE_BEHIND_LIVE_WINDOW -> { // fell behind a live stream: jump back to live
                    p.seekToDefaultPosition()
                    p.prepare()
                }
                e.errorCode == PlaybackException.ERROR_CODE_PARSING_CONTAINER_UNSUPPORTED && mime == null && !started -> {
                    mime = MimeTypes.APPLICATION_M3U8 // ".php", "/live" and the like are nearly always HLS
                    handler.post { release(); play() } // not from inside the player's own callback
                }
                e.errorCode in TRANSIENT && retries < MAX_RETRIES -> {
                    retries++
                    show(getString(R.string.reconnecting, retries, MAX_RETRIES))
                    handler.postDelayed({ player?.prepare() }, 3_000L * retries)
                }
                else -> {
                    failed = true
                    if (!started) Store.markDead(channel.url, true)
                    val http = generateSequence<Throwable>(e) { it.cause }.filterIsInstance<HttpDataSource.InvalidResponseCodeException>().firstOrNull()
                    show(getString(R.string.play_error, channel.title, http?.let { "HTTP ${it.responseCode}" } ?: e.errorCodeName))
                }
            }
        }
    }

    private fun show(text: String) {
        message.text = text
        message.visibility = View.VISIBLE
    }

    /** The player view gets the remote's arrows, OK and media keys even when nothing is focused; OK retries after an error. */
    override fun dispatchKeyEvent(e: KeyEvent): Boolean {
        if (failed && e.keyCode == KeyEvent.KEYCODE_DPAD_CENTER) {
            if (e.action == KeyEvent.ACTION_UP) {
                retries = 0
                release()
                play()
            }
            return true
        }
        return view.dispatchKeyEvent(e) || super.dispatchKeyEvent(e)
    }
}

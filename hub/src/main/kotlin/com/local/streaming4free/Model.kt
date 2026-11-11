package com.local.streaming4free

import android.content.Intent
import android.content.pm.PackageManager

/** The hub's sections, in the order of the left menu. */
enum class Cat(val title: Int) {
    HOME(R.string.cat_home), MOVIES(R.string.cat_movies), SERIES(R.string.cat_series), LIVE(R.string.cat_live),
    SPORT(R.string.cat_sport), DOCS(R.string.cat_docs), YOUTUBE(R.string.cat_youtube), IPTV(R.string.cat_iptv),
    FAVORITES(R.string.cat_favorites), CONTINUE(R.string.cat_continue), SETTINGS(R.string.cat_settings),
}

/** Everything a card can show. */
sealed class Item {
    abstract val key: String
    abstract val title: String
}

/** One stream, from the checked catalog or from a public playlist. */
data class Channel(
    override val title: String,
    val url: String,
    val logo: String = "",
    val group: String = "",
    val source: String = "",
    val id: String = "", // tvg-id
    val quality: String = "", // what the probe read in the playlist, catalog only
) : Item() {
    override val key get() = url
    /** A YouTube page, not a stream: opened by SmartTube or the YouTube app. */
    val isYouTube get() = YOUTUBE.containsMatchIn(url)

    private companion object {
        val YOUTUBE = Regex("^https?://([a-z]+\\.)?(youtube\\.com|youtu\\.be)/")
    }
}

/** What using a service costs: shown on its card, so nothing paid or blocked passes for free. */
enum class Terms(val label: Int) {
    FREE(R.string.terms_free), ACCOUNT(R.string.terms_account), FREEMIUM(R.string.terms_freemium),
    FRANCE(R.string.terms_france), PAID(R.string.terms_paid), SITE(R.string.terms_site),
}

/** An app the hub opens. It never reads that app's data: Android gives no access to it. */
data class App(
    val id: String,
    val packages: List<String>, // first installed one wins
    override val title: String,
    val desc: Int,
    val terms: Terms,
    val cats: Set<Cat>,
    val onPlayStore: Boolean = true,
) : Item() {
    override val key get() = "app:$id"

    fun launchIntent(pm: PackageManager): Intent? =
        packages.firstNotNullOfOrNull { pm.getLeanbackLaunchIntentForPackage(it) ?: pm.getLaunchIntentForPackage(it) }

    fun installedPackage(pm: PackageManager) = packages.firstOrNull { p ->
        try { pm.getApplicationInfo(p, 0).enabled } catch (e: PackageManager.NameNotFoundException) { false }
    }

    /** Free apps are offered for installation; paid or geo-blocked ones only show once installed. */
    fun visible(pm: PackageManager) = installedPackage(pm) != null || (onPlayStore && terms in setOf(Terms.FREE, Terms.ACCOUNT, Terms.FREEMIUM))
}

/** A group of a playlist (country, category), opened as a grid. */
class Folder(override val title: String, val channels: List<Channel>, val source: String) : Item() {
    override val key get() = "folder:$source:$title"
}

/** A settings card, or a plain hint when [id] is empty. */
data class Setting(val id: String, override val title: String, val value: String = "") : Item() {
    override val key get() = "setting:$id:$title"
}

private val MOVIES_SERIES = setOf(Cat.MOVIES, Cat.SERIES)

val APPS = listOf(
    App("cinefuse", listOf("com.local.cinefusetv"), "CINEFUSE TV", R.string.app_cinefuse, Terms.SITE, MOVIES_SERIES, false),
    App("watched", listOf("com.local.watchedtv"), "WATCHED", R.string.app_watched, Terms.SITE, MOVIES_SERIES, false),
    // checked on the TV in Portugal on 2026-11-11; Pluto TV ("not available in your location") and Tubi (not offered) are left out
    App("plex", listOf("com.plexapp.android"), "Plex", R.string.app_plex, Terms.FREE, MOVIES_SERIES + Cat.DOCS),
    App("rakuten", listOf("tv.wuaki.apptv", "tv.wuaki"), "Rakuten TV", R.string.app_rakuten, Terms.FREEMIUM, MOVIES_SERIES),
    App("arte", listOf("tv.arte.plus7"), "ARTE", R.string.app_arte, Terms.FREE, setOf(Cat.DOCS, Cat.MOVIES, Cat.SERIES, Cat.LIVE)),
    App("viki", listOf("com.viki.android"), "Viki", R.string.app_viki, Terms.ACCOUNT, setOf(Cat.SERIES)),
    App("crunchyroll", listOf("com.crunchyroll.crunchyroid"), "Crunchyroll", R.string.app_crunchyroll, Terms.PAID, setOf(Cat.SERIES)),
    App("rtp", listOf("pt.rtp.play"), "RTP Play", R.string.app_rtp, Terms.FREE, setOf(Cat.LIVE, Cat.SERIES, Cat.DOCS, Cat.SPORT)),
    App("tvi", listOf("pt.iol.tviplayer.androidtv"), "TVI Player", R.string.app_tvi, Terms.FREE, setOf(Cat.LIVE, Cat.SERIES)),
    App("opto", listOf("com.impresa.opta"), "OPTO SIC", R.string.app_opto, Terms.FREEMIUM, setOf(Cat.LIVE, Cat.SERIES)),
    App("rtve", listOf("com.rtve.androidtv"), "RTVE Play", R.string.app_rtve, Terms.FREE, setOf(Cat.LIVE, Cat.SERIES, Cat.DOCS)),
    App("redbull", listOf("com.nousguide.android.rbtv"), "Red Bull TV", R.string.app_redbull, Terms.FREE, setOf(Cat.SPORT, Cat.DOCS)),
    App("smarttube", listOf("org.smarttube.stable", "org.smarttube.beta"), "SmartTube", R.string.app_smarttube, Terms.FREE, setOf(Cat.YOUTUBE), false),
    App("youtube", listOf("com.google.android.youtube.tv"), "YouTube", R.string.app_youtube, Terms.FREE, setOf(Cat.YOUTUBE)),
    App("ytmusic", listOf("com.google.android.youtube.tvmusic"), "YouTube Music", R.string.app_ytmusic, Terms.FREE, setOf(Cat.YOUTUBE)),
    App("iptv4free", listOf("com.iptv4free.launcher"), "IPTV4FREE", R.string.app_iptv4free, Terms.FREE, setOf(Cat.IPTV, Cat.LIVE), false),
    App("kodi", listOf("org.xbmc.kodi"), "Kodi", R.string.app_kodi, Terms.FREE, setOf(Cat.IPTV)),
    App("tivimate", listOf("ar.tvplayer.tv"), "TiviMate", R.string.app_tivimate, Terms.FREEMIUM, setOf(Cat.IPTV)),
    App("francetv", listOf("fr.francetv.pluzz"), "france.tv", R.string.app_france, Terms.FRANCE, setOf(Cat.LIVE)),
    App("tf1", listOf("fr.tf1.mytf1"), "TF1+", R.string.app_france, Terms.FRANCE, setOf(Cat.LIVE)),
    App("m6", listOf("fr.m6.m6replay"), "M6+", R.string.app_france, Terms.FRANCE, setOf(Cat.LIVE)),
    App("sporttv", listOf("pt.sporttv.app.androidtv"), "Sport TV", R.string.app_paid, Terms.PAID, setOf(Cat.SPORT)),
    App("dazn", listOf("com.dazn"), "DAZN", R.string.app_paid, Terms.PAID, setOf(Cat.SPORT)),
)

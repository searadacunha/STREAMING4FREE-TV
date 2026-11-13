package com.local.streaming4free

import android.content.Context
import android.content.SharedPreferences
import android.content.res.Configuration
import android.util.Log
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.util.Locale
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.Executors

const val TAG = "S4F"

/** Downloads, parsing and search run here, never on the main thread. */
val IO = Executors.newFixedThreadPool(2)

fun JSONArray.objects() = (0 until length()).map { getJSONObject(it) }

fun channel(o: JSONObject) = Channel(o.getString("n"), o.getString("u"), o.optString("l"), o.optString("g"), o.optString("s"), o.optString("id"), o.optString("q"))

/** Favorites, history, resume positions and settings: kept on the TV, nothing leaves it. */
object Store {
    private lateinit var prefs: SharedPreferences
    private lateinit var positions: SharedPreferences
    private lateinit var failures: SharedPreferences

    fun init(c: Context) {
        if (::prefs.isInitialized) return
        val app = c.applicationContext ?: c
        prefs = app.getSharedPreferences("hub", Context.MODE_PRIVATE)
        positions = app.getSharedPreferences("positions", Context.MODE_PRIVATE)
        failures = app.getSharedPreferences("failures", Context.MODE_PRIVATE)
    }

    /** "" follows the TV's language. */
    var lang: String
        get() = prefs.getString("lang", "")!!
        set(v) = prefs.edit().putString("lang", v).apply()

    /** 0 lets the player pick the quality from the bandwidth. */
    var maxHeight: Int
        get() = prefs.getInt("maxHeight", 0)
        set(v) = prefs.edit().putInt("maxHeight", v).apply()

    fun localized(c: Context): Context {
        init(c)
        if (lang.isEmpty()) return c
        val cfg = Configuration(c.resources.configuration)
        cfg.setLocale(Locale(lang))
        return c.createConfigurationContext(cfg)
    }

    /** Called on the main thread after favorites or history change, by the page on screen. */
    var onChange: (() -> Unit)? = null

    fun favorites() = list("favorites")
    fun history() = list("history")

    /** Returns true when [i] is now a favorite. */
    fun toggleFavorite(i: Item): Boolean {
        val l = favorites().toMutableList()
        val added = !l.removeAll { it.key == i.key }
        if (added) l.add(0, i)
        save("favorites", l)
        onChange?.invoke()
        return added
    }

    fun addHistory(i: Item) = save("history", (listOf(i) + history().filter { it.key != i.key }).take(40))

    fun clearHistory() {
        prefs.edit().remove("history").apply()
        positions.edit().clear().apply()
        onChange?.invoke()
    }

    /** Resume position of a film or replay; live streams have none. */
    fun position(url: String) = positions.getLong(url, 0)
    fun setPosition(url: String, ms: Long) = positions.edit().apply { if (ms > 0) putLong(url, ms) else remove(url) }.apply()

    /** A stream that failed on this TV stays greyed out for a day, or until it plays again. */
    fun isDead(url: String) = System.currentTimeMillis() - failures.getLong(url, 0) < 24 * 3600_000L
    fun markDead(url: String, dead: Boolean) = failures.edit().apply { if (dead) putLong(url, System.currentTimeMillis()) else remove(url) }.apply()

    private fun list(name: String): List<Item> = try {
        JSONArray(prefs.getString(name, "[]")).objects().mapNotNull { o ->
            if (o.has("app")) APPS.find { it.id == o.getString("app") } else channel(o)
        }
    } catch (e: Exception) { // unreadable after a format change: start empty rather than crash at launch
        Log.w(TAG, "$name unreadable: $e")
        emptyList()
    }

    private fun save(name: String, items: List<Item>) {
        val a = JSONArray()
        for (i in items) when (i) {
            is App -> a.put(JSONObject().put("app", i.id))
            is Channel -> a.put(JSONObject().put("n", i.title).put("u", i.url).put("l", i.logo).put("g", i.group).put("s", i.source).put("id", i.id).put("q", i.quality))
            else -> {}
        }
        prefs.edit().putString(name, a.toString()).apply()
    }
}

/** The channels checked from the TV's own network by tools/probe_streams.py, shipped inside the app. */
object Catalog {
    class Row(val cat: String, val row: String, val items: List<Channel>)

    var checked = ""
        private set
    private var rows: List<Row> = emptyList()

    fun rows(c: Context): List<Row> {
        if (rows.isEmpty()) {
            val o = JSONObject(c.assets.open("catalog.json").bufferedReader().use { it.readText() })
            checked = o.getString("checked")
            rows = o.getJSONArray("rows").objects().map { r ->
                Row(r.getString("cat"), r.getString("row"), r.getJSONArray("items").objects().map { channel(it).copy(group = countryName(it.optString("c"))) })
            }
        }
        return rows
    }
}

fun countryName(code: String) = if (code.length == 2) Locale("", code.uppercase(Locale.ROOT)).displayCountry else ""

/** The three public playlists, downloaded by the TV itself and kept 12 hours. */
object Playlists {
    class Source(val name: String, val url: String)

    val SOURCES = listOf(
        Source("M3UPT", "https://m3upt.com/iptv"),
        Source("Free-TV", "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8"),
        Source("iptv-org", "https://iptv-org.github.io/iptv/index.m3u"),
    )
    private const val MAX_AGE = 12 * 3600_000L
    private val memory = ConcurrentHashMap<String, List<Channel>>()
    private val folders = ConcurrentHashMap<String, List<Folder>>()
    private val FIRST = listOf("TV", "Portugal", "France", "Brazil", "Belgium", "Switzerland")

    fun file(c: Context, s: Source) = File(c.filesDir, s.name + ".m3u")

    /** Whatever is already in memory, for the search screen. */
    fun loaded(s: Source) = memory[s.name].orEmpty()

    /** The list's groups (country, category), Portuguese and French first, then the biggest. Blocking. */
    fun folders(c: Context, s: Source, refresh: Boolean = false): List<Folder> {
        if (!refresh) folders[s.name]?.let { return it }
        val groups = LinkedHashMap<String, MutableList<Channel>>()
        for (ch in load(c, s, refresh))
            for (g in ch.group.split(';')) groups.getOrPut(g.trim().ifEmpty { "-" }) { ArrayList() } += ch
        return groups.map { (g, l) -> Folder(g, l, s.name) }
            .sortedWith(compareBy({ FIRST.indexOf(it.title).let { i -> if (i < 0) FIRST.size else i } }, { -it.channels.size }))
            .also { folders[s.name] = it }
    }

    /** Blocking: call it off the main thread. Offline, the last downloaded copy is used, however old. */
    @Throws(IOException::class)
    fun load(c: Context, s: Source, refresh: Boolean = false): List<Channel> {
        if (!refresh) memory[s.name]?.let { return it }
        val file = file(c, s)
        if (refresh || System.currentTimeMillis() - file.lastModified() > MAX_AGE) try {
            val tmp = File(c.filesDir, s.name + ".tmp")
            val http = URL(s.url).openConnection() as HttpURLConnection
            try {
                http.connectTimeout = 10_000
                http.readTimeout = 20_000
                if (http.responseCode != 200) throw IOException("HTTP ${http.responseCode}")
                http.inputStream.use { i -> tmp.outputStream().use { i.copyTo(it) } }
            } finally {
                http.disconnect()
            }
            // a captive portal or an error page must not replace a good list
            if (tmp.useLines { it.firstOrNull()?.trimStart('﻿')?.startsWith("#EXTM3U") } != true) throw IOException("not a playlist")
            if (!tmp.renameTo(file)) throw IOException("cannot store the playlist")
        } catch (e: IOException) {
            Log.w(TAG, "playlist ${s.name}: $e")
            if (!file.exists()) throw e
        }
        return file.useLines { parseM3u(it, s.name) }.also { memory[s.name] = it; folders.remove(s.name) }
    }
}

private val ATTR = Regex("""([\w-]+)="([^"]*)"""")
private val MARKERS = Regex("\\s*[ⓈⒼⓎⒹ]") // Free-TV's flags (geo-blocked, YouTube...), not part of the name

/**
 * Reads an extended M3U playlist. Left out: entries that are not http(s), and entries that only play with a DRM key
 * written in the list. Request headers a list declares (browser user agent, Referer) are not sent by the player.
 */
fun parseM3u(lines: Sequence<String>, source: String): List<Channel> {
    val out = ArrayList<Channel>()
    var info: String? = null
    var drm = false
    for (raw in lines) {
        val line = raw.trim()
        when {
            line.startsWith("#EXTINF") -> { info = line; drm = false }
            info == null || line.isEmpty() -> {}
            line.startsWith("#KODIPROP") && "license" in line -> drm = true
            line.startsWith("#") -> {}
            else -> {
                if (!drm && (line.startsWith("http://") || line.startsWith("https://"))) {
                    val a = ATTR.findAll(info).associate { it.groupValues[1] to it.groupValues[2] }
                    val name = info.substring(info.indexOf(',', info.lastIndexOf('"') + 1) + 1).replace(MARKERS, "").trim()
                    out += Channel(name.ifEmpty { a["tvg-name"].orEmpty() }, line, a["tvg-logo"].orEmpty(), a["group-title"].orEmpty(), source, a["tvg-id"].orEmpty())
                }
                info = null
            }
        }
    }
    return out
}

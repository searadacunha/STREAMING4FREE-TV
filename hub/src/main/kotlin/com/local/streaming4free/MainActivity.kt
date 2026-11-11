package com.local.streaming4free

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.widget.Toast
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import androidx.fragment.app.FragmentActivity
import androidx.leanback.app.BrowseSupportFragment
import androidx.leanback.app.RowsSupportFragment
import androidx.leanback.widget.ArrayObjectAdapter
import androidx.leanback.widget.HeaderItem
import androidx.leanback.widget.ListRow
import androidx.leanback.widget.ListRowPresenter
import androidx.leanback.widget.OnItemViewClickedListener
import androidx.leanback.widget.PageRow
import java.io.IOException

class MainActivity : FragmentActivity() {
    override fun attachBaseContext(base: Context) = super.attachBaseContext(Store.localized(base))

    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        if (b == null) supportFragmentManager.beginTransaction().replace(android.R.id.content, HubFragment()).commit()
    }
}

/** Left menu = the sections; each one opens its own page of rows. */
class HubFragment : BrowseSupportFragment() {
    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        val c = requireContext()
        title = getString(R.string.app_name)
        headersState = HEADERS_ENABLED
        isHeadersTransitionOnBackEnabled = true
        brandColor = ContextCompat.getColor(c, R.color.brand)
        searchAffordanceColor = ContextCompat.getColor(c, R.color.accent)
        setOnSearchClickedListener { startActivity(Intent(c, SearchActivity::class.java)) }
        mainFragmentRegistry.registerFragment(PageRow::class.java, object : FragmentFactory<Fragment>() {
            override fun createFragment(row: Any?) = PageFragment.of(Cat.entries[(row as PageRow).headerItem.id.toInt()])
        })
        adapter = ArrayObjectAdapter(ListRowPresenter()).apply {
            for (cat in Cat.entries) add(PageRow(HeaderItem(cat.ordinal.toLong(), getString(cat.title))))
        }
    }
}

/** Titles of the catalog rows written by tools/probe_streams.py, keyed "cat/row". */
private val ROW_TITLES = mapOf(
    "live/pt" to R.string.row_live_pt, "live/fra" to R.string.row_live_fra, "live/por" to R.string.row_live_por,
    "live/kids" to R.string.row_live_kids, "live/music" to R.string.row_live_music, "live/news" to R.string.row_live_news,
    "live/other" to R.string.row_live_other,
    "sport/por" to R.string.row_sport_por, "sport/fra" to R.string.row_sport_fra, "sport/int" to R.string.row_sport_int,
    "docs/por" to R.string.row_docs_por, "docs/fra" to R.string.row_docs_fra, "docs/int" to R.string.row_docs_int,
    "movies/por" to R.string.row_movies_por, "movies/fra" to R.string.row_movies_fra, "movies/int" to R.string.row_movies_int,
    "series/por" to R.string.row_series_por, "series/fra" to R.string.row_series_fra, "series/int" to R.string.row_series_int,
)

private val YOUTUBE_GROUPS = setOf("France", "Portugal", "Brazil", "Belgium", "Switzerland", "Luxembourg", "Monaco", "News")

class PageFragment : RowsSupportFragment() {
    companion object {
        fun of(cat: Cat) = PageFragment().apply { arguments = Bundle().apply { putInt("cat", cat.ordinal) } }
    }

    /** A row and, for rows that change while the hub is open, how to recompute it. */
    private class Live(val items: ArrayObjectAdapter, val compute: (() -> List<Item>)?)

    private val rows = ArrayObjectAdapter(ListRowPresenter())
    private val live = ArrayList<Live>()
    private val main = Handler(Looper.getMainLooper())
    private val cat get() = Cat.entries[requireNotNull(arguments).getInt("cat")]

    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        adapter = rows
        onItemViewClickedListener = OnItemViewClickedListener { _, item, _, _ ->
            if (item is Setting) setting(item) else open(requireActivity(), item as Item)
        }
        build()
        mainFragmentAdapter.fragmentHost?.notifyDataReady(mainFragmentAdapter)
    }

    private val onStoreChange = { refresh() }

    override fun onResume() {
        super.onResume()
        refresh()
        Store.onChange = onStoreChange
    }

    override fun onPause() {
        if (Store.onChange === onStoreChange) Store.onChange = null
        super.onPause()
    }

    private fun refresh() {
        for (l in live) if (l.compute != null) l.items.setItems(l.compute.invoke(), DIFF)
            else l.items.notifyArrayItemRangeChanged(0, l.items.size()) // installed apps, dead streams
    }

    /** [dynamic] rows are kept even when empty (with a hint), so the page keeps its shape and the focus its place. */
    private fun row(title: Int, dynamic: Boolean = false, compute: () -> List<Item>): ArrayObjectAdapter? {
        val first = compute()
        if (first.isEmpty()) return null
        val items = ArrayObjectAdapter(CardPresenter())
        items.setItems(first, null)
        rows.add(ListRow(HeaderItem(getString(title)), items))
        live += Live(items, if (dynamic) compute else null)
        return items
    }

    private fun hint(id: Int) = listOf(Setting("", getString(id)))

    private fun apps(vararg cats: Cat): List<Item> {
        val pm = requireContext().packageManager
        return APPS.filter { a -> a.cats.any { it in cats } && a.visible(pm) }
            .sortedBy { it.installedPackage(pm) == null } // installed first, then those to install
    }

    private fun catalog(cat: String, vararg rows: String) {
        val all = Catalog.rows(requireContext())
        for (r in rows) all.find { it.cat == cat && it.row == r }?.let { found -> row(ROW_TITLES.getValue("$cat/$r")) { found.items } }
    }

    private fun build() {
        val c = requireContext()
        when (cat) {
            Cat.HOME -> {
                row(R.string.row_continue, true) { Store.history().take(15).ifEmpty { hint(R.string.hint_history) } }
                row(R.string.row_favorites, true) { Store.favorites().ifEmpty { hint(R.string.hint_favorites) } }
                row(R.string.row_apps) { APPS.filter { it.installedPackage(c.packageManager) != null && it.terms != Terms.PAID } }
                catalog("live", "pt", "fra")
                row(R.string.row_free_apps) { APPS.filter { it.visible(c.packageManager) && it.installedPackage(c.packageManager) == null } }
            }
            Cat.MOVIES -> { row(R.string.row_apps) { apps(Cat.MOVIES) }; catalog("movies", "por", "fra", "int") }
            Cat.SERIES -> { row(R.string.row_apps) { apps(Cat.SERIES) }; catalog("series", "por", "fra", "int") }
            Cat.LIVE -> { row(R.string.row_apps) { apps(Cat.LIVE) }; catalog("live", "pt", "fra", "por", "kids", "music", "news", "other") }
            Cat.SPORT -> { row(R.string.row_apps) { apps(Cat.SPORT) }; catalog("sport", "por", "fra", "int") }
            Cat.DOCS -> { row(R.string.row_apps) { apps(Cat.DOCS) }; catalog("docs", "por", "fra", "int") }
            Cat.YOUTUBE -> {
                row(R.string.row_apps) { apps(Cat.YOUTUBE) }
                val freeTv = Playlists.SOURCES.first { it.name == "Free-TV" } // the only list with official YouTube live channels
                rowLater(getString(R.string.row_youtube_live)) { app ->
                    Playlists.load(app, freeTv).filter { it.isYouTube && it.group in YOUTUBE_GROUPS }.distinctBy { it.url }
                }
            }
            Cat.IPTV -> {
                row(R.string.row_apps) { apps(Cat.IPTV) }
                for (s in Playlists.SOURCES) rowLater(s.name) { app -> Playlists.folders(app, s) }
            }
            Cat.FAVORITES -> row(R.string.cat_favorites, true) { Store.favorites().ifEmpty { hint(R.string.hint_favorites) } }
            Cat.CONTINUE -> row(R.string.cat_continue, true) { Store.history().ifEmpty { hint(R.string.hint_history) } }
            Cat.SETTINGS -> settings()
        }
    }

    /** A playlist row shows "loading" at once; the TV downloads the list (kept 12 h) in the background. */
    private fun rowLater(title: String, load: (Context) -> List<Item>) {
        val items = ArrayObjectAdapter(CardPresenter())
        items.add(Setting("", getString(R.string.loading)))
        rows.add(ListRow(HeaderItem(title), items))
        live += Live(items, null)
        val app = requireContext().applicationContext
        val offline = getString(R.string.list_offline)
        IO.execute {
            val result: List<Item> = try { load(app) } catch (e: IOException) { listOf(Setting("", offline)) }
            main.post { if (isAdded) items.setItems(result.ifEmpty { listOf(Setting("", offline)) }, DIFF) }
        }
    }

    private fun settings() {
        val c = requireContext()
        fun mark(on: Boolean) = if (on) getString(R.string.current) else ""
        row(R.string.set_lang, true) {
            listOf("" to R.string.lang_auto, "fr" to R.string.lang_fr, "pt" to R.string.lang_pt)
                .map { (code, name) -> Setting("lang:$code", getString(name), mark(Store.lang == code)) }
        }
        row(R.string.set_quality, true) {
            listOf(0 to R.string.q_auto, 1080 to R.string.q_1080, 720 to R.string.q_720, 480 to R.string.q_480)
                .map { (h, name) -> Setting("q:$h", getString(name), mark(Store.maxHeight == h)) }
        }
        row(R.string.set_data) {
            listOf(Setting("refresh", getString(R.string.refresh), getString(R.string.refresh_value)),
                Setting("clear", getString(R.string.clear_history)))
        }
        row(R.string.set_help) {
            val n = Catalog.rows(c).sumOf { it.items.size }
            listOf(Setting("", getString(R.string.help_fav)), Setting("", getString(R.string.help_back)),
                Setting("", getString(R.string.catalog_info, n), Catalog.checked),
                Setting("", getString(R.string.version), c.packageManager.getPackageInfo(c.packageName, 0).versionName.orEmpty()))
        }
        row(R.string.set_unavailable) {
            listOf(Setting("", getString(R.string.un_rtp), getString(R.string.un_rtp_v)),
                Setting("", getString(R.string.un_fr), getString(R.string.un_fr_v)),
                Setting("", getString(R.string.un_paid), getString(R.string.un_paid_v)))
        }
    }

    private fun setting(s: Setting) {
        val a = requireActivity()
        when {
            s.id.startsWith("lang:") -> if (Store.lang != s.id.substring(5)) { Store.lang = s.id.substring(5); a.recreate() }
            s.id.startsWith("q:") -> { Store.maxHeight = s.id.substring(2).toInt(); refresh() }
            s.id == "refresh" -> {
                Toast.makeText(a, R.string.loading, Toast.LENGTH_SHORT).show()
                val app = a.applicationContext
                IO.execute {
                    val ok = Playlists.SOURCES.count { src -> try { Playlists.folders(app, src, true); true } catch (e: IOException) { false } }
                    main.post { Toast.makeText(app, app.getString(R.string.refresh_done, ok, Playlists.SOURCES.size), Toast.LENGTH_LONG).show() }
                }
            }
            s.id == "clear" -> { Store.clearHistory(); Toast.makeText(a, R.string.cleared, Toast.LENGTH_SHORT).show() }
        }
    }
}

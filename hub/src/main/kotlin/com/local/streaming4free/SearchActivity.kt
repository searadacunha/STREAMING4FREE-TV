package com.local.streaming4free

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import androidx.fragment.app.FragmentActivity
import androidx.leanback.app.SearchSupportFragment
import androidx.leanback.widget.ArrayObjectAdapter
import androidx.leanback.widget.HeaderItem
import androidx.leanback.widget.ListRow
import androidx.leanback.widget.ListRowPresenter
import androidx.leanback.widget.ObjectAdapter
import androidx.leanback.widget.OnItemViewClickedListener
import java.io.IOException
import java.text.Normalizer

/** One search over the hub's apps, the checked channels, the three public playlists, and a hand-off to YouTube. */
class SearchActivity : FragmentActivity() {
    override fun attachBaseContext(base: Context) = super.attachBaseContext(Store.localized(base))

    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        if (b == null) supportFragmentManager.beginTransaction().replace(android.R.id.content, Search()).commit()
    }

    class Search : SearchSupportFragment(), SearchSupportFragment.SearchResultProvider {
        private val results = ArrayObjectAdapter(ListRowPresenter())
        private val main = Handler(Looper.getMainLooper())
        @Volatile private var query = ""

        @Suppress("DEPRECATION") // the callback hands voice input to the TV's own recognizer: no microphone permission
        override fun onCreate(b: Bundle?) {
            super.onCreate(b)
            setSearchResultProvider(this)
            setOnItemViewClickedListener(OnItemViewClickedListener { _, item, _, _ -> open(requireActivity(), item as Item) })
            setSpeechRecognitionCallback {
                try { startActivityForResult(recognizerIntent, 1) } catch (e: ActivityNotFoundException) {}
            }
            if (b == null) setSearchQuery("", false) // opens on the keyboard; voice stays one press away (mic button)
            val app = requireContext().applicationContext
            for (s in Playlists.SOURCES) IO.execute { // so that the playlists can be searched too
                try { Playlists.load(app, s) } catch (e: IOException) {}
            }
        }

        @Deprecated("Activity result API not needed for one request")
        @Suppress("DEPRECATION")
        override fun onActivityResult(request: Int, result: Int, data: Intent?) {
            if (request == 1 && result == android.app.Activity.RESULT_OK && data != null) setSearchQuery(data, true)
        }

        override fun getResultsAdapter(): ObjectAdapter = results

        override fun onQueryTextChange(q: String): Boolean {
            main.removeCallbacksAndMessages(null)
            main.postDelayed({ search(q) }, 300)
            return true
        }

        override fun onQueryTextSubmit(q: String): Boolean {
            main.removeCallbacksAndMessages(null)
            search(q)
            return true
        }

        private fun search(q: String) {
            query = q
            if (q.trim().length < 2) {
                results.clear()
                return
            }
            val c = requireContext().applicationContext
            val n = norm(q)
            val youtube = getString(R.string.search_youtube, q.trim())
            val titles = listOf(R.string.search_apps, R.string.search_catalog).map(::getString)
            IO.execute {
                val pm = c.packageManager
                val found = ArrayList<Pair<String, List<Item>>>()
                found += titles[0] to APPS.filter { it.visible(pm) && norm(it.title).contains(n) }
                found += titles[1] to Catalog.rows(c).flatMap { it.items }.filter { norm(it.title).contains(n) }.distinctBy { it.url }.take(60)
                for (s in Playlists.SOURCES) found += s.name to Playlists.loaded(s).filter { norm(it.title).contains(n) }.take(60)
                found += "YouTube" to listOf(Channel(youtube, "https://www.youtube.com/results?search_query=" + Uri.encode(q.trim())))
                main.post {
                    if (!isAdded || query != q) return@post
                    results.clear()
                    for ((title, items) in found) if (items.isNotEmpty())
                        results.add(ListRow(HeaderItem(title), ArrayObjectAdapter(CardPresenter()).apply { setItems(items, null) }))
                }
            }
        }

        private fun norm(s: String) = Normalizer.normalize(s.lowercase(), Normalizer.Form.NFD).replace(MARKS, "")

        private companion object {
            val MARKS = Regex("\\p{Mn}+")
        }
    }
}

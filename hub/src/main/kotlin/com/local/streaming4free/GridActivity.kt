package com.local.streaming4free

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import androidx.fragment.app.FragmentActivity
import androidx.leanback.app.VerticalGridSupportFragment
import androidx.leanback.widget.ArrayObjectAdapter
import androidx.leanback.widget.OnItemViewClickedListener
import androidx.leanback.widget.VerticalGridPresenter
import java.io.IOException

/** All the channels of one playlist group. */
class GridActivity : FragmentActivity() {
    companion object {
        fun intent(c: Context, f: Folder): Intent =
            Intent(c, GridActivity::class.java).putExtra("source", f.source).putExtra("group", f.title)
    }

    override fun attachBaseContext(base: Context) = super.attachBaseContext(Store.localized(base))

    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        if (b == null) supportFragmentManager.beginTransaction().replace(android.R.id.content, Grid()).commit()
    }

    class Grid : VerticalGridSupportFragment() {
        private val items = ArrayObjectAdapter(CardPresenter())

        override fun onCreate(b: Bundle?) {
            super.onCreate(b)
            val extras = requireActivity().intent
            val group = extras.getStringExtra("group").orEmpty()
            val source = Playlists.SOURCES.first { it.name == extras.getStringExtra("source") }
            setTitle("${source.name} · $group")
            setGridPresenter(VerticalGridPresenter().apply { numberOfColumns = 5 })
            adapter = items
            onItemViewClickedListener = OnItemViewClickedListener { _, item, _, _ -> open(requireActivity(), item as Item) }
            val app = requireContext().applicationContext
            val main = Handler(Looper.getMainLooper())
            IO.execute { // in memory when opened from the hub; read back from the TV's copy after Android closed the app
                val channels = try { Playlists.folders(app, source).find { it.title == group }?.channels.orEmpty() } catch (e: IOException) { emptyList() }
                main.post { if (isAdded) items.setItems(channels.ifEmpty { listOf(Setting("", getString(R.string.list_offline))) }, DIFF) }
            }
        }

        override fun onResume() {
            super.onResume()
            items.notifyArrayItemRangeChanged(0, items.size()) // a stream that just failed is greyed out
        }
    }
}

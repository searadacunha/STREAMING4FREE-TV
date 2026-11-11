package com.local.streaming4free

import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.view.ViewGroup
import android.widget.ImageView
import android.widget.Toast
import androidx.core.content.ContextCompat
import androidx.leanback.widget.DiffCallback
import androidx.leanback.widget.ImageCardView
import androidx.leanback.widget.Presenter
import coil.dispose
import coil.load

/** Cards keep their identity across refreshes, so focus stays put; channel cards are always redrawn (dead or alive). */
val DIFF = object : DiffCallback<Item>() {
    override fun areItemsTheSame(a: Item, b: Item) = a.key == b.key
    override fun areContentsTheSame(a: Item, b: Item) = a == b && a !is Channel
}

class CardPresenter : Presenter() {
    override fun onCreateViewHolder(parent: ViewGroup): ViewHolder {
        val c = parent.context
        val idle = ContextCompat.getColor(c, R.color.card)
        val focused = ContextCompat.getColor(c, R.color.accent)
        val card = object : ImageCardView(c) {
            override fun setSelected(selected: Boolean) {
                setInfoAreaBackgroundColor(if (selected) focused else idle)
                super.setSelected(selected)
            }
        }
        val d = c.resources.displayMetrics.density
        card.setMainImageDimensions((176 * d).toInt(), (99 * d).toInt())
        card.setMainImageScaleType(ImageView.ScaleType.FIT_CENTER)
        card.mainImageView?.setBackgroundColor(ContextCompat.getColor(c, R.color.card_image))
        card.setInfoAreaBackgroundColor(idle)
        card.isFocusable = true
        card.isFocusableInTouchMode = true
        return ViewHolder(card)
    }

    override fun onBindViewHolder(vh: ViewHolder, item: Any?) {
        val card = vh.view as ImageCardView
        val c = card.context
        val i = item as Item
        card.titleText = i.title
        card.contentText = subtitle(c, i)
        card.alpha = if (i is Channel && Store.isDead(i.url)) 0.45f else 1f
        when (i) {
            is Channel -> card.mainImageView?.load(i.logo.ifEmpty { null }) {
                placeholder(R.drawable.ph_tv)
                error(R.drawable.ph_tv)
                fallback(R.drawable.ph_tv)
            }
            is App -> card.mainImage = i.installedPackage(c.packageManager)?.let { p ->
                c.packageManager.getApplicationBanner(p) ?: c.packageManager.getApplicationIcon(p)
            } ?: ContextCompat.getDrawable(c, R.drawable.ph_app)
            is Folder -> card.mainImage = ContextCompat.getDrawable(c, R.drawable.ph_folder)
            is Setting -> card.mainImage = ContextCompat.getDrawable(c, R.drawable.ph_setting)
        }
        card.setOnLongClickListener { // long press on OK
            if (i is Channel || i is App) {
                val added = Store.toggleFavorite(i)
                Toast.makeText(c, if (added) R.string.fav_added else R.string.fav_removed, Toast.LENGTH_SHORT).show()
            }
            true
        }
    }

    override fun onUnbindViewHolder(vh: ViewHolder) {
        val card = vh.view as ImageCardView
        card.mainImageView?.dispose()
        card.mainImage = null
        card.setOnLongClickListener(null)
    }

    private fun subtitle(c: Context, i: Item): String = when (i) {
        is Channel -> if (Store.isDead(i.url)) c.getString(R.string.dead)
            else listOf(i.quality.substringBefore(' '), i.group.substringBefore(';'), i.source).filter { it.isNotEmpty() }.joinToString(" · ")
        is App -> if (i.installedPackage(c.packageManager) != null) c.getString(i.terms.label) + " · " + c.getString(i.desc)
            else c.getString(R.string.to_install) + " · " + c.getString(i.terms.label)
        is Folder -> c.getString(R.string.channels_count, i.channels.size)
        is Setting -> i.value
    }
}

/** What OK on a card does. Settings are handled by the page that shows them. */
fun open(a: Activity, i: Item) {
    when (i) {
        is Channel -> if (i.isYouTube) openYouTube(a, i) else a.startActivity(PlayerActivity.intent(a, i))
        is App -> openApp(a, i)
        is Folder -> a.startActivity(GridActivity.intent(a, i))
        is Setting -> {}
    }
}

private fun openApp(a: Activity, app: App) {
    val launch = app.launchIntent(a.packageManager)
    when {
        launch != null -> {
            Store.addHistory(app)
            a.startActivity(launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        }
        app.onPlayStore -> try { // the TV's Play Store opens on the app's page: one press on Install
            a.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("market://details?id=" + app.packages[0])))
        } catch (e: ActivityNotFoundException) {
            Toast.makeText(a, R.string.no_store, Toast.LENGTH_LONG).show()
        }
        else -> Toast.makeText(a, R.string.not_installed, Toast.LENGTH_LONG).show()
    }
}

/** YouTube pages go to SmartTube when installed (no ads), else to the YouTube app. */
private fun openYouTube(a: Activity, ch: Channel) {
    val pm = a.packageManager
    val pkg = APPS.filter { it.id == "smarttube" || it.id == "youtube" }.firstNotNullOfOrNull { it.installedPackage(pm) }
    if (pkg == null) {
        Toast.makeText(a, R.string.no_youtube, Toast.LENGTH_LONG).show()
        return
    }
    if (!ch.url.contains("/results?")) Store.addHistory(ch)
    try {
        a.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(ch.url)).setPackage(pkg).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    } catch (e: ActivityNotFoundException) {
        Toast.makeText(a, R.string.no_youtube, Toast.LENGTH_LONG).show()
    }
}

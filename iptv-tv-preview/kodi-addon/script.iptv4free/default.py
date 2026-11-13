"""IPTV4FREE inside Kodi: full-screen live TV home driven by the remote."""
import json
import os
import sys
import time

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

ADDON = xbmcaddon.Addon()
ROOT = xbmcvfs.translatePath(ADDON.getAddonInfo("path"))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))
import core  # noqa: E402

LIVE, GUIDE, FAVS, SEARCH, GROUPS_BTN, SETTINGS, QUIT = range(100, 107)
GROUPS, CHANNELS, OPEN_PROGRAMME, PROGRAMME = 300, 500, 599, 600
BACK, CONTEXT, INFO, DOWN, PAGE_DOWN = (9, 10, 92), (117,), (11,), 4, 6
PAGE_SIZE, SHORTLIST = 300, 60  # channels per page in a group; max search/favourite results
STALE = 300  # seconds before now/next is reloaded when coming back to the window
rpc = xbmc.executeJSONRPC
HOME, RUNNING = xbmcgui.Window(10000), "iptv4free.window"  # Kodi Home window holds the instance flag
FROM_TILE = "iptv4free.android"


def log(msg, level=xbmc.LOGINFO):
    xbmc.log(f"IPTV4FREE: {msg}", level)


class Player(xbmc.Player):
    """Kodi calls these on the script thread while the window waits in doModal()."""

    def onAVStarted(self):
        self.ui.on_started()

    def onPlayBackError(self):
        self.ui.on_failed()

    # A stream that cannot be demuxed ends with Stopped/Ended, never with Error (seen in Kodi 21.3).
    onPlayBackStopped = onPlayBackEnded = onPlayBackError


class TVHome(xbmcgui.WindowXML):
    # No __init__: Kodi builds the native window from the constructor arguments.

    def boot(self):
        self.groups, self.channels, self.next, self.total, self.index = [], [], 0, 0, None
        self.view = {"kind": "group", "group": None, "title": "", "query": ""}
        self.loaded_at, self.guide_for, self.opening = 0.0, None, ""
        self.profile = xbmcvfs.translatePath(ADDON.getAddonInfo("profile"))
        self.fav_path = os.path.join(self.profile, "favorites.json")
        self.favorites = self._load_favorites()
        self.player = Player()
        self.player.ui = self
        self.started, self.resume_focus = False, None

    # ---------- lifecycle ----------
    def onInit(self):
        self.wid = xbmcgui.getCurrentWindowId()
        HOME.setProperty(RUNNING, str(self.wid))
        if not self.started:
            self.started = True
            self.setProperty("Loading", "true")
            self.setProperty("Empty", "Chargement des chaînes…")
            core.wait_for_pvr(rpc, xbmc.Monitor().waitForAbort)
            self._safe(self._load_groups)
            self._safe(lambda: self._show_group(core.default_group(self.groups)))
            self.clearProperty("Loading")
        elif time.time() - self.loaded_at > STALE:
            self._safe(self._reload)  # back from playback/guide: refresh now/next
        else:
            self._restore()
        self._mark_playing()
        focus, self.resume_focus = self.resume_focus, None  # back from the guide/settings: same button
        self.setFocusId(focus or (CHANNELS if self.channels else (GROUPS if self.groups else LIVE)))

    def _restore(self):
        """Kodi may rebuild the XML when the window comes back; refill lists if they were emptied."""
        if self.getControl(GROUPS).size() != len(self.groups):
            self._render_groups()
        if self.getControl(CHANNELS).size() != len(self.channels):
            pos = self.getControl(CHANNELS).getSelectedPosition()
            self._render_channels()
            self.getControl(CHANNELS).selectItem(max(pos, 0))

    def _safe(self, fn):
        try:
            fn()
        except core.RpcError as exc:
            log(exc, xbmc.LOGWARNING)
            self.setProperty("Empty", "Kodi PVR indisponible. Activez PVR IPTV Simple Client puis EN DIRECT.")

    # ---------- data ----------
    def _load_groups(self):
        self.groups = core.channel_groups(rpc)
        self._render_groups()

    def _all_group_id(self):
        group = core.default_group(self.groups)
        return group["channelgroupid"] if group else None

    def _show_group(self, group):
        if not group:
            self.channels, self.next, self.total = [], 0, 0
            self.view = {"kind": "group", "group": None, "title": "Aucune chaîne", "query": ""}
            self._render_channels("Aucune chaîne. Vérifiez IPTV Simple Client dans Kodi.")
            return
        self.setProperty("Busy", "true")
        try:
            self.channels, self.next, self.total = core.channels_page(rpc, group["channelgroupid"], 0, PAGE_SIZE)
        finally:
            self.clearProperty("Busy")
        country, category = core.group_names(group)
        title = f"{country.title()} · {category}" if country else category
        self.view = {"kind": "group", "group": group["channelgroupid"], "title": title, "query": ""}
        self.loaded_at = time.time()
        self._render_groups()
        self._render_channels("Aucune chaîne dans ce groupe.")

    def _more(self):
        """Progressive loading: next page when the remote reaches the end of the list."""
        if self.view["kind"] != "group" or self.next >= self.total:
            return
        page, self.next, self.total = core.channels_page(rpc, self.view["group"], self.next, PAGE_SIZE)
        if page:
            control = self.getControl(CHANNELS)
            pos = control.getSelectedPosition()
            self.channels.extend(page)
            control.addItems([self._item(c) for c in page])
            control.selectItem(pos)  # addItems rebinds the whole list and jumps back to row 1
            self._set_count()

    def _shortlist(self, kind, title, predicate, empty):
        self.setProperty("Busy", "true")
        try:
            if self.index is None:
                gid = self._all_group_id()
                self.index = core.channel_index(rpc, gid) if gid is not None else []
            found = [c for c in self.index if predicate(c)][:SHORTLIST]
            self.channels = core.with_programmes(rpc, found)
            self.next = self.total = len(found)
        finally:
            self.clearProperty("Busy")
        self.view = {"kind": kind, "group": None, "title": title, "query": self.view.get("query", "")}
        self.loaded_at = time.time()
        self._render_groups()
        self._render_channels(empty)

    def _show_favorites(self):
        names = {n.casefold() for n in self.favorites}
        self._shortlist("favorites", "Favoris", lambda c: c["name"].casefold() in names,
                        "Aucun favori. Sur une chaîne : MENU ou appui long sur OK, puis Ajouter aux favoris.")

    def _show_search(self, query):
        self.view["query"] = query
        self._shortlist("search", f"Recherche : {query}",
                        lambda c: core.filter_channels([c], search=query) != [],
                        f"Aucune chaîne ne contient « {query} ».")

    def _reload(self):
        self.index = None
        self._load_groups()
        kind = self.view["kind"]
        if kind == "favorites":
            self._show_favorites()
        elif kind == "search" and self.view["query"]:
            self._show_search(self.view["query"])
        else:
            gid = self.view["group"]
            self._show_group(next((g for g in self.groups if g["channelgroupid"] == gid), None)
                             or core.default_group(self.groups))

    # ---------- rendering ----------
    def _render_groups(self):
        items = []
        for g in self.groups:
            country, category = core.group_names(g)
            li = xbmcgui.ListItem(category or g.get("label", "Groupe"), country, offscreen=True)
            active = self.view["kind"] == "group" and g["channelgroupid"] == self.view["group"]
            li.setProperty("active", "true" if active else "")
            items.append(li)
        control = self.getControl(GROUPS)
        pos = control.getSelectedPosition()
        control.reset()
        control.addItems(items)
        if items:
            active = next((i for i, g in enumerate(self.groups)
                           if g["channelgroupid"] == self.view["group"]), max(pos, 0))
            control.selectItem(min(active, len(items) - 1))

    def _item(self, ch):
        li = xbmcgui.ListItem(ch["name"], ch["now"] or "Programme indisponible", offscreen=True)
        li.setArt({"thumb": ch["logo"]})
        for key in ("id", "number", "now_time", "progress", "next", "next_time"):
            li.setProperty(key, str(ch[key]))
        li.setProperty("favorite", "true" if ch["name"].casefold() in self._fav_keys() else "")
        return li

    def _render_channels(self, empty=""):
        control = self.getControl(CHANNELS)
        control.reset()
        control.addItems([self._item(c) for c in self.channels])
        self.guide_for = None
        self.clearProperty("GuideFor")
        self.setProperty("Title", self.view["title"])
        self.setProperty("Empty", "" if self.channels else empty)
        self._set_count()
        self._mark_playing()

    def _mark_playing(self):
        """White marker on the channel being played, also after zapping in full screen."""
        name = xbmc.getInfoLabel("VideoPlayer.ChannelName") if xbmc.getCondVisibility("Player.HasVideo") else ""
        control = self.getControl(CHANNELS)
        for pos in range(control.size()):
            item = control.getListItem(pos)
            item.setProperty("playing", "true" if name and item.getLabel() == name else "")

    def _set_count(self):
        more = self.view["kind"] == "group" and self.next < self.total
        self.setProperty("Count", core.count_label(len(self.channels), self.total, more))

    # ---------- favourites ----------
    def _fav_keys(self):
        return {n.casefold() for n in self.favorites}

    def _load_favorites(self):
        try:
            with open(self.fav_path, encoding="utf-8") as handle:
                data = json.load(handle)
            return [n for n in data if isinstance(n, str)]  # channel names survive PVR re-imports
        except (OSError, ValueError, TypeError):
            return []

    def _toggle_favorite(self, ch):
        key = ch["name"].casefold()
        if key in self._fav_keys():
            self.favorites = [n for n in self.favorites if n.casefold() != key]
        else:
            self.favorites.append(ch["name"])
        try:
            os.makedirs(self.profile, exist_ok=True)
            tmp = self.fav_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump(self.favorites, handle, ensure_ascii=False)
            os.replace(tmp, self.fav_path)
        except OSError as exc:
            log(f"favorites not saved: {exc}", xbmc.LOGERROR)
            xbmcgui.Dialog().notification("IPTV4FREE", "Favori non enregistré", xbmcgui.NOTIFICATION_ERROR)
            return
        if self.view["kind"] == "favorites":
            self._show_favorites()
            if not self.channels:
                self.setFocusId(FAVS)  # the emptied list cannot keep the focus
        else:
            item = self.getControl(CHANNELS).getSelectedItem()
            if item:
                item.setProperty("favorite", "true" if key in self._fav_keys() else "")

    # ---------- programme guide ----------
    def _selected(self):
        pos = self.getControl(CHANNELS).getSelectedPosition()
        return self.channels[pos] if 0 <= pos < len(self.channels) else None

    def _show_programme(self):
        ch = self._selected()
        if not ch:
            return
        if self.guide_for != ch["id"]:
            rows = core.schedule(rpc, ch["id"])
            items = []
            for row in rows:
                li = xbmcgui.ListItem(row["time"], row["title"], offscreen=True)
                li.setProperty("plot", row["plot"])
                li.setProperty("genre", row["genre"])
                li.setProperty("live", "true" if row["live"] else "")
                items.append(li)
            if not items:
                items = [xbmcgui.ListItem("", "Aucun programme pour cette chaîne", offscreen=True)]
            control = self.getControl(PROGRAMME)
            control.reset()
            control.addItems(items)
            self.guide_for = ch["id"]
            self.setProperty("GuideFor", str(ch["id"]))
        self._focus_visible(PROGRAMME)

    def _focus_visible(self, control_id):
        """Kodi applies a new <visible> state on its next frame; focusing earlier is ignored."""
        for _ in range(25):
            if xbmc.getCondVisibility(f"Control.IsVisible({control_id})"):
                break
            xbmc.sleep(20)
        self.setFocusId(control_id)

    def _programme_details(self):
        item = self.getControl(PROGRAMME).getSelectedItem()
        if item and item.getLabel():
            text = "\n\n".join(x for x in (item.getLabel(), item.getProperty("genre"),
                                          item.getProperty("plot") or "Pas de description.") if x)
            xbmcgui.Dialog().textviewer(item.getLabel2(), text)

    # ---------- playback ----------
    def _play(self, ch):
        playing = xbmc.getCondVisibility("Player.HasVideo")
        if playing and xbmc.getInfoLabel("VideoPlayer.ChannelName") == ch["name"]:
            xbmc.executebuiltin("ActivateWindow(fullscreenvideo)")
            return
        if self.player.isPlaying():
            self.player.stop()  # switching HLS streams without a stop has crashed inputstream.adaptive
            monitor, deadline = xbmc.Monitor(), time.time() + 5
            while self.player.isPlaying() and time.time() < deadline and not monitor.waitForAbort(0.1):
                pass
            xbmc.sleep(150)  # let the old stream's Stopped callback run before we wait for the new one
        self.opening = ch["name"]
        self.setProperty("Status", f"Ouverture de {ch['name']}…")
        try:
            core.rpc_call(rpc, "Player.Open", {"item": {"channelid": ch["id"]}})
        except core.RpcError as exc:
            log(exc, xbmc.LOGWARNING)
            self.on_failed()

    def on_started(self):
        self.clearProperty("Status")
        self.opening = ""
        if xbmcgui.getCurrentWindowId() == self.wid:
            xbmc.executebuiltin("ActivateWindow(fullscreenvideo)")

    def on_failed(self):
        if self.opening and not self.player.isPlaying():
            self.setProperty("Status", f"Lecture impossible : {self.opening}")
            self.opening = ""

    # ---------- remote ----------
    def _context_menu(self):
        ch = self._selected()
        if not ch:
            return
        fav = ch["name"].casefold() in self._fav_keys()
        choice = xbmcgui.Dialog().contextmenu(
            ["Regarder", "Retirer des favoris" if fav else "Ajouter aux favoris", "Programme de la chaîne"])
        if choice == 0:
            self._play(ch)
        elif choice == 1:
            self._toggle_favorite(ch)
        elif choice == 2:
            self._safe(self._show_programme)

    def onClick(self, control_id):
        if control_id == CHANNELS:
            ch = self._selected()
            if ch:
                self._play(ch)
        elif control_id == GROUPS:
            pos = self.getControl(GROUPS).getSelectedPosition()
            if 0 <= pos < len(self.groups):
                self._safe(lambda: self._show_group(self.groups[pos]))
                if self.channels:
                    self.setFocusId(CHANNELS)
        elif control_id == OPEN_PROGRAMME:
            self._safe(self._show_programme)
        elif control_id == PROGRAMME:
            self._programme_details()
        elif control_id == LIVE:
            self._safe(self._reload if self.view["kind"] == "group" else
                       lambda: self._show_group(core.default_group(self.groups)))
            self.setFocusId(CHANNELS if self.channels else LIVE)
        elif control_id == FAVS:
            self._safe(self._show_favorites)
            self.setFocusId(CHANNELS if self.channels else FAVS)
        elif control_id == SEARCH:
            query = xbmcgui.Dialog().input("Rechercher une chaîne", self.view.get("query", "")).strip()
            if query:
                self._safe(lambda: self._show_search(query))
                self.setFocusId(CHANNELS if self.channels else SEARCH)
        elif control_id == GROUPS_BTN:
            self.setFocusId(GROUPS if self.groups else GROUPS_BTN)
        elif control_id in (GUIDE, SETTINGS):
            self.resume_focus = control_id  # Kodi's full EPG grid / PVR settings; Back returns here
            xbmc.executebuiltin("ActivateWindow(TVGuide)" if control_id == GUIDE else "ActivateWindow(pvrsettings)")
        elif control_id == QUIT:
            self.close()

    def _focus_id(self):
        try:
            return self.getFocusId()
        except RuntimeError:  # nothing focused
            return 0

    def onAction(self, action):
        aid, focus = action.getId(), self._focus_id()
        if not focus and aid not in BACK:
            self.setFocusId(LIVE)  # an emptied list lost the focus: give the remote a way out
        elif aid in BACK:
            if focus == PROGRAMME:
                self.setFocusId(CHANNELS)
            elif focus in (CHANNELS, GROUPS):
                self.setFocusId(LIVE)
            else:
                self.close()
        elif aid in CONTEXT and focus == CHANNELS:
            self._context_menu()
        elif aid in INFO and focus == CHANNELS:
            self._safe(self._show_programme)
        elif aid in (DOWN, PAGE_DOWN) and focus == CHANNELS:
            control = self.getControl(CHANNELS)
            if control.getSelectedPosition() >= control.size() - 3:
                self._safe(self._more)


def main():
    running = HOME.getProperty(RUNNING)
    from_tile = "android" in sys.argv[1:]  # Addons.ExecuteAddon params of the Android TV launcher
    if from_tile or not running:
        HOME.setProperty(FROM_TILE, "true" if from_tile else "")
    if running:  # still open behind Kodi's Home or the video: bring it back, never stack a 2nd copy
        xbmc.executebuiltin(f"ActivateWindow({running})")
        return
    ui = TVHome("IPTV4FREE.xml", ROOT, "Default", "1080i")
    ui.boot()
    try:
        ui.doModal()
    finally:
        HOME.clearProperty(RUNNING)
        ui.player.ui = None
    del ui
    if HOME.getProperty(FROM_TILE) and not xbmc.Monitor().abortRequested():
        # Opened from the IPTV4FREE tile: leaving goes back to the TV home, not to Kodi's menus.
        HOME.clearProperty(FROM_TILE)
        xbmc.Player().stop()
        xbmc.executebuiltin("Minimize")


if __name__ == "__main__":
    main()

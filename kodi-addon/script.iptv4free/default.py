"""IPTV4FREE inside Kodi: independent, full-screen TV interface."""
import json
import os
import sys

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

ADDON = xbmcaddon.Addon()
ROOT = xbmcvfs.translatePath(ADDON.getAddonInfo("path"))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))
from core import RpcError, channel_groups, channels_for_group, default_group, filter_channels, rpc_call  # noqa: E402

CHANNELS, GROUPS, FAV, SEARCH, RELOAD = 500, 107, 108, 103, 109


class TVHome(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.groups = []
        self.all_channels = []
        self.filtered = []
        self.group_id = None
        self.favorites = set()
        self.search = ""
        self.only_favorites = False
        self.profile = xbmcvfs.translatePath(ADDON.getAddonInfo("profile"))
        self.fav_path = os.path.join(self.profile, "favorites.json")

    def onInit(self):
        # Keep the original text header until the supplied logo is packaged.
        has_logo = os.path.isfile(os.path.join(ROOT, "resources", "skins", "Default", "media", "iptv4free-logo.png"))
        self.setProperty("HasBrandLogo", "true" if has_logo else "false")
        self._load_favorites()
        self._refresh()
        self.setFocusId(CHANNELS if self.filtered else GROUPS)

    def _load_favorites(self):
        try:
            with open(self.fav_path, encoding="utf-8") as handle:
                data = json.load(handle)
            self.favorites = {int(x) for x in data if str(x).isdigit()}
        except (OSError, ValueError, TypeError):
            self.favorites = set()

    def _save_favorites(self):
        os.makedirs(self.profile, exist_ok=True)
        tmp = self.fav_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(sorted(self.favorites), handle)
        os.replace(tmp, self.fav_path)

    def _refresh(self):
        try:
            self.groups = channel_groups(xbmc.executeJSONRPC)
            group = next((g for g in self.groups if g["channelgroupid"] == self.group_id), None)
            group = group or default_group(self.groups)
            self.group_id = group["channelgroupid"] if group else None
            self.all_channels = channels_for_group(xbmc.executeJSONRPC, self.group_id) if group else []
            self.setProperty("Group", group.get("label", "Aucune chaîne") if group else "Aucune chaîne")
            self.setProperty("Status", "CHAÎNES DISPONIBLES" if group else "CONFIGUREZ IPTV SIMPLE CLIENT")
        except (RpcError, KeyError, TypeError) as exc:
            self.all_channels = []
            self.setProperty("Status", "PVR INDISPONIBLE")
            self.setProperty("Group", "Kodi PVR")
            xbmc.log(f"IPTV4FREE: {exc}", xbmc.LOGWARNING)
        self._render()

    def _render(self):
        self.filtered = filter_channels(self.all_channels, search=self.search,
                                        favorites=self.favorites, only_favorites=self.only_favorites)
        items = []
        for ch in self.filtered:
            li = xbmcgui.ListItem(label=ch["name"], label2=ch["now"])
            li.setArt({"thumb": ch["thumb"], "icon": ch["thumb"]})
            li.setProperty("number", ch["number"])
            li.setProperty("now", ch["now"])
            li.setProperty("star", "★" if ch["id"] in self.favorites else "")
            items.append(li)
        control = self.getControl(CHANNELS)
        control.reset()
        control.addItems(items)
        self.setProperty("Count", str(len(self.filtered)))
        self.setProperty("Filter", "FAVORIS" if self.only_favorites else ("RECHERCHE" if self.search else "EN DIRECT"))
        self.setProperty("Empty", "AUCUNE CHAÎNE TROUVÉE" if not items else "")

    def _selected(self):
        pos = self.getControl(CHANNELS).getSelectedPosition()
        return self.filtered[pos] if 0 <= pos < len(self.filtered) else None

    def onClick(self, control_id):
        if control_id == CHANNELS:
            selected = self._selected()
            if selected:
                try:
                    rpc_call(xbmc.executeJSONRPC, "Player.Open", {"item": {"channelid": selected["id"]}})
                    self.close()
                except RpcError as exc:
                    xbmcgui.Dialog().notification("IPTV4FREE", str(exc), xbmcgui.NOTIFICATION_ERROR)
        elif control_id == GROUPS:
            options = [g.get("label", "Groupe") for g in self.groups]
            if not options:
                return
            chosen = xbmcgui.Dialog().select("Groupes de chaînes", options)
            if chosen >= 0:
                self.group_id = self.groups[chosen]["channelgroupid"]
                self.search = ""
                self.only_favorites = False
                self._refresh()
                self.setFocusId(CHANNELS)
        elif control_id == FAV:
            selected = self._selected()
            if selected:
                if selected["id"] in self.favorites:
                    self.favorites.remove(selected["id"])
                else:
                    self.favorites.add(selected["id"])
                try:
                    self._save_favorites()
                except OSError as exc:
                    xbmc.log(f"IPTV4FREE favorites: {exc}", xbmc.LOGERROR)
                self._render()
                self.setFocusId(CHANNELS)
        elif control_id == SEARCH:
            value = xbmcgui.Dialog().input("Rechercher une chaîne", defaultt=self.search)
            self.search = value if value is not None else self.search
            self.only_favorites = False
            self._render()
            self.setFocusId(CHANNELS)
        elif control_id == RELOAD:
            self._refresh()
            self.setFocusId(CHANNELS)
        elif control_id == 102:
            self.only_favorites = not self.only_favorites
            self.search = ""
            self._render()
            self.setFocusId(CHANNELS)
        elif control_id in (101, 105, 104):
            target = {101: "TVGuide", 105: "pvrsettings", 104: "home"}[control_id]
            self.close()
            xbmc.executebuiltin(f"ActivateWindow({target})")
        elif control_id == 100:
            self.only_favorites = False
            self.search = ""
            self._render()
            self.setFocusId(CHANNELS)

    def onAction(self, action):
        if action.getId() in (9, 10, 92):  # Escape, PreviousMenu, NavigateBack
            self.close()


if __name__ == "__main__":
    ui = TVHome("IPTV4FREE.xml", ROOT, "Default", "1080i")
    ui.doModal()
    del ui

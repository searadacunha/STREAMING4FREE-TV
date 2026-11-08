"""IPTV4FREE background service: runs the local HLS relay while Kodi runs (resources/lib/relay.py).

Only channels that `iptv4free health` measured better through it point at 127.0.0.1:52180;
every other channel keeps its source URL and does not depend on this service.
"""
import os
import sys
import threading

import xbmc
import xbmcaddon
import xbmcvfs

ROOT = xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo("path"))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))
import relay  # noqa: E402


def main():
    relay.log = lambda message: xbmc.log(f"IPTV4FREE relay: {message}", xbmc.LOGWARNING)
    try:
        server = relay.serve()
    except OSError as exc:  # port taken: relayed channels will fail to open, the rest still play
        xbmc.log(f"IPTV4FREE: relay not started on 127.0.0.1:{relay.PORT}: {exc}", xbmc.LOGERROR)
        return
    threading.Thread(target=server.serve_forever, name="iptv4free-relay", daemon=True).start()
    xbmc.log(f"IPTV4FREE: relay listening on 127.0.0.1:{relay.PORT}", xbmc.LOGINFO)
    xbmc.Monitor().waitForAbort()
    server.shutdown()
    server.server_close()


if __name__ == "__main__":
    main()

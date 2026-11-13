#!/usr/bin/env python3
"""Probes the public IPTV playlists from this network and builds the hub's curated catalog.

Each candidate stream is opened the way the hub's player opens it (plain GET, platform user agent, no
Referer/Origin, no DRM key): playlist, best variant up to 1080p, then the first bytes of a media segment.
Only streams that answer from here end up in the catalog, so run it from the network the TV uses.

    python3 tools/probe_streams.py            # download, probe, write the catalog and the report
    python3 tools/probe_streams.py --reuse    # rebuild the outputs from the last probe (no network)

Writes hub/src/main/assets/catalog.json and docs/SOURCES.md. Standard library only.
"""
import argparse, collections, concurrent.futures, datetime, ipaddress, json, re, sys, threading, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "tools" / ".cache"
# what HttpURLConnection sends on the TV when the app sets no user agent (Media3's default)
UA = "Dalvik/2.1.0 (Linux; U; Android 12; Smart TV Pro Build/STT2.230203.001)"
LISTS = {
    "M3UPT": "https://m3upt.com/iptv",
    "Free-TV": "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8",
    "iptv-org": "https://iptv-org.github.io/iptv/index.m3u",
}
LANGS = {l: f"https://iptv-org.github.io/iptv/languages/{l}.m3u" for l in ("fra", "por", "eng", "spa")}
FREETV_GROUPS = {"France": "fra", "Portugal": "por", "Brazil": "por", "Belgium": "fra", "Switzerland": "fra",
                 "Luxembourg": "fra", "Monaco": "fra", "News": "eng", "Documentaries (EN)": "eng"}
THEMES = {"Sports": "sport", "Documentary": "docs", "Science": "docs", "Outdoor": "docs", "Travel": "docs",
          "Movies": "movies", "Classic": "movies", "Series": "series"}  # iptv-org category -> hub category
LIVE_ROWS = {"Kids": "kids", "Animation": "kids", "Family": "kids", "Music": "music", "News": "news"}
TIMEOUT = 8


def fetch(url, limit=262144):
    """GET like the hub: returns (status, final_url, content_type, first bytes)."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, r.geturl(), r.headers.get("Content-Type", ""), r.read(limit)
    except urllib.error.HTTPError as e:
        return e.code, url, "", b""
    except Exception as e:  # DNS, timeout, TLS, refused...
        return 0, url, type(e).__name__, b""


def parse_m3u(text, source):
    out, cur = [], None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#EXTINF"):
            attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', line))
            cur = {"name": line[line.find(",", line.rfind('"') + 1) + 1:].strip(), "source": source,
                   "id": attrs.get("tvg-id", ""), "logo": attrs.get("tvg-logo", ""), "group": attrs.get("group-title", ""),
                   "headers": "http-user-agent" in attrs or "http-referrer" in attrs, "drm": False}
        elif cur and line.startswith("#EXTVLCOPT:http-"):
            cur["headers"] = True
        elif cur and line.startswith("#KODIPROP") and "license" in line:
            cur["drm"] = True
        elif cur and line and not line.startswith("#"):
            cur["url"] = line
            out.append(cur)
            cur = None
    return out


def probe(url):
    """Returns a dict: status ('OK' or a failure class), detail, and quality when the playlist tells it."""
    host = urllib.parse.urlsplit(url).hostname or ""
    if re.search(r"(^|\.)(youtube\.com|youtu\.be)$", host):
        return {"status": "YOUTUBE", "detail": "opened by the YouTube app"}
    code, final, ctype, body = fetch(url)
    if code != 200:
        return {"status": {403: "HTTP403", 451: "HTTP403", 404: "HTTP404", 0: "UNREACHABLE"}.get(code, "HTTP" + str(code)), "detail": ctype or str(code)}
    head = body[:2048].lstrip(b"\xef\xbb\xbf \r\n\t")
    if head.startswith(b"#EXTM3U"):
        return probe_hls(final, body.decode("utf-8", "replace"))
    if b"<MPD" in body[:4096]:
        if b"ContentProtection" in body:
            return {"status": "DRM", "detail": "DASH with ContentProtection"}
        return {"status": "OK", "detail": "DASH manifest (segments not fetched)"}
    if ctype.startswith(("video/", "audio/", "application/octet-stream")) or head[:1] == b"G":
        return {"status": "OK", "detail": "direct " + (ctype or "MPEG-TS")}
    return {"status": "WEBPAGE", "detail": ctype[:40]}


def probe_hls(base, text, depth=0):
    quality = ""
    variants = re.findall(r"#EXT-X-STREAM-INF:([^\n]*)\n(?:#[^\n]*\n)*([^#\n][^\n]*)", text)
    if variants and depth == 0:
        def height(v):
            m = re.search(r"RESOLUTION=\d+x(\d+)", v[0])
            return int(m.group(1)) if m else 0
        def rate(v):
            m = re.search(r"[^-]BANDWIDTH=(\d+)", "," + v[0])
            return int(m.group(1)) if m else 0
        fit = [v for v in variants if height(v) <= 1080] or variants
        best = max(fit, key=lambda v: (height(v), rate(v)))
        codecs = re.search(r'CODECS="([^"]*)"', best[0])
        quality = " ".join(filter(None, [f"{height(best)}p" if height(best) else "", codecs.group(1) if codecs else ""]))
        code, final, ctype, body = fetch(urllib.parse.urljoin(base, best[1].strip()))
        if code != 200:
            return {"status": "HTTP403" if code in (403, 451) else "VARIANT" + str(code), "detail": "variant playlist", "quality": quality}
        r = probe_hls(final, body.decode("utf-8", "replace"), 1)
        r["quality"] = quality
        return r
    key = re.search(r"#EXT-X-KEY:METHOD=([A-Z0-9-]+)([^\n]*)", text)
    if key and key.group(1) not in ("NONE", "AES-128"):
        return {"status": "DRM", "detail": "HLS " + key.group(1)}  # SAMPLE-AES and friends: FairPlay or Widevine
    segments = [l.strip() for l in text.splitlines() if l.strip() and not l.startswith("#")]
    if not segments:
        return {"status": "EMPTY", "detail": "playlist without segments"}
    code, _, ctype, body = fetch(urllib.parse.urljoin(base, segments[-1]), 32768)
    if code != 200 or len(body) < 188:
        return {"status": "HTTP403" if code in (403, 451) else "SEGMENT" + str(code), "detail": "media segment"}
    return {"status": "OK", "detail": "HLS" + (" AES-128" if key and key.group(1) == "AES-128" else "")}


def probe_all(urls):
    """At most 2 requests at a time per host: lists point hundreds of channels at the same CDN."""
    gates = collections.defaultdict(lambda: threading.Semaphore(2))
    done = [0]
    def one(u):
        with gates[urllib.parse.urlsplit(u).hostname]:
            try:
                r = probe(u)
            except Exception as e:
                r = {"status": "ERROR", "detail": type(e).__name__}
        done[0] += 1
        if done[0] % 100 == 0:
            print(f"  {done[0]}/{len(urls)}", file=sys.stderr, flush=True)
        return u, r
    with concurrent.futures.ThreadPoolExecutor(48) as pool:
        return dict(pool.map(one, urls))


def bare_ip(url):
    try:
        ipaddress.ip_address(urllib.parse.urlsplit(url).hostname or "")
        return True
    except ValueError:
        return False


# iptv-org lists any public stream, re-streams of paid channels included: from it, only the free ad-supported (FAST)
# platforms and broadcast CDNs below are kept, or a channel served from a domain carrying its own name.
FAST_HOSTS = re.compile(r"(^|\.)(jmp2\.uk|amagi\.tv|wurl\.com|wurl\.tv|transmit\.live|getpublica\.com|frequency\.stream|"
                        r"otteravision\.com|tubi\.video|amazonaws\.com|zype\.com|klowdtv\.com|sofast\.tv|akamaized\.net|"
                        r"brightcove\.com|cloudfront\.net)$")
GENERIC_LABELS = {"live", "stream", "streams", "streaming", "hls", "cdn", "video", "edge", "origin", "media", "www", "play",
                  "player", "channels", "ott", "multimedia", "global", "prod", "linear", "tv", "web", "online", "server"}


def official(name, url):
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    if "premium" in host:  # a subscriber CDN reachable without login is not an authorised free stream
        return False
    if FAST_HOSTS.search(host):
        return True
    n = re.sub(r"[^a-z0-9]", "", name.lower())
    return any(len(l) >= 3 and l not in GENERIC_LABELS and (l in n or (len(n) >= 3 and n in l)) for l in host.split(".")[:-1])


def base_id(tvg_id):
    return tvg_id.split("@")[0]


def country(tvg_id):
    m = re.search(r"\.([a-z]{2})$", base_id(tvg_id))
    return m.group(1) if m else ""


def self_check():
    assert official("Pluto TV Cine", "https://jmp2.uk/plu-5f1.m3u8")
    assert official("France 24 Français", "https://live.france24.com/hls/live/x/master.m3u8")
    assert official("Real Madrid TV", "https://rmtv.akamaized.net/hls/live/2043153/rmtv-es-web/master.m3u8")
    assert not official("ESPN Latin America", "https://barinaslive1.boldmss.com/espn/index.m3u8")
    assert not official("Canal+ Sport (France)", "https://tv.streambox.fr/canalsport/index.m3u8")
    assert not official("Fox Sports News", "https://skynewsau-live-premium.akamaized.net/x.m3u8")
    assert not official("Live TV", "https://live.example.net/tv.m3u8")  # generic labels never count as the channel's own domain
    assert bare_ip("http://151.80.18.177:86/TF1_HD/index.m3u8") and not bare_ip("https://example.com/a.m3u8")


def main():
    self_check()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--reuse", action="store_true", help="rebuild the outputs from tools/.cache without any request")
    args = ap.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    texts = {}
    for name, url in {**LISTS, **LANGS}.items():
        f = CACHE / (name + ".m3u")
        if not args.reuse:
            code, _, _, body = fetch(url, 1 << 26)
            if code != 200 or not body.lstrip(b"\xef\xbb\xbf").startswith(b"#EXTM3U"):
                sys.exit(f"{name}: download failed ({code}) {url}")
            f.write_bytes(body)
        texts[name] = f.read_text("utf-8", "replace")
    lists = {n: parse_m3u(texts[n], n) for n in LISTS}
    lang_of = {}  # stream URL -> language, from iptv-org's per-language lists
    for l in LANGS:
        for c in parse_m3u(texts[l], l):
            lang_of.setdefault(c["url"], l)
    cats = collections.defaultdict(set)  # tvg-id without feed -> iptv-org categories
    for c in lists["iptv-org"]:
        cats[base_id(c["id"])].update(c["group"].split(";"))

    # candidates: Portuguese and French first, English and Spanish only for the themed categories
    cand = []
    for c in lists["M3UPT"]:
        if c["group"] == "TV":
            cand.append({**c, "lang": "por" if country(c["id"]) in ("pt", "br", "ao", "mz", "mo", "cv", "st", "gw", "tl") else
                         lang_of.get(c["url"]) or ("fra" if re.search(r"Fran[cç]ais|French|\bFR$", c["name"]) else "eng")})
    for c in lists["Free-TV"]:
        if c["group"] in FREETV_GROUPS:
            cand.append({**c, "lang": FREETV_GROUPS[c["group"]]})
    for c in lists["iptv-org"]:
        l = lang_of.get(c["url"])
        themed = any(k in THEMES for k in c["group"].split(";"))
        if l in ("fra", "por") or (l in ("eng", "spa") and themed):
            cand.append({**c, "lang": l})
    for c in cand:
        c["cats"] = sorted(cats.get(base_id(c["id"]), set()) | ({"News"} if c["group"] == "News" else set())
                           | ({"Documentary"} if c["group"].startswith("Documentaries") else set()))

    results_file = CACHE / "probe.json"
    if args.reuse:
        results = json.loads(results_file.read_text())
    else:
        urls = sorted({c["url"] for c in cand if c["url"].startswith("http") and not c["drm"]})
        print(f"probing {len(urls)} streams ({len(cand)} candidates)...", file=sys.stderr)
        results = probe_all(urls)
        results_file.write_text(json.dumps(results, indent=0, sort_keys=True))
    for c in cand:
        c["probe"] = {"status": "DRM", "detail": "DRM key in the playlist"} if c["drm"] else \
            results.get(c["url"], {"status": "UNSUPPORTED", "detail": c["url"].split(":")[0]})

    # catalog: working streams only, one per channel, official-looking hosts only
    def usable(c):
        # Free-TV states no license: its entries are probed for the report but not copied into the app, the TV downloads that list itself
        return c["probe"]["status"] in ("OK", "YOUTUBE") and not bare_ip(c["url"]) and c["source"] != "Free-TV" and \
            (c["source"] != "iptv-org" or official(c["name"], c["url"]))
    order = {"M3UPT": 0, "Free-TV": 1, "iptv-org": 2}
    seen, rows = set(), collections.defaultdict(list)
    for c in sorted((c for c in cand if usable(c)), key=lambda c: order[c["source"]]):  # stable: keeps each list's own order
        key = base_id(c["id"]).lower() or re.sub(r"\W+", "", c["name"].lower())
        if key in seen or c["url"] in seen:
            continue
        seen.update((key, c["url"]))
        theme = next((THEMES[k] for k in c["cats"] if k in THEMES), None)
        if theme:
            row = (theme, c["lang"] if c["lang"] in ("por", "fra") else "int")
        else:
            special = next((LIVE_ROWS[k] for k in c["cats"] if k in LIVE_ROWS), None)
            if c["lang"] not in ("por", "fra"):
                row = ("live", "news") if special == "news" else None  # foreign generalist channels stay in the IPTV section
            elif special in ("kids", "music"):
                row = ("live", special)
            elif {"Religious", "Shop", "Legislative"} & set(c["cats"]):
                row = ("live", "other")
            else:
                row = ("live", "pt" if country(c["id"]) == "pt" else "por" if c["lang"] == "por" else "fra")
        if row:
            # the stream answered from here: iptv-org's "[Geo-blocked]" and Free-TV's Ⓖ do not apply
            rows[row].append({"n": re.sub(r"\s*[ⓈⒼⓎⒹ]\s*|\s*\((?:\d{3,4}[pi]|[^)]*Geo-blocked[^)]*)\)|\s*\[Geo-blocked\]", "", c["name"]).strip(),
                              "u": c["url"], "l": c["logo"], "s": c["source"], "id": c["id"],
                              "q": c["probe"].get("quality", ""), "c": country(c["id"])})
    row_order = [("live", r) for r in ("pt", "fra", "por", "kids", "music", "news", "other")] + \
                [(t, r) for t in ("sport", "docs", "movies", "series") for r in ("por", "fra", "int")]
    today = datetime.date.today().isoformat()
    catalog = {"checked": today, "rows": [{"cat": t, "row": r, "items": rows[(t, r)]} for t, r in row_order if rows[(t, r)]]}
    out = ROOT / "hub" / "src" / "main" / "assets" / "catalog.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":")) + "\n")

    # report
    md = [f"# Free sources checked on {today}", "",
          "Generated by `tools/probe_streams.py` from the network the TV uses (Portugal). A stream counts as working when its",
          "playlist, its best variant up to 1080p and a media segment all answer to a plain request: no Referer, no browser",
          "user agent, no DRM key. Streams hosted on a bare IP address are left out of the catalog. M3UPT and Free-TV only",
          "list official free streams; iptv-org lists any public stream, so from it only free ad-supported platforms (Pluto TV,",
          "Samsung TV Plus, Amagi, Wurl...), broadcast CDNs and channels served from their own domain are kept. Free-TV states",
          "no license, so none of its entries is copied into the app: the TV downloads that list itself (IPTV section).", "",
          "| List | Entries | Probed | Working | Needs browser headers | DRM | In the catalog |", "|---|---|---|---|---|---|---|"]
    in_catalog = collections.Counter(i["s"] for r in catalog["rows"] for i in r["items"])
    for n in LISTS:
        mine = [c for c in cand if c["source"] == n]
        ok = sum(1 for c in mine if c["probe"]["status"] in ("OK", "YOUTUBE"))
        md.append(f"| {n} | {len(lists[n])} | {len(mine)} | {ok} | {sum(1 for c in mine if c['headers'] and c['probe']['status'] not in ('OK', 'YOUTUBE'))} "
                  f"| {sum(1 for c in mine if c['probe']['status'] == 'DRM')} | {in_catalog[n]} |")
    md += ["", "Probed = the Portuguese and French candidates, plus English and Spanish channels of the themed categories.", "",
           "## Failure classes", "", "| Result | Streams |", "|---|---|"]
    for status, n in collections.Counter(c["probe"]["status"] for c in cand).most_common():
        md.append(f"| {status} | {n} |")
    md += ["", "## Catalog rows", "", "| Category | Row | Channels |", "|---|---|---|"]
    md += [f"| {r['cat']} | {r['row']} | {len(r['items'])} |" for r in catalog["rows"]]
    md += ["", "## Portuguese and French channels that did not pass", "",
           "| Channel | List | Result | Declares browser headers |", "|---|---|---|---|"]
    for c in cand:
        if c["source"] != "iptv-org" and c["lang"] in ("por", "fra") and c["probe"]["status"] not in ("OK", "YOUTUBE"):
            md.append(f"| {c['name']} | {c['source']} | {c['probe']['status']} ({c['probe']['detail']}) | {'yes' if c['headers'] else 'no'} |")
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "SOURCES.md").write_text("\n".join(md) + "\n")
    total = sum(len(r["items"]) for r in catalog["rows"])
    assert total > 0, "empty catalog: probe failed or the lists changed format"
    print(f"catalog: {total} channels in {len(catalog['rows'])} rows -> {out.relative_to(ROOT)}; report -> docs/SOURCES.md")


if __name__ == "__main__":
    main()

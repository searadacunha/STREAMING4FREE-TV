<div align="center">

<img src="hub/src/main/res/drawable-xhdpi/banner.png" width="320" alt="STREAMING4FREE hub tile for the Android TV home screen" />
<img src="res/drawable-xhdpi/banner.png" width="320" alt="WATCHED tile for the Android TV home screen" />
<img src="cinefuse/res/drawable-xhdpi/banner.png" width="320" alt="CINEFUSE TV tile for the Android TV home screen" />

# STREAMING4FREE TV

**A free-TV hub and lightweight launchers for WATCHED and CINEFUSE, for Android TV.**  
One remote-friendly home for free live channels, free streaming apps and fullscreen ways to open [watched.cx](https://watched.cx) and [cinefuse.cc](https://cinefuse.cc) on your TV.

<p>
  <img alt="Android TV" src="https://img.shields.io/badge/Android_TV-3DDC84?style=flat-square&logo=android&logoColor=white">
  <img alt="Android 5.0+" src="https://img.shields.io/badge/Android-5.0%2B-1F2937?style=flat-square">
  <img alt="Java 17 build toolchain" src="https://img.shields.io/badge/Build-JDK_17-2563EB?style=flat-square">
  <img alt="Launchers without Gradle" src="https://img.shields.io/badge/Launchers-No_Gradle-1F2937?style=flat-square">
  <a href="LICENSE"><img alt="MIT License" src="https://img.shields.io/badge/License-MIT-22C55E?style=flat-square"></a>
</p>

<a href="#streaming4free-hub">Hub</a> ·
<a href="#what-it-does">Features</a> ·
<a href="#quick-start">Quick start</a> ·
<a href="#remote-controls">Controls</a> ·
<a href="#compatibility--limitations">Compatibility</a>

</div>

---

## Overview

STREAMING4FREE TV contains **a hub and two small, single-activity Android TV apps**. The hub gathers free live channels and the TV's streaming apps; WATCHED and CINEFUSE TV each open a website in a fullscreen Android WebView. All three appear on the TV home screen under their own name, icon and banner.

| App | Opens | Source | Package | APK |
|---|---|---|---|---|
| **STREAMING4FREE** | free channels and apps, see [below](#streaming4free-hub) | [`hub/`](hub/) | `com.local.streaming4free` | `hub/build/outputs/apk/release/streaming4free-hub-release.apk` |
| **WATCHED** | `https://watched.cx` | repository root | `com.local.watchedtv` | `build/watched-1.0.apk` |
| **CINEFUSE TV** | `https://cinefuse.cc` | [`cinefuse/`](cinefuse/) | `com.local.cinefusetv` | `cinefuse/build/cinefuse-tv-1.0.apk` |

The three apps have different packages and install side by side. The websites are operated by third parties and may provide TV-specific interfaces. **The hub plays public, free streams listed by M3UPT, iptv-org and Free-TV and opens the official apps; it hosts no media and supplies no subscription.**

## STREAMING4FREE hub

A Leanback home with a left menu: **Home, Movies, Series, Live TV, Sport, Documentaries, YouTube, IPTV, Favorites, Continue watching, Settings**. French and Portuguese, no account.

| | Feature | Details |
|:--:|---|---|
| 📡 | **Checked channels** | 781 free channels in 19 rows, each one probed from the TV's own network (Portugal) by [`tools/probe_streams.py`](tools/probe_streams.py): playlist, best variant and a media segment must answer without browser headers or DRM. Re-streams of paid channels are left out. Results: [`docs/SOURCES.md`](docs/SOURCES.md). |
| 📺 | **Free apps** | Plex, Rakuten TV, ARTE, RTP Play, TVI Player, RTVE Play, Red Bull TV, Viki and others: installed ones open directly, free ones not yet installed open their Play Store page. Paid or geo-blocked apps are labelled as such; Pluto TV and Tubi are left out because they refuse Portugal. |
| 🗂 | **Public playlists** | M3UPT, Free-TV and iptv-org, downloaded by the TV (kept 12 hours, last copy used offline) and browsed by country or category. |
| ▶️ | **Player** | Media3: HLS, DASH, MPEG-TS and MP4, hardware decoders first, quality from the bandwidth (or capped in Settings), audio and subtitle tracks, resume for films, reconnection on network errors, a clear message when a source refuses. |
| ⭐ | **Favorites and history** | Long press on OK adds or removes a favorite; Continue watching lists what was opened last. Kept on the TV only. |
| 🔎 | **Search** | One search over the apps, the checked channels and the three playlists, plus a hand-off to YouTube. Voice through the TV's own recognizer. |

## What it does

| | Feature | Details |
|:--:|---|---|
| 📺 | **TV launcher integration** | A dedicated tile for each app on the Android TV home screen. |
| ⛶ | **Fullscreen viewing** | Hosts the website in a fullscreen WebView, including its HTML5 fullscreen video view. |
| ⏯ | **Remote playback keys** | Handles Play, Pause, and Play/Pause for a video in the main webpage. |
| ↩ | **Predictable navigation** | Back closes fullscreen first, then navigates browser history, then exits the app. |
| 🔒 | **Restricted permissions** | Allows protected-media identification requests; denies other WebView permission requests, including camera and microphone. |
| 🖱 | **Cursor** (CINEFUSE TV) | A long press on OK shows a pointer for what the arrows cannot reach, such as search results and the player's buttons. |
| 🚫 | **Site-only navigation** (CINEFUSE TV) | Links and popups to other websites are blocked; video players inside iframes keep working. |
| 🛠 | **Simple source build** | Uses Android SDK command-line tools and JDK 17, with no Gradle project. |

## Quick start

### 1. Install the build tools

On **macOS**, using Homebrew:

```bash
brew install --cask android-commandlinetools
brew install openjdk@17 android-platform-tools
sdkmanager "build-tools;36.0.0" "platforms;android-36"
```

Required: **JDK 17**, Android SDK **Build Tools 36.0.0**, **Android API 36** platform, and **ADB** for installation.

### 2. Build the APK

From the repository root:

```bash
./build.sh
```

The script compiles, packages, aligns, and signs the app with your local **Android debug keystore**.

**Output:** `build/watched-1.0.apk`

For CINEFUSE TV, build from its folder:

```bash
cd cinefuse && ./build.sh
```

**Output:** `cinefuse/build/cinefuse-tv-1.0.apk`. Its build also runs a small self-check of the link rule (`test/SiteCheck.java`).

The hub uses the Gradle wrapper (it downloads Gradle and the libraries the first time):

```bash
cd hub && ./gradlew testDebugUnitTest assembleRelease
```

**Output:** `hub/build/outputs/apk/release/streaming4free-hub-release.apk`.

Or build the three apps and install them on the TV in one go: `tools/tv.sh install TV_IP` (`tools/tv.sh status TV_IP` shows what is installed).

### 3. Install on Android TV

Enable Android/ADB debugging on the TV and make sure the TV is reachable from your computer.

```bash
adb connect TV_IP:5555
adb -s TV_IP:5555 install -r build/watched-1.0.apk
adb -s TV_IP:5555 install -r cinefuse/build/cinefuse-tv-1.0.apk
adb -s TV_IP:5555 install -r hub/build/outputs/apk/release/streaming4free-hub-release.apk
```

Replace `TV_IP` with your television's IP address. Some devices require wireless-debugging pairing or a different port before ADB can connect.

Open **STREAMING4FREE**, **WATCHED** or **CINEFUSE TV** from the TV home screen.

## Remote controls

| Remote action | Behavior |
|---|---|
| **Back** | Exits fullscreen video, goes to the previous webpage, or leaves the app. In CINEFUSE TV it hides the cursor first. In the hub's player it returns to the hub at once. |
| **Long press OK** (hub) | Adds the channel or app under the focus to the favorites, or removes it. |
| **OK** (hub player) | Shows the controls: audio and subtitle tracks, quality, seek. After an error, tries again. |
| **Home** | Sends the app to the background; the WebView is paused. Reopening the app returns to the same page. |
| **Play / Pause / Play-Pause** | Controls the first ready HTML5 video on the top-level page. |
| **Long press OK** (CINEFUSE TV) | Shows or hides the cursor. Arrows move it, pushing it against an edge scrolls, OK clicks. |

> **Playback key limitation:** The media-key shortcut does not reach videos embedded inside third-party iframes. Playback and navigation still depend on the website's implementation.

## Build options

The build script assumes Homebrew's default macOS paths. Override them if needed:

```bash
ANDROID_HOME=/path/to/android-sdk JAVA_HOME=/path/to/jdk17 ./build.sh
```

You can also select a different installed SDK build-tool or platform version through `BUILD_TOOLS` and `PLATFORM`.

For WebView debugging during development only:

```bash
DEBUG=1 ./build.sh
```

A debuggable build also opens a start URL passed by ADB, for testing: `adb shell am start -n com.local.watchedtv/.MainActivity -d <url>`. Regular builds ignore that URL, because any app installed on the TV could send it.

**Do not keep the debuggable build installed** for regular use. To uninstall:

```bash
adb uninstall com.local.watchedtv
adb uninstall com.local.cinefusetv
```

## Project structure

```text
STREAMING4FREE-TV/
├── AndroidManifest.xml          # Android TV launcher metadata
├── src/com/local/watchedtv/
│   └── MainActivity.java        # WebView, fullscreen, remote keys
├── res/                         # TV banner and launcher icons
├── make_art.py                  # Regenerates the artwork (macOS + Pillow)
├── build.sh                     # Gradle-free build and APK signing
├── cinefuse/                    # CINEFUSE TV, same layout
│   ├── src/com/local/cinefusetv/MainActivity.java
│   ├── test/SiteCheck.java      # link rule self-check, run by build.sh
│   └── README.md                # CINEFUSE TV details
├── hub/                         # STREAMING4FREE hub (Kotlin, Leanback, Media3, Gradle wrapper)
│   ├── src/main/kotlin/…        # menu and pages, player, search, playlists, favorites
│   ├── src/main/assets/catalog.json  # checked channels, written by tools/probe_streams.py
│   └── make_art.py              # hub banner and icon, same look as the two launchers
├── tools/
│   ├── probe_streams.py         # probes the public playlists, writes the catalog and docs/SOURCES.md
│   └── tv.sh                    # build, install over Wi-Fi ADB, status
├── docs/SOURCES.md              # what works from the TV's network, and what does not
├── THIRD_PARTY_NOTICES.md
└── LICENSE
```

Refresh the checked channels from the network the TV uses with `python3 tools/probe_streams.py` (about 2,000 streams, a few minutes), then rebuild the hub.

The launcher artwork can be regenerated with `python3 make_art.py` (in the root or in `cinefuse/`) after installing **Pillow** on macOS.

## Compatibility & limitations

| Area | Current status |
|---|---|
| **Minimum Android version** | Android 5.0 / API 21; requires Android System WebView. |
| **Verified test device** | One Android 12 TV with WebView 156. |
| **Tested on that device** | TV launch, remote navigation, fullscreen, media keys, audio/subtitle selection, public HLS test streams at 1080p, and a Widevine L3 demo. |
| **Not verified** | Playback through the actual watched.cx website player; Linux builds; other TV models. |
| **CINEFUSE TV, tested** | On the same TV: launch, redirects, search, movie page, playback of one film, resume, media keys, ±10 s seek, VF/VOSTFR switch, player settings, fullscreen, Back, Home and reopening. |
| **CINEFUSE TV, not verified** | Login, series and episodes, subtitles, quality above 448p, live channels, watch parties. See [`cinefuse/README.md`](cinefuse/README.md). |
| **Device-specific limits** | The tested WebView did not decode AC-3/E-AC-3 audio and did not provide Widevine L1. |
| **Hub, tested** | On an Android TV 12 emulator (1080p): menu, rows, playback of a live channel, controls, Play/Pause, Back to the hub, favorites, history kept after a reinstall, playlists, groups, error message on a refused stream (about 4 s), YouTube hand-off and return, search, Portuguese. On the TCL Android 12 TV (32-bit Realtek): cold start 1.1 s, 37 MB of memory, a 720p live channel decoded by the hardware decoder (`OMX.realtek.video.decoder`, 25 frames/s), Play/Pause, Back to the hub, an official app opened from the hub. |
| **Hub, limits** | RTP 1, RTP 2, SIC and most French national channels refuse a plain player (browser headers or geo-blocking): use their official apps. The hub does not read other apps' content, progress or favorites; Android gives no access to them. |

The WebView enables JavaScript, DOM storage, and third-party cookies to support web playback. It blocks external application-link schemes such as `intent:` and `market:`; ordinary HTTP(S) links remain within the WebView.

## Content, affiliation & licensing

**STREAMING4FREE TV is an independent, open-source launcher.** It is **not affiliated with watched.cx or cinefuse.cc**, does not host or supply media, and does not assess the licensing or availability of content on those websites. Use third-party services in accordance with applicable laws and rights-holder terms.

The project's own code and artwork are released under the **MIT License**. See [LICENSE](LICENSE) and [Third-party notices](THIRD_PARTY_NOTICES.md).

---

<div align="center">
  <sub>Built for Android TV · Small codebase · Launchers without Gradle</sub>
</div>

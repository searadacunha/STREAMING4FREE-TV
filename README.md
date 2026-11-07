<div align="center">

<img src="res/drawable-xhdpi/banner.png" width="320" alt="WATCHED tile for the Android TV home screen" />

# STREAMING4FREE TV

**A lightweight Android TV launcher for WATCHED.**  
A fullscreen, remote-friendly way to open [watched.cx](https://watched.cx) on your TV — built from source without Gradle.

<p>
  <img alt="Android TV" src="https://img.shields.io/badge/Android_TV-3DDC84?style=flat-square&logo=android&logoColor=white">
  <img alt="Android 5.0+" src="https://img.shields.io/badge/Android-5.0%2B-1F2937?style=flat-square">
  <img alt="Java 17 build toolchain" src="https://img.shields.io/badge/Build-JDK_17-2563EB?style=flat-square">
  <img alt="No Gradle" src="https://img.shields.io/badge/Gradle-Not_required-1F2937?style=flat-square">
  <a href="LICENSE"><img alt="MIT License" src="https://img.shields.io/badge/License-MIT-22C55E?style=flat-square"></a>
</p>

<a href="#what-it-does">Features</a> ·
<a href="#quick-start">Quick start</a> ·
<a href="#remote-controls">Controls</a> ·
<a href="#compatibility--limitations">Compatibility</a>

</div>

---

## Overview

STREAMING4FREE TV is a **small, single-activity Android TV app** that opens `https://watched.cx` in a fullscreen Android WebView. It appears on the TV home screen under the **WATCHED** name and uses the project's own launcher icon and banner.

The website is operated by a third party and may provide a TV-specific interface. **This repository is a launcher, not an IPTV player or a source of channels, subscriptions, or streaming content.**

## What it does

| | Feature | Details |
|:--:|---|---|
| 📺 | **TV launcher integration** | A dedicated WATCHED tile on the Android TV home screen. |
| ⛶ | **Fullscreen viewing** | Hosts the website in a fullscreen WebView, including its HTML5 fullscreen video view. |
| ⏯ | **Remote playback keys** | Handles Play, Pause, and Play/Pause for a video in the main webpage. |
| ↩ | **Predictable navigation** | Back closes fullscreen first, then navigates browser history, then exits the app. |
| 🔒 | **Restricted permissions** | Allows protected-media identification requests; denies other WebView permission requests, including camera and microphone. |
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

### 3. Install on Android TV

Enable Android/ADB debugging on the TV and make sure the TV is reachable from your computer.

```bash
adb connect TV_IP:5555
adb -s TV_IP:5555 install -r build/watched-1.0.apk
```

Replace `TV_IP` with your television's IP address. Some devices require wireless-debugging pairing or a different port before ADB can connect.

Open **WATCHED** from the TV home screen.

## Remote controls

| Remote action | Behavior |
|---|---|
| **Back** | Exits fullscreen video, goes to the previous webpage, or leaves the app. |
| **Home** | Sends the app to the background; the WebView is paused. |
| **Play / Pause / Play-Pause** | Controls the first ready HTML5 video on the top-level page. |

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

**Do not keep the debuggable build installed** for regular use. To uninstall:

```bash
adb uninstall com.local.watchedtv
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
├── THIRD_PARTY_NOTICES.md
└── LICENSE
```

The existing launcher artwork can be regenerated with `python3 make_art.py` after installing **Pillow** on macOS.

## Compatibility & limitations

| Area | Current status |
|---|---|
| **Minimum Android version** | Android 5.0 / API 21; requires Android System WebView. |
| **Verified test device** | One Android 12 TV with WebView 156. |
| **Tested on that device** | TV launch, remote navigation, fullscreen, media keys, audio/subtitle selection, public HLS test streams at 1080p, and a Widevine L3 demo. |
| **Not verified** | Playback through the actual watched.cx website player; Linux builds; other TV models. |
| **Device-specific limits** | The tested WebView did not decode AC-3/E-AC-3 audio and did not provide Widevine L1. |

The WebView enables JavaScript, DOM storage, and third-party cookies to support web playback. It blocks external application-link schemes such as `intent:` and `market:`; ordinary HTTP(S) links remain within the WebView.

## Content, affiliation & licensing

**STREAMING4FREE TV is an independent, open-source launcher.** It is **not affiliated with watched.cx**, does not host or supply media, and does not assess the licensing or availability of content on that website. Use third-party services in accordance with applicable laws and rights-holder terms.

The project's own code and artwork are released under the **MIT License**. See [LICENSE](LICENSE) and [Third-party notices](THIRD_PARTY_NOTICES.md).

---

<div align="center">
  <sub>Built for Android TV · Small codebase · No Gradle</sub>
</div>

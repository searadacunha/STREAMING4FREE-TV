#!/usr/bin/env bash
# One entry point for reproducible IPTV + streaming checks and builds.
# Run from any working directory: bash tools/build-all.sh [check|build]
set -euo pipefail
cd "$(dirname "$0")/.."

require() {
  command -v "$1" >/dev/null 2>&1 || { echo "Missing $1. See README build requirements." >&2; exit 2; }
}

case "${1:-build}" in
  check)
    require python3
    echo "[1/2] IPTV4FREE stable Python tests"
    (cd iptv && PYTHONPATH=src python3 -m pytest -q)
    echo "[2/2] Kodi/Android IPTV UI preview tests"
    (cd iptv-tv-preview && PYTHONPATH=src python3 -m pytest -q tests/test_tv_ui.py tests/test_android_launcher.py)
    ;;
  build)
    require python3
    require gradle
    echo "[1/3] STREAMING4FREE hub, WATCHED and CINEFUSE APKs"
    bash tools/tv.sh build
    echo "[2/3] IPTV4FREE Kodi add-on ZIP"
    python3 iptv-tv-preview/scripts/build_addon.py
    echo "[3/3] IPTV4FREE Android TV preview APK"
    python3 iptv-tv-preview/scripts/prepare_android_launcher.py
    (cd iptv-tv-preview/android-tv-launcher && gradle --no-daemon :app:assembleDebug)
    echo "Build output locations:"
    ls -lh build/watched-1.0.apk cinefuse/build/cinefuse-tv-1.0.apk \
      hub/build/outputs/apk/release/streaming4free-hub-release.apk \
      iptv-tv-preview/dist/script.iptv4free-0.3.1.zip \
      iptv-tv-preview/android-tv-launcher/app/build/outputs/apk/debug/app-debug.apk
    echo "Note: debug-signed IPTV APK may not update an app signed with a different key."
    ;;
  *)
    echo "Usage: bash tools/build-all.sh [check|build]" >&2
    exit 2
    ;;
esac

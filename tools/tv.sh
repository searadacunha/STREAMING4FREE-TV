#!/usr/bin/env bash
# Rebuilds the three apps and (re)installs them on an Android TV over Wi-Fi ADB.
# Updates keep each app's data (adb install -r); nothing is ever uninstalled.
#
#   tools/tv.sh build                  build WATCHED, CINEFUSE TV and the STREAMING4FREE hub (with its unit tests)
#   tools/tv.sh install TV_IP[:PORT]   build, then install the three APKs on the TV
#   tools/tv.sh status  TV_IP[:PORT]   Android version, CPU, free space, installed versions, apps on the home screen
#
# First connection: enable network debugging on the TV. With Android 11+ "wireless debugging", pair once with
# `adb pair TV_IP:PAIRING_PORT CODE` (both shown on the TV), then use the connection port it shows as TV_IP:PORT.
set -euo pipefail
cd "$(dirname "$0")/.."
export JAVA_HOME=${JAVA_HOME:-/opt/homebrew/opt/openjdk@17}
APKS=(build/watched-1.0.apk cinefuse/build/cinefuse-tv-1.0.apk hub/build/outputs/apk/release/streaming4free-hub-release.apk)
PKGS=(com.local.watchedtv com.local.cinefusetv com.local.streaming4free)

build() {
  ./build.sh
  (cd cinefuse && ./build.sh)
  (cd hub && ./gradlew --no-daemon -q testDebugUnitTest assembleRelease)
  ls -l "${APKS[@]}"
}

connect() {
  [[ -n ${1:-} ]] || { echo "usage: $0 $CMD TV_IP[:PORT]" >&2; exit 2; }
  TV=$1
  [[ $TV == *:* ]] || TV=$TV:5555
  adb connect "$TV" >/dev/null || true
  if [[ $(adb -s "$TV" get-state 2>/dev/null) != device ]]; then
    echo "$TV: not connected or not authorised. Accept the prompt on the TV, or pair first: adb pair TV_IP:PORT CODE" >&2
    exit 1
  fi
}

status() {
  adb -s "$TV" shell 'echo "Android $(getprop ro.build.version.release) (API $(getprop ro.build.version.sdk)), CPU $(getprop ro.product.cpu.abilist), $(getprop ro.product.manufacturer) $(getprop ro.product.model)"; df -h /data | tail -1'
  for p in "${PKGS[@]}"; do
    printf '%-26s %s\n' "$p" "$(adb -s "$TV" shell dumpsys package "$p" | grep -m1 -o 'versionName=.*' || echo 'not installed')"
  done
  echo "Apps on the TV home screen:"
  adb -s "$TV" shell cmd package query-activities --brief -a android.intent.action.MAIN -c android.intent.category.LEANBACK_LAUNCHER \
    | grep / | sed 's,/.*,,; s/^ *//' | sort -u | tr '\n' ' '
  echo
}

CMD=${1:-}
case $CMD in
  build) build ;;
  install) connect "${2:-}"; build; for a in "${APKS[@]}"; do adb -s "$TV" install -r "$a"; done; status ;;
  status) connect "${2:-}"; status ;;
  *) sed -n '2,11p' "$0"; exit 2 ;;
esac

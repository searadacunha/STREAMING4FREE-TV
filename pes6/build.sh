#!/usr/bin/env bash
# Separate PES 2006 launcher; no game files are packaged.
set -euo pipefail
cd "$(dirname "$0")"
SDK=${ANDROID_HOME:-/opt/homebrew/share/android-commandlinetools}
BT="$SDK/build-tools/${BUILD_TOOLS:-36.0.0}"
JAR="$SDK/platforms/android-${PLATFORM:-36}/android.jar"
export JAVA_HOME=${JAVA_HOME:-/opt/homebrew/opt/openjdk@17}
export PATH="$JAVA_HOME/bin:$PATH"
KS="$HOME/.android/debug.keystore"
OUT=build
python3 art/make_art.py
for exe in aapt2 d8 zipalign apksigner; do
  [[ -x "$BT/$exe" ]] || { echo "Missing $BT/$exe" >&2; exit 1; }
done
[[ -f "$JAR" ]] || { echo "Missing $JAR" >&2; exit 1; }
rm -rf "$OUT"
mkdir -p "$OUT/classes" "$OUT/dex"
if [[ ! -f "$KS" ]]; then
  mkdir -p "$(dirname "$KS")"
  keytool -genkeypair -keystore "$KS" -storepass android \
    -alias androiddebugkey -keypass android -keyalg RSA -keysize 2048 \
    -validity 10000 -dname "CN=Android Debug,O=Android,C=US"
fi
"$BT/aapt2" compile --dir res -o "$OUT/res.zip"
"$BT/aapt2" link -I "$JAR" --manifest AndroidManifest.xml -A assets \
  -o "$OUT/unsigned.apk" "$OUT/res.zip" --auto-add-overlay ${DEBUG:+--debug-mode}
javac -source 8 -target 8 -Xlint:-options -bootclasspath "$JAR" \
  -d "$OUT/classes" src/com/local/pes6tv/*.java
"$BT/d8" --release --min-api 23 --lib "$JAR" --output "$OUT/dex" \
  "$OUT/classes"/com/local/pes6tv/*.class
(cd "$OUT/dex" && zip -q ../unsigned.apk classes.dex)
"$BT/zipalign" -f -p 4 "$OUT/unsigned.apk" "$OUT/aligned.apk"
"$BT/apksigner" sign --ks "$KS" --ks-pass pass:android \
  --ks-key-alias androiddebugkey --key-pass pass:android \
  --out "$OUT/pes2006-tv-1.0.apk" "$OUT/aligned.apk"
"$BT/apksigner" verify "$OUT/pes2006-tv-1.0.apk"
ls -lh "$OUT/pes2006-tv-1.0.apk"

# PES 2006 · Android TV

Dedicated **PES 2006** launcher tile for Android TV/Google TV. Opens
[OptiJuegos' PES 6 Web Online](https://pes6.optijuegos.net/) full-screen
from the TV home screen. Original WATCHED and CINEFUSE apps are unchanged.

The site serves the PSP game recompiled to WebAssembly and documents
WebGL2, USB/Bluetooth gamepad support, saved games and online play. The
game runs on the remote site, **not inside this repository or APK**.

## Build and install

Same JDK 17 and Android SDK command-line tools as the root app
(Android platform 36, build-tools 36.0.0), plus Python 3 + Pillow.

```bash
python3 -m pip install Pillow
cd pes6
./build.sh
adb connect TV_IP:5555
adb install -r build/pes2006-tv-1.0.apk
```

On Android TV/Google TV, a **PES 2006** tile appears with the black/gold PES 6
logo. Installation from GitHub Actions artifacts is also possible.
The APK is signed with the builder's debug key; packages from different
builders cannot be installed as an update over each other.

## GameSir / gamepad setup

1. Pair the GameSir to the **TV**, not the phone. Use Android/HID gamepad
   mode (Bluetooth, USB, or the controller's supported 2.4 GHz dongle).
   Avoid a touch-only G-Touch/V-Touch mode. Model-specific combinations
   depend on your GameSir version.
2. Open PES 2006 and press a gamepad button to activate detection.
   In the website's **Controles → Mandos**, choose **Autoconfigurar**
   if necessary; check A/B/X/Y, D-pad, both sticks and triggers.
3. The app forwards Android gamepad keys and axes to the WebView, and
   provides a fallback Gamepad API shim when the browser returns no pads.
   Native Gamepad API has priority. Press the **TV remote's MENU** key for
   Reload, Android/controller/WebGL2 diagnostics, or external browser.
   The controller's B/BACK must not close the application.
4. For slow TVs: choose **WebGL2**, 1x internal resolution, 30 FPS,
   and no optional commentary. The WebView must support WebGL2 with
   hardware acceleration; compatibility and FPS are device-dependent.
   A newer TV WebView, or an external Chromium browser, may be needed.

The GameSir's model and the television chipset/Android WebView version
are not known, so **physical compatibility and gameplay FPS have not been
verified on the actual TV**. An APK installing successfully is not a
substitute for a real match test. Save data stays with this app's WebView
and can be lost on uninstall.

## Sources considered

- [CloudJoy](https://github.com/scionoftech/cloudjoy) — Android TV
  WebView with native controller passthrough/back handling (MIT).
- [Sofa TV Browser](https://github.com/sonalder-darlene/sofa-tv-browser) —
  remote/gamepad TV navigation; a fallback browser, GPL-3.0.
- [PES6ANDROIDPORT](https://github.com/haveniiii/PES6ANDROIDPORT) —
  alternative native Android project, but requires a user-provided ISO;
  **not** equivalent to opening the OptiJuegos web version.

This wrapper is unofficial, not affiliated with Konami or OptiJuegos,
and does not redistribute game assets. Logo artwork is a manually drawn
stylistic representation, not an official asset.

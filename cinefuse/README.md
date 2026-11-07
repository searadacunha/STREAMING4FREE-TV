# CINEFUSE TV

**A Cinefuse launcher tile for Android TV.**

<img src="res/drawable-xhdpi/banner.png" width="320" alt="CINEFUSE TV tile for the Android TV home screen" />

CINEFUSE TV is a small Android TV app, shown on the home screen as CINEFUSE TV, that opens
https://cinefuse.cc full screen in the TV's WebView. Like WATCHED, it is one activity,
built from source without Gradle and installed over Wi-Fi with `adb`. cinefuse.cc is a
third-party website, not affiliated with this project.

```bash
cd cinefuse && ./build.sh        # build/cinefuse-tv-1.0.apk, package com.local.cinefusetv
adb -s TV_IP:5555 install -r build/cinefuse-tv-1.0.apk
```

Requirements, build options and installation are in the [main README](../README.md).
`DEBUG=1 ./build.sh` builds a debuggable variant for WebView DevTools; do not keep it
installed.

## Features

- The remote's arrows move between the site's links and buttons, OK selects.
- **Cursor**: a long press on OK shows a pointer for what the arrows cannot reach (search
  results, the player's settings and fullscreen buttons). Arrows move it, pushing it
  against an edge scrolls the page, OK clicks, Back or a long press on OK hides it.
- Back closes the cursor, then fullscreen, then goes to the previous page, then to the TV
  home screen. Home pauses the page, so the sound stops; reopening the app returns to the
  same page.
- The remote's Play/Pause, Play and Pause keys control the page's video.
- Navigation stays on `cinefuse.<any TLD>`: links and popups to other sites (ads) are
  blocked with a short message, links to other apps (`intent:`, `market:`) are ignored.
  Video players inside iframes keep their own hosts.
- Only the protected-content permission (Widevine) is granted; microphone and camera
  requests are denied.
- If the TV was offline when a page loaded, reopening the app reloads it.

## Site address

`HOME` in `MainActivity.java` is `https://cinefuse.cc`. On 7 Nov 2026 it redirected
cinefuse.cc → cinefuse.icu → cinefuse.mom → cinefuse.sbs, and the site's address page
(cinefuse.wiki, `/api/site`) gave the same final address. If the site moves to a domain
not named `cinefuse.<TLD>`, the redirect is blocked: change `HOME` and `isSite()`, then
rebuild.

## Changes made to the site's behaviour

Two, both needed for the remote:

- `Android TV` is appended to the WebView user agent. The site switches to its TV mode only
  for user agents naming a TV; without it, playback starts behind three ad popups.
- A one-rule stylesheet is added to cinefuse pages: the site's TV stylesheet sets
  `position: relative` on the focused element, which collapsed the player to 0 px high
  when the remote focused it (sound without picture).

## Limitations

- Tested on one TV (TCL, Google TV, Android 12, WebView 156) on 7 Nov 2026: launch from the
  home screen, redirects, search, movie page, playback of one film, resume prompt,
  Play/Pause keys, ±10 s seek, VF/VOSTFR switch, settings menu, fullscreen, Back, Home and
  reopening. Not tested: login, series and episodes, subtitles (none on the tested film),
  quality above 448p, live channels, watch parties.
- On the search page the TV keyboard opens as soon as the search field is focused and takes
  the arrow keys; press Back to close it, then use the cursor to pick a result.
- That TV's WebView cannot decode AC-3 or E-AC-3 audio and has no Widevine L1.
- Building on Linux was not tested.
- This project does not host or provide any content and does not verify the rights to the
  content of cinefuse.cc. Users are responsible for complying with the laws and rights
  holders' terms that apply to them.

## License

MIT. See [LICENSE](../LICENSE) and [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).

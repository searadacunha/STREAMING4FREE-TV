# IPTV4FREE official logo

`IPTV4FREE-original.png` is the official logo supplied by the project owner: white "IPTV4 FREE" lettering, electric-blue globe, orbit and stars. Keep it exactly as it is: do not recolour, redraw, regenerate or reshape it.

- Size: 1536 × 1024, PNG, RGBA (transparent background)
- SHA-256: `895a691c86d56185416257ce026c540e49b49aaedf438c98c5242dcee60485bf`

`python3 scripts/prepare_branding.py` (needs Pillow, build time only) produces, in the Kodi add-on:

- `resources/skins/Default/media/iptv4free-logo.png`: a byte-for-byte copy, shown on screen;
- `icon.png`: a transparent 512 × 512 square, declared in `addon.xml`. Only invisible margins (alpha ≤ 1/255) are trimmed, then the logo is scaled proportionally and centred.

`tests/test_tv_ui.py` checks the SHA-256 above, the copy, the icon and their presence in the ZIP.

# dmgbuild settings: uv run python -m dmgbuild -s packaging/dmg_settings.py -D app=<path to .app> "CAESAR Course Check" out.dmg
import os

app = defines["app"]  # noqa: F821  (dmgbuild injects `defines`)
appname = os.path.basename(app)

format = "UDZO"
files = [app]
symlinks = {"Applications": "/Applications"}
icon = "assets/AppIcon.icns"
background = "assets/dmg-bg.tiff"
window_rect = ((220, 140), (600, 380))
icon_size = 112
text_size = 13
icon_locations = {appname: (150, 175), "Applications": (450, 175)}

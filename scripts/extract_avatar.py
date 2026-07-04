"""One-off helper: extract Alpha Wang avatar from Jira check HTML."""
from __future__ import annotations

import base64
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT.parent / "Jira check" / "index.html"
OUT = ROOT / "app" / "assets" / "alpha_wang.jpg"

html = SRC.read_text(encoding="utf-8")
match = re.search(r'src="(data:image/jpeg;base64,[^"]+)"', html)
if not match:
    raise SystemExit("avatar data URI not found")
data = base64.b64decode(match.group(1).split(",", 1)[1])
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_bytes(data)
print(f"wrote {OUT} ({len(data)} bytes)")

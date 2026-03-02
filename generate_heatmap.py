import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

BASE = os.environ.get("SHIKI_BASE", "https://shikimori.one")
USER_ID = os.environ.get("SHIKI_USER_ID") or (sys.argv[1] if len(sys.argv) > 1 else None)

DAYS = int(os.environ.get("DAYS", "365"))        # сколько дней рисовать
LIMIT = int(os.environ.get("LIMIT", "100"))      # limit на страницу истории
MAX_PAGES = int(os.environ.get("MAX_PAGES", "200"))

OUT_DIR = os.environ.get("OUT_DIR", "dist")
OUT_FILE = os.environ.get("OUT_FILE", "heatmap.svg")

if not USER_ID:
    raise SystemExit("Set SHIKI_USER_ID env var (numeric)")

def fetch_json(url: str):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "shiki-heatmap-gh-actions/1.0",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        txt = r.read().decode("utf-8", errors="replace")
    if txt.lstrip().startswith("<"):
        raise RuntimeError("Got HTML instead of JSON (API error/protection).")
    return json.loads(txt)

today = datetime.now(timezone.utc).date()
start = today - timedelta(days=DAYS - 1)

# ключи дат
counts = { (start + timedelta(days=i)).isoformat(): 0 for i in range(DAYS) }

# грузим историю постранично
page = 1
while page <= MAX_PAGES:
    url = f"{BASE}/api/users/{USER_ID}/history?limit={LIMIT}&page={page}"
    items = fetch_json(url)
    if not items:
        break

    for it in items:
        created_at = it.get("created_at")
        if not created_at:
            continue
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        d = dt.date().isoformat()
        if d in counts:
            counts[d] += 1

    # ускорение: как только ушли раньше start — выходим
    last_created = items[-1].get("created_at")
    if last_created:
        last_dt = datetime.fromisoformat(last_created.replace("Z", "+00:00"))
        if last_dt.date() < start:
            break

    page += 1

# уровни “GitHub-like”
def level(v: int) -> int:
    if v <= 0: return 0
    if v == 1: return 1
    if v <= 3: return 2
    if v <= 6: return 3
    return 4

palette = ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"]

cell = 10
gap = 3
rows = 7  # 7 дней недели

# Чтобы было похоже на GitHub: строки сверху вниз = Sun..Sat
# Выравниваем сетку по дню недели старта (UTC)
def utc_dow(iso_date: str) -> int:
    d = datetime.fromisoformat(iso_date).date()
    # Python weekday: Mon=0..Sun=6, нам надо Sun=0..Sat=6
    return (d.weekday() + 1) % 7

start_dow = utc_dow(start.isoformat())
cols = (start_dow + DAYS + 6) // 7

width = cols * cell + (cols - 1) * gap
height = rows * cell + (rows - 1) * gap

rects = []
for i in range(DAYS):
    day = start + timedelta(days=i)
    iso = day.isoformat()
    idx = start_dow + i
    col = idx // 7
    row = idx % 7

    x = col * (cell + gap)
    y = row * (cell + gap)

    v = int(counts[iso])
    fill = palette[level(v)]

    # tooltip
    title = f"{iso}: {v} действий"

    rects.append(
        f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" ry="2" fill="{fill}">'
        f'<title>{title}</title>'
        f'</rect>'
    )

svg = (
f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
f'viewBox="0 0 {width} {height}" role="img" aria-label="Shikimori activity heatmap">\n'
+ "\n".join(rects) +
"\n</svg>\n"
)

os.makedirs(OUT_DIR, exist_ok=True)
out_path = os.path.join(OUT_DIR, OUT_FILE)
with open(out_path, "w", encoding="utf-8") as f:
    f.write(svg)

print(f"Wrote {out_path} (days={DAYS})")

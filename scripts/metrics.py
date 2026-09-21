"""Generate github-metrics.svg from a user's public repos (stdlib only)."""
import json, os, sys, urllib.request
from collections import Counter
from datetime import datetime, timezone
from html import escape

USER = "emuiga"
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")

def api(path):
    req = urllib.request.Request(f"https://api.github.com{path}",
                                 headers={"Accept": "application/vnd.github+json"})
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

user = api(f"/users/{USER}")
repos, page = [], 1
while True:
    chunk = api(f"/users/{USER}/repos?per_page=100&type=owner&page={page}")
    repos += chunk
    if len(chunk) < 100:
        break
    page += 1

SKIP_REPOS = {"KensHRBackend"}  # has a committed virtualenv
SKIP_LANGS = {"C++", "C", "Cython", "CMake", "Jupyter Notebook"}  # vendored / generated code
own = [r for r in repos if not r["fork"]]
langs = Counter()
for r in own:
    if r["name"] in SKIP_REPOS:
        continue
    try:
        langs.update({k: v for k, v in api(f"/repos/{USER}/{r['name']}/languages").items() if k not in SKIP_LANGS})
    except Exception as e:
        print(f"skip {r['name']}: {e}", file=sys.stderr)

years = (datetime.now(timezone.utc) - datetime.fromisoformat(user["created_at"].replace("Z", "+00:00"))).days // 365
stats = [
    (len(own), "public repos"),
    (len(langs), "languages"),
    (user["followers"], "followers"),
    (years, "years on GitHub"),
]

PALETTE = ["#8abf98", "#2e6849", "#c4935a", "#e86c3d", "#15616d", "#5f9f7a"]
total = sum(langs.values()) or 1
top = langs.most_common(6)

W, H, PAD = 495, 250, 24
out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="-apple-system,Segoe UI,Helvetica,Arial,sans-serif">',
       f'<rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="10" fill="#0e1a14" stroke="#2e6849"/>',
       f'<text x="{PAD}" y="38" font-size="18" font-weight="600" fill="#8abf98">Steve Muiga · GitHub</text>']
colw = (W - 2 * PAD) / 4
for i, (n, label) in enumerate(stats):
    x = PAD + i * colw
    out.append(f'<text x="{x}" y="80" font-size="26" font-weight="700" fill="#ffffff">{n}</text>')
    out.append(f'<text x="{x}" y="98" font-size="11" fill="#8abf98">{escape(label)}</text>')
out.append(f'<text x="{PAD}" y="132" font-size="12" font-weight="600" fill="#c4935a">MOST USED LANGUAGES</text>')
x = PAD; barw = W - 2 * PAD
out.append(f'<g>')
for i, (name, b) in enumerate(top):
    w = barw * b / total
    out.append(f'<rect x="{x:.1f}" y="142" width="{w:.1f}" height="8" fill="{PALETTE[i]}"/>')
    x += w
out.append('</g>')
for i, (name, b) in enumerate(top):
    cx = PAD + (i % 2) * (barw / 2); cy = 176 + (i // 2) * 22
    out.append(f'<circle cx="{cx+5}" cy="{cy-4}" r="5" fill="{PALETTE[i]}"/>')
    out.append(f'<text x="{cx+16}" y="{cy}" font-size="12" fill="#ffffff">{escape(name)}</text>')
    out.append(f'<text x="{cx+16+7*len(name)+10}" y="{cy}" font-size="12" fill="#8abf98">{100*b/total:.1f}%</text>')
out.append('</svg>')
open("github-metrics.svg", "w").write("\n".join(out))
print(stats, top)

"""Generate github-metrics.svg for a user: contributions, streaks, top language, orgs (stdlib only)."""
import json, os, sys, urllib.request
from collections import Counter
from datetime import date, timedelta
from html import escape

USER = "emuiga"
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
SKIP_REPOS = {"KensHRBackend"}  # has a committed virtualenv
SKIP_LANGS = {"C++", "C", "Cython", "CMake", "Jupyter Notebook"}  # vendored / generated code

def request(url, body=None):
    req = urllib.request.Request(url, data=body, headers={"Accept": "application/vnd.github+json"})
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def api(path):
    return request(f"https://api.github.com{path}")

def graphql(query):
    return request("https://api.github.com/graphql", json.dumps({"query": query}).encode())["data"]

# languages across own public repos
repos, page = [], 1
while True:
    chunk = api(f"/users/{USER}/repos?per_page=100&type=owner&page={page}")
    repos += chunk
    if len(chunk) < 100:
        break
    page += 1
langs = Counter()
for r in repos:
    if r["fork"] or r["name"] in SKIP_REPOS:
        continue
    try:
        langs.update({k: v for k, v in api(f"/repos/{USER}/{r['name']}/languages").items() if k not in SKIP_LANGS})
    except Exception as e:
        print(f"skip {r['name']}: {e}", file=sys.stderr)

# contributions, streaks, orgs
data = graphql('{user(login:"%s"){organizations(first:20){nodes{name login}} contributionsCollection{contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}' % USER)["user"]
cal = data["contributionsCollection"]["contributionCalendar"]
days = sorted((date.fromisoformat(d["date"]), d["contributionCount"]) for w in cal["weeks"] for d in w["contributionDays"])
active = {d for d, c in days if c > 0}
longest = run = 0
prev = None
for d, c in days:
    run = run + 1 if c > 0 and prev is not None and prev == d - timedelta(days=1) and (d - timedelta(days=1)) in active else (1 if c > 0 else 0)
    longest = max(longest, run)
    prev = d
today = days[-1][0]
cur, d = 0, today if today in active else today - timedelta(days=1)  # today may not have activity yet
while d in active:
    cur += 1
    d -= timedelta(days=1)
orgs = [o["name"] or o["login"] for o in data["organizations"]["nodes"]]

PALETTE = ["#e86c3d", "#8abf98", "#2e6849", "#c4935a", "#5f9f7a", "#15616d"]
total = sum(langs.values()) or 1
top = langs.most_common(6)

W, PAD, GAP = 495, 20, 10
BG, TILE, SAGE, ORANGE, BEIGE = "#042f2e", "#0a423d", "#8abf98", "#e86c3d", "#f0e6d2"
out = []

# stat tiles
tw = (W - 2 * PAD - 2 * GAP) / 3
for i, (n, label) in enumerate([(cal["totalContributions"], "contributions, past year"), (cur, "day streak"), (longest, "longest streak")]):
    x = PAD + i * (tw + GAP)
    out.append(f'<rect x="{x:.1f}" y="{PAD}" width="{tw:.1f}" height="74" rx="8" fill="{TILE}"/>')
    out.append(f'<text x="{x+14:.1f}" y="{PAD+38}" font-size="26" font-weight="700" fill="{ORANGE}">{n:,}</text>')
    out.append(f'<text x="{x+14:.1f}" y="{PAD+58}" font-size="11" fill="{SAGE}">{label}</text>')

# top language tile with proportion bar
y = PAD + 74 + GAP
out.append(f'<rect x="{PAD}" y="{y}" width="{W-2*PAD}" height="78" rx="8" fill="{TILE}"/>')
out.append(f'<text x="{PAD+14}" y="{y+24}" font-size="11" font-weight="600" fill="{ORANGE}">TOP LANGUAGE</text>')
name, b = top[0]
out.append(f'<text x="{PAD+14}" y="{y+50}" font-size="20" font-weight="700" fill="{BEIGE}">{escape(name)}</text>')
out.append(f'<text x="{PAD+14+11*len(name)+18}" y="{y+50}" font-size="14" fill="{SAGE}">{100*b/total:.0f}%</text>')
x, barw = PAD + 14, W - 2 * PAD - 28
for i, (n, v) in enumerate(top):
    w = barw * v / total
    out.append(f'<rect x="{x:.1f}" y="{y+60}" width="{w:.1f}" height="6" fill="{PALETTE[i]}"/>')
    x += w

# organizations as solid pills
y += 78 + GAP
out.append(f'<rect x="{PAD}" y="{y}" width="{W-2*PAD}" height="__H__" rx="8" fill="{TILE}"/>')
out.append(f'<text x="{PAD+14}" y="{y+24}" font-size="11" font-weight="600" fill="{ORANGE}">ORGANIZATIONS</text>')
px, py = PAD + 14, y + 36
for o in orgs:
    pw = 8 * len(o) + 22
    if px + pw > W - PAD - 14:
        px, py = PAD + 14, py + 32
    out.append(f'<rect x="{px}" y="{py}" width="{pw}" height="24" rx="12" fill="#2e6849"/>')
    out.append(f'<text x="{px+11}" y="{py+16}" font-size="12" fill="{BEIGE}">{escape(o)}</text>')
    px += pw + 8
orgh = py + 24 + 14 - y
H = y + orgh + PAD
body = "\n".join(out).replace("__H__", str(orgh))
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
       f'font-family="-apple-system,Segoe UI,Helvetica,Arial,sans-serif"><rect width="{W}" height="{H}" rx="12" fill="{BG}"/>\n{body}\n</svg>')
open("github-metrics.svg", "w").write(svg)
print(cal["totalContributions"], cur, longest, top[0], orgs)

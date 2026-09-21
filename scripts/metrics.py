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

# contributions (all time + past year), streaks, orgs
years = graphql('{user(login:"%s"){contributionsCollection{contributionYears}}}' % USER)["user"]["contributionsCollection"]["contributionYears"]
YEAR_Q = ' '.join(
    'y%d: contributionsCollection(from:"%d-01-01T00:00:00Z", to:"%d-12-31T23:59:59Z"){contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}' % (y, y, y)
    for y in years)
data = graphql('{user(login:"%s"){organizations(first:20){nodes{name login}} %s recent: contributionsCollection{contributionCalendar{totalContributions}}}}' % (USER, YEAR_Q))["user"]
days = {}
for y in years:
    for w in data[f"y{y}"]["contributionCalendar"]["weeks"]:
        for d in w["contributionDays"]:
            days[date.fromisoformat(d["date"])] = d["contributionCount"]
all_time = sum(data[f"y{y}"]["contributionCalendar"]["totalContributions"] for y in years)
past_year = data["recent"]["contributionCalendar"]["totalContributions"]
active = {d for d, c in days.items() if c > 0}
longest = run = 0
for d in sorted(active):
    run = run + 1 if d - timedelta(days=1) in active else 1
    longest = max(longest, run)
today = max(days)
cur, d = 0, today if today in active else today - timedelta(days=1)  # today may not have activity yet
while d in active:
    cur += 1
    d -= timedelta(days=1)
orgs = [o["name"] or o["login"] for o in data["organizations"]["nodes"]]

PALETTE = ["#e86c3d", "#8abf98", "#2e6849", "#c4935a", "#5f9f7a", "#15616d"]
total = sum(langs.values()) or 1
top = langs.most_common(6)
ICONS = json.load(open(os.path.join(os.path.dirname(__file__), "icons.json")))

# Square badge blocks: dark icon tile + solid green label, full width, no rounding.
W, GAP, H1 = 830, 6, 56
DARK, GREEN, SAGE, ORANGE, WHITE = "#0e1a14", "#2e6849", "#8abf98", "#e86c3d", "#ffffff"
out = []

def icon(name, x, y, size=24):
    k = size / 16
    paths = "".join(f'<path d="{d}"/>' for d in ICONS[name])
    return f'<g transform="translate({x},{y}) scale({k})" fill="{ORANGE}">{paths}</g>'

def block(x, y, w, h, ico, label, value=None, extra=""):
    o = [f'<rect x="{x}" y="{y}" width="{h}" height="{h}" fill="{DARK}"/>', icon(ico, x + (h - 24) / 2, y + (h - 24) / 2),
         f'<rect x="{x+h}" y="{y}" width="{w-h}" height="{h}" fill="{GREEN}"/>']
    tx = x + h + 16
    if value is None:
        o.append(f'<text x="{tx}" y="{y+h/2+5}" font-size="12" font-weight="700" letter-spacing=".5" fill="{WHITE}">{escape(label.upper())}</text>')
    else:
        o.append(f'<text x="{tx}" y="{y+22}" font-size="11" font-weight="600" letter-spacing=".5" fill="{SAGE}">{escape(label.upper())}</text>')
        o.append(f'<text x="{tx}" y="{y+45}" font-size="22" font-weight="700" fill="{WHITE}">{value}</text>')
    return o + [extra]

bw = (W - 3 * GAP) / 4
for i, (ico, label, val) in enumerate([("graph", "All time", f"{all_time:,}"), ("calendar", "Past year", f"{past_year:,}"),
                                        ("flame", "Streak", f"{cur} days"), ("trophy", "Best streak", f"{longest} days")]):
    out += block(i * (bw + GAP), 0, bw, H1, ico, label, val)

# top language, with proportion bar
y = H1 + GAP
name, b = top[0]
out += block(0, y, W, H1, "code", "Top language", escape(name))
out.append(f'<text x="{H1 + 16 + 13 * len(name) + 12}" y="{y+45}" font-size="14" font-weight="700" fill="{SAGE}">{100*b/total:.0f}%</text>')
x, bx, barw = 0, W * 0.5, W * 0.5 - 16
for i, (n, v) in enumerate(top):
    w = barw * v / total
    out.append(f'<rect x="{bx + x:.1f}" y="{y + H1/2 - 4}" width="{w:.1f}" height="8" fill="{PALETTE[i]}"/>')
    x += w

# organizations: same square badge, wrapped across the full width
y += H1 + GAP
ox, oy, OH = 0, y, 40
for o in orgs:
    ow = OH + 32 + 10.5 * len(o)
    if ox + ow > W:
        ox, oy = 0, oy + OH + GAP
    out += block(ox, oy, ow, OH, "organization", o)
    ox += ow + GAP
H = oy + OH
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
       f'font-family="-apple-system,Segoe UI,Helvetica,Arial,sans-serif">\n' + "\n".join(out) + "\n</svg>")
open("github-metrics.svg", "w").write(svg)
print(all_time, past_year, cur, longest, top[0], orgs)

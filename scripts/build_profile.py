"""Builds the profile's SVG panels (dark + light) from live GitHub data.

Design: an engineering spec sheet. Big Shoulders Display + IBM Plex Mono
(both OFL, subset and embedded), safety amber and deep green as solid fills,
square corners, hard rules. No gradients, blur, glass or fade-ins.

Run with GITHUB_TOKEN set (the contribution calendar needs it).
Only the Python standard library is used.
"""

import base64
import datetime as dt
import json
import os
import re
import urllib.parse
import urllib.request
from html import escape

USER = "itsvishalyadav"
HERE = os.path.dirname(os.path.abspath(__file__))
VENDOR = os.path.join(HERE, "vendor")
OUT = os.path.join(HERE, "..", "assets")
W = 1000

THEMES = {
    "dark": {
        "bg": "#121310", "ink": "#ECEAE3", "muted": "#8C8A80", "rule": "#34352F",
        "amber": "#F2B705", "on_amber": "#121310", "green": "#4C9A6F",
        "num": "#F2B705", "empty": "#1E1F1A",
        "heat": ["#1E1F1A", "#1E4D38", "#2F6B4F", "#4C9A6F", "#F2B705"],
    },
    "light": {
        "bg": "#ECEBE5", "ink": "#141510", "muted": "#6E6C63", "rule": "#C9C7BE",
        "amber": "#F2B705", "on_amber": "#141510", "green": "#1F5A3F",
        "num": "#141510", "empty": "#DEDCD4",
        "heat": ["#DEDCD4", "#B9D3C2", "#6FA486", "#1F5A3F", "#E0A800"],
    },
}

DISPLAY = "'BSD',Impact,'Arial Narrow',sans-serif"
MONO = "'PLX','IBM Plex Mono',Consolas,monospace"


# ------------------------------------------------------------------ data

def _req(url, body=None):
    req = urllib.request.Request(url, data=body, headers={"Accept": "application/vnd.github+json"})
    tok = os.environ.get("GITHUB_TOKEN")
    if tok:
        req.add_header("Authorization", "Bearer " + tok)
    if body:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)


def search(q, per_page=1, sort=None):
    url = "https://api.github.com/search/issues?per_page=%d&q=%s" % (per_page, urllib.parse.quote(q))
    if sort:
        url += "&sort=%s&order=desc" % sort
    return _req(url)


def repo_counts(q):
    counts, page = {}, 1
    while page <= 10:
        items = _req("https://api.github.com/search/issues?per_page=100&page=%d&q=%s" % (page, urllib.parse.quote(q)))["items"]
        for i in items:
            r = i["repository_url"].rsplit("/", 1)[1]
            counts[r] = counts.get(r, 0) + 1
        if len(items) < 100:
            break
        page += 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


def clean_title(t):
    t = re.sub(r"^\w+(\([^)]*\))?!?:\s*", "", t)  # drop "fix(scope): "
    return t[:1].upper() + t[1:]


def recent_merged(n=10):
    q = f"author:{USER} is:pr is:merged -user:{USER} -user:piyxsh31"
    items = search(q, per_page=40, sort="updated")["items"]
    out = []
    for i in items:
        merged = (i.get("pull_request") or {}).get("merged_at")
        if merged:
            repo = i["repository_url"].rsplit("/", 1)[1]
            out.append((merged, f"{repo}#{i['number']}", clean_title(i["title"])))
    out.sort(reverse=True)
    return [(r, t) for _, r, t in out[:n]]


def calendar():
    q = {"query": 'query{user(login:"%s"){contributionsCollection{contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}' % USER}
    cal = _req("https://api.github.com/graphql", json.dumps(q).encode())["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    return cal["totalContributions"], [[(d["date"], d["contributionCount"]) for d in w["contributionDays"]] for w in cal["weeks"]]


def gather():
    ks_q = f"author:{USER} org:kubescape is:pr is:merged"
    try:
        total, weeks = calendar()
    except Exception as e:  # keep the last heatmap if the calendar can't be read
        print("calendar unavailable:", e)
        total, weeks = None, None
    d = {
        "ks": search(ks_q)["total_count"],
        "ks_by_repo": repo_counts(ks_q),
        "kv": search(f"author:{USER} org:kyverno is:pr is:merged")["total_count"],
        "issues": search(f"author:{USER} is:issue -user:{USER}")["total_count"],
        "recent": recent_merged(),
        "contrib_total": total,
        "weeks": weeks,
        "rev": dt.date.today().strftime("%Y.%m.%d"),
    }
    d["ks_repos"] = len(d["ks_by_repo"])
    return d


# ------------------------------------------------------------------ pieces

def b64(path):
    with open(os.path.join(VENDOR, path), "rb") as f:
        return base64.b64encode(f.read()).decode()


FACES = {
    "bsd800": ("BSD", 800, "bsd-800.woff"),
    "bsd400": ("BSD", 400, "bsd-400.woff"),
    "plx400": ("PLX", 400, "plex-400.woff"),
    "plx600": ("PLX", 600, "plex-600.woff"),
}


def fonts(*keys):
    css = "".join(
        "@font-face{font-family:'%s';font-weight:%d;src:url(data:font/woff;base64,%s) format('woff')}" % (
            FACES[k][0], FACES[k][1], b64(FACES[k][2])) for k in keys)
    return f"<style>{css}</style>"


def logo(name, x, y, size):
    return (f'<image x="{x}" y="{y}" width="{size}" height="{size}" '
            f'href="data:image/svg+xml;base64,{b64(name)}"/>')


def hazard(t, y, h, uid):
    return (f'<defs><pattern id="hz{uid}" width="22" height="22" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
            f'<rect width="22" height="22" fill="{t["on_amber"]}"/><rect width="11" height="22" fill="{t["amber"]}"/></pattern></defs>'
            f'<rect x="0" y="{y}" width="{W}" height="{h}" fill="url(#hz{uid})"/>')


def crop_marks(t, w, h, inset=14, size=14):
    c = t["muted"]
    p = []
    for (x, y, dx, dy) in [(inset, inset, 1, 1), (w - inset, inset, -1, 1), (inset, h - inset, 1, -1), (w - inset, h - inset, -1, -1)]:
        p.append(f'M{x} {y + dy*size}V{y}H{x + dx*size}')
    return f'<path d="{" ".join(p)}" fill="none" stroke="{c}" stroke-width="1"/>'


def label(t, x, y, text, anchor="start", color=None, size=11.5):
    return (f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-family="{MONO}" font-weight="600" font-size="{size}" '
            f'letter-spacing="1.6" fill="{color or t["muted"]}">{escape(text)}</text>')


def svg(h, body, aria):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" role="img" '
            f'aria-label="{escape(aria)}">{body}</svg>\n')


# ------------------------------------------------------------------ panels

def masthead(t, d):
    h = 452
    rows = [
        ("BASE", "ABV-IIITM Gwalior · B.Tech CSE"),
        ("NEXT", "Google · SWE intern · summer 2027"),
        ("WORKS ON", "admission control · runtime detection"),
        ("LANGUAGES", "Go · C++ · Python · TypeScript"),
    ]
    spec, y = [], 286
    for k, v in rows:
        spec.append(label(t, 560, y, k))
        spec.append(f'<text x="672" y="{y}" font-family="{MONO}" font-size="14" fill="{t["ink"]}">{escape(v)}</text>')
        spec.append(f'<line x1="560" y1="{y + 13}" x2="960" y2="{y + 13}" stroke="{t["rule"]}"/>')
        y += 32
    body = fonts("bsd800", "plx400", "plx600") + f"""
<rect width="{W}" height="{h}" fill="{t['bg']}"/>
{crop_marks(t, W, h - 30)}
{label(t, 40, 52, "ITSVISHALYADAV / PROFILE")}
{label(t, 960, 52, "REV. " + d['rev'], anchor="end")}
<line x1="40" y1="66" x2="960" y2="66" stroke="{t['ink']}" stroke-width="2"/>
<text x="34" y="236" font-family="{DISPLAY}" font-weight="800" font-size="196" letter-spacing="-2" fill="{t['ink']}">VISHAL</text>
<text x="34" y="400" font-family="{DISPLAY}" font-weight="800" font-size="196" letter-spacing="-2" fill="none" stroke="{t['ink']}" stroke-width="2.2">YADAV</text>
<rect x="560" y="96" width="400" height="150" fill="{t['amber']}"/>
<text x="578" y="122" font-family="{MONO}" font-weight="600" font-size="11.5" letter-spacing="1.6" fill="{t['on_amber']}">ROLE</text>
<text x="576" y="180" font-family="{DISPLAY}" font-weight="800" font-size="46" fill="{t['on_amber']}">SYSTEMS ENGINEER</text>
<text x="576" y="228" font-family="{DISPLAY}" font-weight="800" font-size="46" fill="{t['on_amber']}">KUBERNETES SECURITY</text>
{''.join(spec)}
{hazard(t, h - 30, 30, "m")}"""
    return svg(h, body, "Vishal Yadav, systems engineer, Kubernetes security")


def ledger(t, d):
    h = 300
    cols = [
        (40, 420, "kubescape-icon-color.svg", "KUBESCAPE · CNCF", str(d["ks"]), t["num"], f"merged pull requests across {d['ks_repos']} repositories"),
        (440, 720, "kyverno-icon-color.svg", "KYVERNO · CNCF", str(d["kv"]), t["ink"], "merged pull requests"),
        (740, 960, None, "BUG REPORTS", str(d["issues"]), t["green"], "issues filed"),
    ]
    parts = []
    for x0, x1, lg, lab, num, color, cap in cols:
        lx = x0
        if lg:
            parts.append(logo(lg, x0, 96, 30))
            lx = x0 + 42
        parts.append(label(t, lx, 116, lab, color=t["ink"]))
        parts.append(f'<text x="{x0 - 6}" y="240" font-family="{DISPLAY}" font-weight="800" font-size="150" fill="{color}">{num}</text>')
        parts.append(f'<text x="{x0}" y="272" font-family="{MONO}" font-size="13.5" fill="{t["muted"]}">{escape(cap)}</text>')
        if x1 < 960:
            parts.append(f'<line x1="{x1}" y1="92" x2="{x1}" y2="276" stroke="{t["rule"]}"/>')
    body = fonts("bsd800", "plx400", "plx600") + f"""
<rect width="{W}" height="{h}" fill="{t['bg']}"/>
{label(t, 40, 44, "OPEN SOURCE")}
{label(t, 960, 44, "LIVE COUNT · UPDATED DAILY", anchor="end")}
<line x1="40" y1="58" x2="960" y2="58" stroke="{t['ink']}" stroke-width="2"/>
{''.join(parts)}"""
    return svg(h, body, f"{d['ks']} merged Kubescape PRs, {d['kv']} merged Kyverno PRs, {d['issues']} issues filed")


def ticker(t, d):
    h = 58
    items = "     ▸     ".join(f"{r}  {title}" for r, title in d["recent"]) + "     ▸     "
    cw = 0.6 * 15  # IBM Plex Mono advance width at 15px
    run = len(items) * cw
    body = fonts("plx400", "plx600") + f"""
<rect width="{W}" height="{h}" fill="{t['bg']}"/>
<line x1="0" y1="0.5" x2="{W}" y2="0.5" stroke="{t['rule']}"/><line x1="0" y1="{h-0.5}" x2="{W}" y2="{h-0.5}" stroke="{t['rule']}"/>
<g>
  <animateTransform attributeName="transform" type="translate" from="0 0" to="{-run:.1f} 0" dur="{run/38:.0f}s" repeatCount="indefinite"/>
  <text x="196" y="35" font-family="{MONO}" font-size="15" fill="{t['ink']}" xml:space="preserve">{escape(items)}{escape(items)}</text>
</g>
<rect x="0" y="0" width="176" height="{h}" fill="{t['amber']}"/>
<text x="20" y="35" font-family="{MONO}" font-weight="600" font-size="13" letter-spacing="1.8" fill="{t['on_amber']}">JUST MERGED</text>
<rect x="148" y="24" width="9" height="9" fill="{t['on_amber']}"><animate attributeName="opacity" values="1;0.15;1" dur="1.6s" repeatCount="indefinite"/></rect>"""
    return svg(h, body, "Recently merged pull requests")


WORK = [
    ("kubescape/storage", "528", "Mid-path wildcards kept as written",
     "Saved profiles were silently widened, so file-access alerts went quiet."),
    ("kubescape/node-agent", "1175", "Argv boundaries in the CEL cache key",
     "Two different command lines shared one cached verdict, letting R0040 be bypassed."),
    ("kubescape/operator", "583", "Legacy AppArmor annotation blocked",
     "A remediation patch could still switch a workload to unconfined."),
    ("kubescape/storage", "533", "Network peers no longer merged by mistake",
     "Hand-written profiles lost allowed IPs, DNS names and pod selectors on save."),
]


def work_row(t, repo, num, title, why, last):
    h = 104
    body = fonts("bsd800", "plx400", "plx600") + f"""
<rect width="{W}" height="{h}" fill="{t['bg']}"/>
{label(t, 40, 34, repo.upper())}
<text x="36" y="84" font-family="{DISPLAY}" font-weight="800" font-size="52" fill="{t['num']}">#{num}</text>
<text x="300" y="50" font-family="{DISPLAY}" font-weight="800" font-size="34" fill="{t['ink']}">{escape(title)}</text>
<text x="300" y="80" font-family="{MONO}" font-size="13.5" fill="{t['muted']}">{escape(why)}</text>
<rect x="890" y="25" width="8" height="8" fill="{t['green']}"/>
{label(t, 960, 34, "MERGED", anchor="end", color=t['green'])}
<line x1="40" y1="{h - 1}" x2="960" y2="{h - 1}" stroke="{t['ink'] if last else t['rule']}" stroke-width="{2 if last else 1}"/>"""
    return svg(h, body, f"{repo}#{num}: {title}")


def heatmap(t, d):
    weeks = d["weeks"][-53:]
    cell, gap, x0, y0 = 13, 4, 84, 96
    h = y0 + 7 * (cell + gap) + 44
    counts = sorted(c for w in weeks for _, c in w if c > 0)
    q = [counts[int(len(counts) * f)] if counts else 1 for f in (0.25, 0.5, 0.9)]

    def level(c):
        if c == 0:
            return 0
        return 1 + sum(c > v for v in q)

    cells, months, last_month = [], [], None
    for wi, week in enumerate(weeks):
        for date, c in week:
            di = dt.date.fromisoformat(date).weekday()  # Mon=0
            row = (di + 1) % 7  # Sunday first, like GitHub
            x, y = x0 + wi * (cell + gap), y0 + row * (cell + gap)
            cells.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" fill="{t["heat"][level(c)]}"><title>{date}: {c}</title></rect>')
        m = dt.date.fromisoformat(week[0][0]).strftime("%b").upper()
        if m != last_month and wi < len(weeks) - 2:
            months.append(f'<text x="{x0 + wi * (cell + gap)}" y="{y0 - 12}" font-family="{MONO}" font-size="10.5" fill="{t["muted"]}">{m}</text>')
            last_month = m
    days = "".join(f'<text x="{x0 - 12}" y="{y0 + r * (cell + gap) + 10}" text-anchor="end" font-family="{MONO}" font-size="10.5" fill="{t["muted"]}">{n}</text>'
                   for r, n in ((1, "MON"), (3, "WED"), (5, "FRI")))
    legend = "".join(f'<rect x="{860 + i*(cell+3)}" y="{h - 26}" width="{cell}" height="{cell}" fill="{c}"/>' for i, c in enumerate(t["heat"]))
    body = fonts("bsd800", "plx400", "plx600") + f"""
<rect width="{W}" height="{h}" fill="{t['bg']}"/>
{label(t, 40, 44, "CONTRIBUTIONS · LAST 12 MONTHS")}
<text x="960" y="50" text-anchor="end" font-family="{DISPLAY}" font-weight="800" font-size="42" fill="{t['num']}">{d['contrib_total']:,}</text>
<line x1="40" y1="58" x2="960" y2="58" stroke="{t['ink']}" stroke-width="2"/>
{''.join(months)}{days}{''.join(cells)}
<text x="852" y="{h - 15}" text-anchor="end" font-family="{MONO}" font-size="10.5" fill="{t['muted']}">LESS</text>{legend}
<text x="{860 + 5*(cell+3) + 4}" y="{h - 15}" font-family="{MONO}" font-size="10.5" fill="{t['muted']}">MORE</text>"""
    return svg(h, body, f"{d['contrib_total']} contributions in the last year")


def about(t, d):
    h = 330
    quote = ["I find logic bugs in", "Kubernetes security tools,", "prove them with a failing", "test, and fix them."]
    para = [
        "Most of my work is in Go: admission",
        "controllers, policy engines, runtime",
        "detection rules and the storage that",
        "holds learned behaviour. I check the",
        "code against the spec or a sibling",
        "path, write the failing test first,",
        "then the smallest fix, and show the",
        "before/after in every pull request.",
    ]
    q = "".join(f'<text x="40" y="{118 + i*42}" font-family="{DISPLAY}" font-weight="800" font-size="40" fill="{t["ink"]}">{escape(l)}</text>' for i, l in enumerate(quote))
    p = "".join(f'<text x="640" y="{104 + i*22}" font-family="{MONO}" font-size="13" fill="{t["muted"]}">{escape(l)}</text>' for i, l in enumerate(para))
    body = fonts("bsd800", "plx400", "plx600") + f"""
<rect width="{W}" height="{h}" fill="{t['bg']}"/>
{label(t, 40, 44, "ABOUT")}
{label(t, 960, 44, "SYSTEMS · SECURITY · OPEN SOURCE", anchor="end")}
<line x1="40" y1="58" x2="960" y2="58" stroke="{t['ink']}" stroke-width="2"/>
<rect x="40" y="82" width="8" height="166" fill="{t['amber']}"/>
<g transform="translate(26 0)">{q}</g>
<line x1="612" y1="86" x2="612" y2="262" stroke="{t['rule']}"/>
{p}
<text x="66" y="300" font-family="{MONO}" font-weight="600" font-size="12.5" letter-spacing="1.4" fill="{t['green']}">● OPEN TO SECURITY &amp; INFRASTRUCTURE WORK · CNCF MENTORSHIPS</text>"""
    return svg(h, body, "About: finds and fixes logic bugs in Kubernetes security tools")


def repo_bars(t, d):
    rows = d["ks_by_repo"][:8]
    top = rows[0][1] if rows else 1
    h = 92 + len(rows) * 34 + 26
    bars = []
    for i, (repo, n) in enumerate(rows):
        y = 96 + i * 34
        w = max(6, 560 * n / top)
        bars.append(f'<text x="40" y="{y + 15}" font-family="{MONO}" font-size="13.5" fill="{t["ink"]}">{escape(repo)}</text>')
        bars.append(f'<rect x="290" y="{y}" width="{w:.0f}" height="20" fill="{t["amber"] if i == 0 else t["green"]}"/>')
        bars.append(f'<text x="{290 + w + 12:.0f}" y="{y + 16}" font-family="{DISPLAY}" font-weight="800" font-size="22" fill="{t["ink"]}">{n}</text>')
    rest = sum(n for _, n in d["ks_by_repo"][8:])
    more = f"+ {rest} more across {len(d['ks_by_repo']) - 8} other repositories" if rest else ""
    body = fonts("bsd800", "plx400", "plx600") + f"""
<rect width="{W}" height="{h}" fill="{t['bg']}"/>
{label(t, 40, 44, "KUBESCAPE · WHERE THE MERGED PRS LANDED")}
{label(t, 960, 44, "LIVE · BY REPOSITORY", anchor="end")}
<line x1="40" y1="58" x2="960" y2="58" stroke="{t['ink']}" stroke-width="2"/>
{''.join(bars)}
<text x="40" y="{h - 18}" font-family="{MONO}" font-size="12.5" fill="{t['muted']}">{escape(more)}</text>"""
    return svg(h, body, "Merged Kubescape pull requests by repository")


KYVERNO = [
    ("17189", "CVE-2026-56853", "Bumped Go to 1.26.6 to fix an HTTP/2 timeout bypass in the standard library"),
    ("17156", "CVE-2026-56853", "Bumped golang.org/x/net for the same HTTP/2 ReadHeaderTimeout evasion"),
    ("17215", "CVE-2026-46600", "Bumped miekg/dns to fix a DNS parsing panic"),
    ("16782", "CEL", "Bumped cel-go to v0.30.0 to resolve a published advisory"),
    ("16910", "ENGINE", "Context propagation in MatchPolicyContext"),
    ("17116", "TRACING", "OpenTelemetry spans for APICalls without a custom CA bundle"),
    ("17024", "LEAKS", "Goroutine and ticker leaks in metrics, TTL and policy controllers"),
]


def kyverno(t, d):
    h = 92 + len(KYVERNO) * 36 + 20
    rows = []
    for i, (num, tag, text) in enumerate(KYVERNO):
        y = 100 + i * 36
        rows.append(f'<text x="40" y="{y + 6}" font-family="{DISPLAY}" font-weight="800" font-size="24" fill="{t["num"]}">#{num}</text>')
        rows.append(f'<rect x="150" y="{y - 11}" width="{14 + 8.4*len(tag):.0f}" height="22" fill="none" stroke="{t["muted"]}"/>')
        rows.append(f'<text x="157" y="{y + 4}" font-family="{MONO}" font-weight="600" font-size="11.5" letter-spacing="1" fill="{t["ink"]}">{escape(tag)}</text>')
        rows.append(f'<text x="330" y="{y + 5}" font-family="{MONO}" font-size="13.5" fill="{t["ink"]}">{escape(text)}</text>')
        rows.append(f'<line x1="40" y1="{y + 20}" x2="960" y2="{y + 20}" stroke="{t["rule"]}"/>')
    body = fonts("bsd800", "plx400", "plx600") + f"""
<rect width="{W}" height="{h}" fill="{t['bg']}"/>
{logo("kyverno-icon-color.svg", 40, 22, 28)}
{label(t, 78, 44, f"KYVERNO · {d['kv']} MERGED · SECURITY AND RELIABILITY FIXES", color=t['ink'])}
{label(t, 960, 44, "SINCE JUL 2026", anchor="end")}
<line x1="40" y1="58" x2="960" y2="58" stroke="{t['ink']}" stroke-width="2"/>
{''.join(rows)}"""
    return svg(h, body, "Kyverno security and reliability fixes")


TIMELINE = [
    ("MAY 2025", "GitHub", "first web projects"),
    ("2025", "Web3", "Solidity contracts"),
    ("JUN 2026", "InterVue", "AI interview platform"),
    ("JUL 2026", "Kyverno", "CVE and leak fixes"),
    ("NOV 2026", "Kubescape", "{ks} PRs merged"),
    ("SUMMER 2027", "Google", "SWE intern"),
]


def timeline(t, d):
    h = 250
    n = len(TIMELINE)
    x0, x1, y = 110, 890, 132
    step = (x1 - x0) / (n - 1)
    parts = [f'<line x1="{x0}" y1="{y}" x2="{x1}" y2="{y}" stroke="{t["ink"]}" stroke-width="2"/>']
    for i, (when, what, note) in enumerate(TIMELINE):
        x = x0 + i * step
        last = i == n - 1
        anchor = "middle"
        parts.append(f'<rect x="{x - 7}" y="{y - 7}" width="14" height="14" fill="{t["amber"] if last else t["bg"]}" stroke="{t["ink"]}" stroke-width="2"/>')
        parts.append(f'<text x="{x}" y="{y - 24}" text-anchor="{anchor}" font-family="{MONO}" font-weight="600" font-size="11.5" letter-spacing="1.4" fill="{t["muted"]}">{escape(when)}</text>')
        parts.append(f'<text x="{x}" y="{y + 44}" text-anchor="{anchor}" font-family="{DISPLAY}" font-weight="800" font-size="30" fill="{t["ink"]}">{escape(what)}</text>')
        parts.append(f'<text x="{x}" y="{y + 68}" text-anchor="{anchor}" font-family="{MONO}" font-size="12" fill="{t["muted"]}">{escape(note.format(ks=d["ks"]))}</text>')
    body = fonts("bsd800", "plx400", "plx600") + f"""
<rect width="{W}" height="{h}" fill="{t['bg']}"/>
{label(t, 40, 44, "TIMELINE")}
<line x1="40" y1="58" x2="960" y2="58" stroke="{t['ink']}" stroke-width="2"/>
{''.join(parts)}"""
    return svg(h, body, "Timeline from 2025 to 2027")


PROJECTS = [
    ("InterVue", "JAVASCRIPT · AI", ["AI mock interviews with voice,", "proctoring, a code sandbox and", "ATS resume scoring."]),
    ("GetMySeat", "JAVASCRIPT · FULL STACK", ["Movie booking with real-time", "seat selection and Razorpay", "payments."]),
    ("AI Decision Auditor", "PYTHON · TRUSTWORTHY AI", ["Audits AI decisions for fairness,", "explainability, robustness and", "accountability."]),
    ("Foundry FundMe", "SOLIDITY · FOUNDRY", ["ETH crowdfunding contract with a", "USD minimum via Chainlink price", "feeds; fully tested with Foundry."]),
]


def project_tile(t, name, tag, lines, i):
    w, h = 490, 176
    body = fonts("bsd800", "plx400", "plx600") + f"""
<rect width="{w}" height="{h}" fill="{t['bg']}"/>
<rect x="1" y="1" width="{w - 2}" height="{h - 2}" fill="none" stroke="{t['rule']}" stroke-width="2"/>
<rect x="1" y="1" width="{w - 2}" height="8" fill="{t['amber'] if i == 0 else t['ink']}"/>
<text x="24" y="44" font-family="{MONO}" font-weight="600" font-size="11.5" letter-spacing="1.4" fill="{t['muted']}">{escape(tag)}</text>
<text x="22" y="84" font-family="{DISPLAY}" font-weight="800" font-size="38" fill="{t['ink']}">{escape(name)}</text>
{''.join(f'<text x="24" y="{112 + j*20}" font-family="{MONO}" font-size="13" fill="{t["muted"]}">{escape(l)}</text>' for j, l in enumerate(lines))}
<text x="{w - 24}" y="44" text-anchor="end" font-family="{MONO}" font-weight="600" font-size="13" fill="{t['ink']}">↗</text>"""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" '
            f'aria-label="{escape(name)}">{body}</svg>\n')


TOOLBOX = [
    ("LANGUAGES", ["Go", "C++", "Python", "TypeScript", "JavaScript", "Solidity"]),
    ("CLOUD NATIVE", ["Kubernetes", "Helm", "Docker", "eBPF", "OPA / Rego", "CEL"]),
    ("SECURITY", ["Admission control", "Runtime rules", "SBOM / VEX", "CVE triage", "Supply chain"]),
    ("BACKEND & WEB", ["Node.js", "Express", "MongoDB", "MySQL", "React", "Tailwind"]),
    ("TOOLING", ["Git", "GitHub Actions", "Linux", "Bash", "pytest", "Foundry"]),
]


def toolbox(t, d):
    h = 300
    colw = 920 / len(TOOLBOX)
    parts = []
    for c, (head, items) in enumerate(TOOLBOX):
        x = 40 + c * colw
        parts.append(f'<rect x="{x:.0f}" y="84" width="{colw - 16:.0f}" height="30" fill="{t["amber"] if c == 1 else t["ink"]}"/>')
        parts.append(f'<text x="{x + 12:.0f}" y="104" font-family="{MONO}" font-weight="600" font-size="11.5" letter-spacing="1.4" fill="{t["on_amber"] if c == 1 else t["bg"]}">{escape(head)}</text>')
        for j, it in enumerate(items):
            parts.append(f'<text x="{x + 2:.0f}" y="{142 + j*24}" font-family="{MONO}" font-size="14" fill="{t["ink"]}">{escape(it)}</text>')
    body = fonts("plx400", "plx600") + f"""
<rect width="{W}" height="{h}" fill="{t['bg']}"/>
{label(t, 40, 44, "TOOLBOX")}
<line x1="40" y1="58" x2="960" y2="58" stroke="{t['ink']}" stroke-width="2"/>
{''.join(parts)}"""
    return svg(h, body, "Toolbox")


def section(t, left, right):
    h = 72
    body = fonts("plx600") + f"""
<rect width="{W}" height="{h}" fill="{t['bg']}"/>
{label(t, 40, 52, left)}
{label(t, 960, 52, right, anchor="end")}
<line x1="40" y1="{h - 6}" x2="960" y2="{h - 6}" stroke="{t['ink']}" stroke-width="2"/>"""
    return svg(h, body, left)


def footer(t, d):
    h = 64
    body = fonts("plx400", "plx600") + f"""
<rect width="{W}" height="{h}" fill="{t['bg']}"/>
{hazard(t, 0, 12, "f")}
<text x="40" y="44" font-family="{MONO}" font-size="12" fill="{t['muted']}">Panels drawn by scripts/build_profile.py from the GitHub API · refreshed daily</text>
{label(t, 960, 44, "END OF SHEET", anchor="end")}"""
    return svg(h, body, "footer")


def main():
    os.makedirs(OUT, exist_ok=True)
    d = gather()
    for name, t in THEMES.items():
        files = {
            f"masthead-{name}.svg": masthead(t, d),
            f"ledger-{name}.svg": ledger(t, d),
            f"ticker-{name}.svg": ticker(t, d),
            f"footer-{name}.svg": footer(t, d),
            f"section-work-{name}.svg": section(t, "SELECTED WORK", "KUBERNETES SECURITY · GO"),
            f"about-{name}.svg": about(t, d),
            f"repos-{name}.svg": repo_bars(t, d),
            f"kyverno-{name}.svg": kyverno(t, d),
            f"timeline-{name}.svg": timeline(t, d),
            f"toolbox-{name}.svg": toolbox(t, d),
            f"section-built-{name}.svg": section(t, "BUILT", "SIDE PROJECTS"),
        }
        for i, p in enumerate(PROJECTS):
            files[f"project{i+1}-{name}.svg"] = project_tile(t, *p, i)
        if d["weeks"]:
            files[f"heatmap-{name}.svg"] = heatmap(t, d)
        for i, w in enumerate(WORK):
            files[f"work{i+1}-{name}.svg"] = work_row(t, *w, last=(i == len(WORK) - 1))
        for fn, content in files.items():
            with open(os.path.join(OUT, fn), "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
    print(json.dumps({k: v for k, v in d.items() if k not in ("weeks",)}, indent=1))


if __name__ == "__main__":
    main()

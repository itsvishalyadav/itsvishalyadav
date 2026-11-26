"""Builds the profile's SVG cards (dark + light) from live GitHub data.

Run locally with GITHUB_TOKEN set, or from .github/workflows/profile.yml.
Outputs go to assets/. No third-party packages needed.
"""

import datetime as dt
import json
import os
import urllib.parse
import urllib.request
from html import escape

USER = "itsvishalyadav"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")

THEMES = {
    "dark": {
        "bg": "#07080c", "panel": "#0f1219", "panel2": "#141824", "stroke": "#232838",
        "text": "#e6e9f2", "muted": "#7c8499", "dim": "#4a5164",
        "a1": "#22d3ee", "a2": "#a78bfa", "a3": "#f472b6", "ok": "#34d399",
        "orb": "0.55", "grid": "0.06",
    },
    "light": {
        "bg": "#f6f7fb", "panel": "#ffffff", "panel2": "#f0f2f8", "stroke": "#dfe3ee",
        "text": "#141824", "muted": "#5b6478", "dim": "#a3aabb",
        "a1": "#0891b2", "a2": "#7c3aed", "a3": "#db2777", "ok": "#059669",
        "orb": "0.30", "grid": "0.07",
    },
}

MONO = "'JetBrains Mono','SF Mono','Cascadia Code',Consolas,'Liberation Mono',monospace"
SANS = "'Inter','Segoe UI',-apple-system,'Helvetica Neue',Arial,sans-serif"


# ---------------------------------------------------------------- data

def api(path):
    req = urllib.request.Request("https://api.github.com" + path, headers={"Accept": "application/vnd.github+json"})
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def count(query):
    return api("/search/issues?per_page=1&q=" + urllib.parse.quote(query))["total_count"]


def repos_touched(query):
    names = set()
    page = 1
    while True:
        data = api(f"/search/issues?per_page=100&page={page}&q=" + urllib.parse.quote(query))
        for item in data["items"]:
            names.add(item["repository_url"].rsplit("/", 1)[1])
        if len(data["items"]) < 100 or page >= 10:
            return len(names)
        page += 1


def gather():
    user = api(f"/users/{USER}")
    created = dt.datetime.fromisoformat(user["created_at"].replace("Z", "+00:00")).date()
    days = (dt.date.today() - created).days
    return {
        "ks": count(f"author:{USER} org:kubescape is:pr is:merged"),
        "ks_repos": repos_touched(f"author:{USER} org:kubescape is:pr is:merged"),
        "kv": count(f"author:{USER} org:kyverno is:pr is:merged"),
        "issues": count(f"author:{USER} is:issue -user:{USER}"),
        # PRs merged into other people's projects (a friend's class-assignment repo left out)
        "oss": count(f"author:{USER} is:pr is:merged -user:{USER} -user:piyxsh31"),
        "uptime": f"{days // 365}y {(days % 365) // 30}m" if days >= 365 else f"{days // 30} months",
        "updated": dt.date.today().strftime("%d %b %Y"),
    }


# ---------------------------------------------------------------- shared pieces

def defs(t, uid):
    return f"""
  <defs>
    <linearGradient id="grad{uid}" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="{t['a1']}"/><stop offset=".5" stop-color="{t['a2']}"/><stop offset="1" stop-color="{t['a3']}"/>
    </linearGradient>
    <filter id="blur{uid}" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="55"/></filter>
    <pattern id="grid{uid}" width="28" height="28" patternUnits="userSpaceOnUse">
      <path d="M28 0H0V28" fill="none" stroke="{t['text']}" stroke-opacity="{t['grid']}" stroke-width="1"/>
    </pattern>
    <clipPath id="clip{uid}"><rect width="100%" height="100%" rx="22"/></clipPath>
  </defs>"""


def orbs(t, uid, w, h):
    return f"""
  <g filter="url(#blur{uid})" opacity="{t['orb']}">
    <circle cx="{w*0.18}" cy="{h*0.35}" r="{h*0.42}" fill="{t['a1']}">
      <animate attributeName="cx" values="{w*0.18};{w*0.32};{w*0.18}" dur="14s" repeatCount="indefinite"/>
    </circle>
    <circle cx="{w*0.62}" cy="{h*0.75}" r="{h*0.40}" fill="{t['a2']}">
      <animate attributeName="cy" values="{h*0.75};{h*0.35};{h*0.75}" dur="11s" repeatCount="indefinite"/>
    </circle>
    <circle cx="{w*0.88}" cy="{h*0.25}" r="{h*0.34}" fill="{t['a3']}">
      <animate attributeName="cx" values="{w*0.88};{w*0.74};{w*0.88}" dur="16s" repeatCount="indefinite"/>
    </circle>
  </g>"""


def svg(w, h, body, label):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-label="{escape(label)}">{body}\n</svg>\n')


# ---------------------------------------------------------------- hero

def hero(t, d):
    w, h, u = 1000, 330, "h"
    chips = ["Go", "Kubernetes", "eBPF", "CEL", "Rego", "Policy engines"]
    x, chip_svg = 70, []
    for i, c in enumerate(chips):
        cw = 22 + 9 * len(c)
        chip_svg.append(
            f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" begin="{1.6 + i*0.15:.2f}s" dur=".5s" fill="freeze"/>'
            f'<rect x="{x}" y="232" width="{cw}" height="30" rx="15" fill="{t["panel2"]}" fill-opacity=".75" stroke="{t["stroke"]}"/>'
            f'<text x="{x + cw/2}" y="252" text-anchor="middle" font-family="{MONO}" font-size="13" fill="{t["muted"]}">{c}</text></g>')
        x += cw + 10
    body = defs(t, u) + f"""
  <g clip-path="url(#clip{u})">
    <rect width="{w}" height="{h}" fill="{t['bg']}"/>
    {orbs(t, u, w, h)}
    <rect width="{w}" height="{h}" fill="url(#grid{u})"/>
    <rect x="40" y="34" width="{w-80}" height="{h-68}" rx="18" fill="{t['panel']}" fill-opacity=".55" stroke="{t['stroke']}"/>
    <circle cx="66" cy="58" r="5.5" fill="#ff5f57"/><circle cx="84" cy="58" r="5.5" fill="#febc2e"/><circle cx="102" cy="58" r="5.5" fill="#28c840"/>
    <text x="{w-66}" y="63" text-anchor="end" font-family="{MONO}" font-size="12" fill="{t['dim']}">~/itsvishalyadav</text>
    <text x="70" y="112" font-family="{MONO}" font-size="15" fill="{t['muted']}"><tspan fill="{t['ok']}">❯</tspan> whoami</text>
    <rect x="146" y="99" width="8" height="16" fill="{t['a1']}"><animate attributeName="opacity" values="1;0;1" dur="1.1s" repeatCount="indefinite"/></rect>
    <text x="{w-70}" y="112" text-anchor="end" font-family="{MONO}" font-size="12.5" fill="{t['muted']}">B.Tech CSE · ABV-IIITM Gwalior  ·  <tspan fill="{t['a2']}">SWE Intern @ Google '27</tspan></text>
    <text x="68" y="172" font-family="{SANS}" font-size="56" font-weight="800" letter-spacing="-1.5" fill="url(#grad{u})">Vishal Yadav</text>
    <text x="70" y="208" font-family="{SANS}" font-size="19" fill="{t['text']}" opacity="0">Systems engineer working on Kubernetes security
      <animate attributeName="opacity" from="0" to="1" begin=".7s" dur=".8s" fill="freeze"/></text>
    {''.join(chip_svg)}
  </g>"""
    return svg(w, h, body, "Vishal Yadav, systems engineer working on Kubernetes security")


# ---------------------------------------------------------------- neofetch

ART = r"""
           .::::::::::.
       .:::'          ':::.
     .::'    .::::::.    '::.
    ::'    .:'  /\  ':.    '::
   ::     ::   /  \   ::     ::
  ::     ::---/----\---::     ::
  ::     ::  /  ()  \  ::     ::
  ::     ::--\------/--::     ::
   ::     ::  \    /  ::     ::
    ::.    ':. \  / .:'    .::
     '::.    '::\/::'    .::'
       ':::.          .:::'
           '::::::::::'
""".strip("\n").split("\n")


def neofetch(t, d):
    w, u = 1000, "n"
    rows = [
        ("title", "vishal@github"),
        ("rule", ""),
        ("OS", "Kubernetes · Linux"),
        ("Host", "ABV-IIITM Gwalior · B.Tech CSE"),
        ("Kernel", "Go"),
        ("Uptime", f"{d['uptime']} on GitHub"),
        ("Next", "SWE Intern @ Google (Summer '27)"),
        ("Shell", "admission control · runtime detection"),
        ("Policy", "Rego · CEL · ValidatingAdmissionPolicy"),
        ("gap", ""),
        ("— Open source", ""),
        ("Kubescape", f"{d['ks']} merged PRs · {d['ks_repos']} repos"),
        ("Kyverno", f"{d['kv']} merged PRs"),
        ("Merged total", f"{d['oss']} PRs to others' repos"),
        ("Bugs filed", f"{d['issues']} issues"),
    ]
    art = "".join(
        f'<tspan x="70" dy="{0 if i == 0 else 21}">{escape(line)}</tspan>' for i, line in enumerate(ART))
    lines, y = [], 104
    for i, (k, v) in enumerate(rows):
        begin = f"{0.25 + i*0.11:.2f}s"
        fade = f'<animate attributeName="opacity" from="0" to="1" begin="{begin}" dur=".35s" fill="freeze"/>'
        if k == "title":
            body = f'<tspan fill="{t["a1"]}" font-weight="700">vishal</tspan><tspan fill="{t["muted"]}">@</tspan><tspan fill="{t["a2"]}" font-weight="700">github</tspan>'
        elif k == "rule":
            body = f'<tspan fill="{t["dim"]}">{"─" * 30}</tspan>'
        elif k == "gap":
            y += 8
            continue
        elif k.startswith("—"):
            body = f'<tspan fill="{t["a3"]}" font-weight="700">{escape(k)}</tspan> <tspan fill="{t["dim"]}">{"─" * 16}</tspan>'
        else:
            dots = "." * max(2, 14 - len(k))
            body = (f'<tspan fill="{t["a2"]}">{escape(k)}</tspan><tspan fill="{t["dim"]}"> {dots} </tspan>'
                    f'<tspan fill="{t["text"]}">{escape(v)}</tspan>')
        lines.append(f'<text x="470" y="{y}" font-family="{MONO}" font-size="15" opacity="0">{body}{fade}</text>')
        y += 22
    palette = "".join(
        f'<rect x="{470 + i*34}" y="{y + 6}" width="28" height="14" rx="3" fill="{c}"/>'
        for i, c in enumerate([t["a1"], t["a2"], t["a3"], t["ok"], "#fbbf24", t["muted"]]))
    h = y + 80
    body = defs(t, u) + f"""
  <g clip-path="url(#clip{u})">
    <rect width="{w}" height="{h}" fill="{t['bg']}"/>
    {orbs(t, u, w, h)}
    <rect x="30" y="28" width="{w-60}" height="{h-56}" rx="18" fill="{t['panel']}" fill-opacity=".72" stroke="{t['stroke']}"/>
    <circle cx="56" cy="52" r="5.5" fill="#ff5f57"/><circle cx="74" cy="52" r="5.5" fill="#febc2e"/><circle cx="92" cy="52" r="5.5" fill="#28c840"/>
    <text x="{w/2}" y="57" text-anchor="middle" font-family="{MONO}" font-size="12" fill="{t['dim']}">neofetch — updated {d['updated']}</text>
    <text x="70" y="104" font-family="{MONO}" font-size="15" fill="url(#grad{u})" xml:space="preserve">{art}</text>
    {''.join(lines)}
    {palette}
    <rect x="682" y="{y + 5}" width="9" height="17" fill="{t['a1']}">
      <animate attributeName="opacity" values="1;0;1" dur="1.1s" repeatCount="indefinite"/></rect>
  </g>"""
    return svg(w, h, body, "neofetch-style card: system and open-source stats")


# ---------------------------------------------------------------- fix cards

FIXES = [
    ("kubescape/storage", "#528", "Mid-path wildcards kept as written",
     "Profiles were widened on every save, so file-access alerts went quiet."),
    ("kubescape/node-agent", "#1175", "Argv boundaries in the CEL cache key",
     "Two different command lines shared one cached verdict for R0040."),
    ("kubescape/operator", "#583", "Legacy AppArmor annotation blocked",
     "A remediation patch could still flip a workload to unconfined."),
    ("kubescape/operator", "#598", "Admin cordons survive a revert",
     "Undoing a remediation no longer reopens a node under maintenance."),
]


def fix_card(t, repo, num, title, why, i):
    w, h, u = 480, 150, f"f{i}"
    return svg(w, h, defs(t, u) + f"""
  <g clip-path="url(#clip{u})">
    <rect width="{w}" height="{h}" fill="{t['panel']}"/>
    <circle cx="{w-10}" cy="-10" r="120" fill="url(#grad{u})" opacity=".09"/>
    <rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="22" fill="none" stroke="{t['stroke']}"/>
    <rect x="24" y="24" width="4" height="22" rx="2" fill="url(#grad{u})"/>
    <text x="38" y="41" font-family="{MONO}" font-size="13" fill="{t['muted']}">{escape(repo)} <tspan fill="{t['a1']}">{escape(num)}</tspan></text>
    <text x="24" y="80" font-family="{SANS}" font-size="19" font-weight="700" fill="{t['text']}">{escape(title)}</text>
    <text x="24" y="110" font-family="{SANS}" font-size="13.5" fill="{t['muted']}">{escape(why)}</text>
    <text x="{w-24}" y="{h-20}" text-anchor="end" font-family="{MONO}" font-size="12" fill="{t['ok']}">● merged</text>
  </g>""", f"{repo}{num}: {title}")


# ---------------------------------------------------------------- divider

def divider(t, label):
    w, h, u = 1000, 60, "d" + label[:3]
    return svg(w, h, defs(t, u) + f"""
  <line x1="0" y1="30" x2="{w}" y2="30" stroke="url(#grad{u})" stroke-opacity=".35"/>
  <rect x="{w/2 - (11*len(label) + 56)/2}" y="12" width="{11*len(label) + 56}" height="36" rx="18" fill="{t['bg']}" stroke="{t['stroke']}"/>
  <text x="{w/2}" y="36" text-anchor="middle" font-family="{MONO}" font-size="15" letter-spacing="2" fill="url(#grad{u})">{escape(label)}</text>""",
               label)


def main():
    os.makedirs(OUT, exist_ok=True)
    d = gather()
    for name, t in THEMES.items():
        files = {f"hero-{name}.svg": hero(t, d), f"neofetch-{name}.svg": neofetch(t, d)}
        for i, f in enumerate(FIXES):
            files[f"fix{i+1}-{name}.svg"] = fix_card(t, *f, i)
        for label in ("OPEN SOURCE", "STACK", "ACTIVITY"):
            files[f"div-{label.split()[0].lower()}-{name}.svg"] = divider(t, label)
        for fn, content in files.items():
            with open(os.path.join(OUT, fn), "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
    print(json.dumps(d))


if __name__ == "__main__":
    main()

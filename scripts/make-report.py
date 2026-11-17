#!/usr/bin/env python3
"""Turn the raw scan reports in a folder into ONE readable HTML page.

Raw files are left untouched. Standard library only (runs in python:3.12-slim).
Usage: python make-report.py --reports reports --out reports/summary.html \
         --app node-app --build 15 [--sonar-url https://sonarcloud.io/dashboard?id=...]
Any report that is missing or unreadable is shown as "not found" instead of failing.
"""
import argparse, glob, html, json, os, datetime

SEV = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
ALIAS = {"ERROR": "HIGH", "WARNING": "MEDIUM", "NOTE": "LOW", "MODERATE": "MEDIUM",
         "NONE": "INFO", "UNKNOWN": "INFO", "INFORMATIONAL": "INFO", "": "INFO"}
MAX_ROWS = 200
e = lambda x: html.escape(str(x if x is not None else ""))


def sev(s):
    s = str(s or "").upper()
    s = ALIAS.get(s, s)
    return s if s in SEV else "INFO"


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def first(pattern, d):
    m = sorted(glob.glob(os.path.join(d, pattern)))
    return m[0] if m else None


# ---------- parsers: each returns a list of findings ----------
# finding = dict(sev, title, where, fix)

def p_sarif(data, all_high=False):
    out = []
    for run in (data or {}).get("runs", []):
        for r in run.get("results", []):
            loc = (r.get("locations") or [{}])[0].get("physicalLocation", {})
            uri = loc.get("artifactLocation", {}).get("uri", "")
            line = loc.get("region", {}).get("startLine", "")
            msg = (r.get("message") or {}).get("text", "")
            out.append(dict(sev="HIGH" if all_high else sev(r.get("level", "warning")),
                            title=r.get("ruleId", ""), where=f"{uri}:{line}" if line else uri,
                            fix=msg[:300]))
    return out


def p_trivy(data):
    out = []
    for res in (data or {}).get("Results", []) or []:
        tgt = res.get("Target", "")
        for v in res.get("Vulnerabilities") or []:
            out.append(dict(sev=sev(v.get("Severity")),
                            title=f'{v.get("VulnerabilityID","")} - {v.get("Title","")}'.strip(" -"),
                            where=f'{v.get("PkgName","")} {v.get("InstalledVersion","")}  ({tgt})',
                            fix=("fix: " + v["FixedVersion"]) if v.get("FixedVersion") else "no fix yet"))
        for m in res.get("Misconfigurations") or []:
            out.append(dict(sev=sev(m.get("Severity")), title=m.get("Title", ""), where=tgt, fix=m.get("Resolution", "")))
        for s in res.get("Secrets") or []:
            out.append(dict(sev=sev(s.get("Severity")), title=s.get("Title", ""), where=tgt, fix=""))
    return out


def p_npm(data):
    out = []
    for name, v in ((data or {}).get("vulnerabilities") or {}).items():
        titles = [x.get("title") for x in v.get("via", []) if isinstance(x, dict) and x.get("title")]
        fx = v.get("fixAvailable")
        fix = "no fix" if fx is False else (f'upgrade to {fx.get("name")}@{fx.get("version")}' if isinstance(fx, dict) else "fix available")
        out.append(dict(sev=sev(v.get("severity")), title=name + (" - " + "; ".join(titles[:3]) if titles else ""),
                        where=f'range {v.get("range","")}', fix=fix))
    return out


def p_pipaudit(data):
    deps = data.get("dependencies", []) if isinstance(data, dict) else (data or [])
    out = []
    for d in deps:
        for v in d.get("vulns", []) or []:
            fv = v.get("fix_versions") or []
            out.append(dict(sev="HIGH", title=f'{v.get("id","")} ({d.get("name")})', where=f'{d.get("name")} {d.get("version")}',
                            fix=("fix: " + ", ".join(fv)) if fv else "no fix yet"))
    return out


def p_bandit(data):
    return [dict(sev=sev(r.get("issue_severity")), title=f'{r.get("test_id","")} {r.get("issue_text","")}',
                 where=f'{r.get("filename","")}:{r.get("line_number","")}', fix="")
            for r in (data or {}).get("results", [])]


def p_zap(data):
    out = []
    for site in (data or {}).get("site", []):
        for a in site.get("alerts", []):
            code = str(a.get("riskcode", "0"))
            out.append(dict(sev={"3": "HIGH", "2": "MEDIUM", "1": "LOW"}.get(code, "INFO"),
                            title=a.get("name", ""), where=f'{a.get("count","?")} instance(s) at {site.get("@name","")}',
                            fix=(a.get("solution", "") or "").replace("<p>", "").replace("</p>", " ")[:300]))
    return out


# name, category, glob, loader -> findings
TOOLS = [
    ("Gitleaks", "Secret scan", "gitleaks*.sarif", lambda d: p_sarif(d, all_high=True)),
    ("npm audit", "SCA (dependencies)", "npm-audit.json", p_npm),
    ("pip-audit", "SCA (dependencies)", "pip-audit.json", p_pipaudit),
    ("Semgrep", "SAST (source code)", "semgrep*.sarif", p_sarif),
    ("Bandit", "SAST (source code)", "bandit.json", p_bandit),
    ("Trivy", "Container image", "trivy*.json", p_trivy),
    ("OWASP ZAP", "DAST (running app)", "zap*.json", p_zap),
]


def count(findings):
    c = {s: 0 for s in SEV}
    for f in findings:
        c[f["sev"]] += 1
    return c


def chips(c):
    return "".join(f'<span class="chip {s.lower()}">{s.title()} {c[s]}</span>' for s in SEV if c[s])


def section(name, cat, path, findings):
    raw = f'<a href="{e(os.path.basename(path))}">{e(os.path.basename(path))}</a>' if path else ""
    if findings is None:
        return f'<section class="card"><h2>{e(name)} <small>{e(cat)}</small></h2><p class="muted">Report not found or unreadable.</p></section>', None
    c = count(findings)
    findings = sorted(findings, key=lambda f: SEV.index(f["sev"]))
    state = chips(c) or '<span class="chip ok">No findings</span>'
    rows = "".join(
        f'<tr><td><span class="chip {f["sev"].lower()}">{f["sev"].title()}</span></td><td>{e(f["title"])}</td>'
        f'<td class="mono">{e(f["where"])}</td><td>{e(f["fix"])}</td></tr>' for f in findings[:MAX_ROWS])
    more = f'<p class="muted">Showing first {MAX_ROWS} of {len(findings)}. See the raw file for the rest.</p>' if len(findings) > MAX_ROWS else ""
    table = (f'<details{" open" if c["CRITICAL"] or c["HIGH"] else ""}><summary>Details ({len(findings)})</summary>'
             f'<table><tr><th>Severity</th><th>Finding</th><th>Where</th><th>Fix / note</th></tr>{rows}</table>{more}</details>') if findings else ""
    return (f'<section class="card"><h2>{e(name)} <small>{e(cat)}</small></h2><div class="row">{state}'
            f'<span class="raw">raw: {raw}</span></div>{table}</section>'), c


def sbom_section(d):
    p = first("sbom*.json", d)
    data = load(p) if p else None
    if not data:
        return '<section class="card"><h2>SBOM <small>Software bill of materials</small></h2><p class="muted">Report not found or unreadable.</p></section>'
    comps = data.get("components", []) or []
    types = {}
    for c in comps:
        types[c.get("type", "?")] = types.get(c.get("type", "?"), 0) + 1
    rows = "".join(f'<tr><td>{e(c.get("name"))}</td><td class="mono">{e(c.get("version",""))}</td><td>{e(c.get("type",""))}</td></tr>'
                   for c in sorted(comps, key=lambda c: str(c.get("name")))[:MAX_ROWS])
    t = ", ".join(f"{k}: {v}" for k, v in sorted(types.items()))
    return (f'<section class="card"><h2>SBOM <small>Software bill of materials</small></h2><div class="row">'
            f'<span class="chip info">{len(comps)} components</span><span class="muted">{e(t)}</span>'
            f'<span class="raw">raw: <a href="{e(os.path.basename(p))}">{e(os.path.basename(p))}</a></span></div>'
            f'<details><summary>Components (first {MAX_ROWS})</summary><table><tr><th>Name</th><th>Version</th><th>Type</th></tr>{rows}</table></details></section>')


CSS = """
:root{--bg:#f6f7f9;--card:#fff;--fg:#1b1f24;--mut:#6b7280;--bd:#e5e7eb;--crit:#7f1d1d;--high:#b91c1c;--med:#b45309;--low:#1d4ed8;--info:#4b5563;--ok:#166534}
@media(prefers-color-scheme:dark){:root{--bg:#0f1115;--card:#171a21;--fg:#e6e8eb;--mut:#9aa3af;--bd:#2a2f3a}}
*{box-sizing:border-box}body{margin:0;padding:24px;background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:1100px;margin:auto}h1{margin:0 0 4px;font-size:22px}h2{margin:0 0 8px;font-size:16px}h2 small{font-weight:400;color:var(--mut);margin-left:6px}
.muted{color:var(--mut)}.card{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:16px;margin:14px 0}
.row{display:flex;flex-wrap:wrap;gap:8px;align-items:center}.raw{margin-left:auto;color:var(--mut);font-size:12px}
.chip{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:600;color:#fff;background:var(--info)}
.chip.critical{background:var(--crit)}.chip.high{background:var(--high)}.chip.medium{background:var(--med)}.chip.low{background:var(--low)}.chip.ok{background:var(--ok)}
.totals{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin:14px 0}.tot{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:12px}
.tot b{display:block;font-size:26px}details{margin-top:10px}summary{cursor:pointer;color:var(--mut)}
table{width:100%;border-collapse:collapse;margin-top:8px;font-size:13px}th,td{text-align:left;padding:6px 8px;border-top:1px solid var(--bd);vertical-align:top}
th{color:var(--mut);font-weight:600}.mono{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px;word-break:break-all}a{color:var(--low)}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reports", default="reports")
    ap.add_argument("--out", default=None)
    ap.add_argument("--app", default="app")
    ap.add_argument("--build", default="")
    ap.add_argument("--sonar-url", default="")
    a = ap.parse_args()
    out = a.out or os.path.join(a.reports, "summary.html")

    total = {s: 0 for s in SEV}
    parts, missing = [], []
    for name, cat, pattern, fn in TOOLS:
        p = first(pattern, a.reports)
        data = load(p) if p else None
        if p is None and name in ("pip-audit", "Bandit"):
            continue  # python-only tools: hide when the app does not use them
        if p is None and name == "npm audit" and first("pip-audit.json", a.reports):
            continue
        findings = None
        if data is not None:
            try:
                findings = fn(data)
            except Exception:
                findings = None
        html_part, c = section(name, cat, p, findings)
        parts.append(html_part)
        if c is None:
            missing.append(name)
        else:
            for s in SEV:
                total[s] += c[s]
    parts.append(sbom_section(a.reports))
    if a.sonar_url:
        parts.append(f'<section class="card"><h2>SonarQube Cloud <small>SAST + Quality Gate</small></h2>'
                     f'<p>Results live on SonarQube Cloud: <a href="{e(a.sonar_url)}">open the project dashboard</a>. '
                     f'Quality Gate status is in the Jenkins console log of the SonarQube stage.</p></section>')
    for z in sorted(glob.glob(os.path.join(a.reports, "zap*.html"))):
        parts.append(f'<p class="muted">ZAP full HTML report: <a href="{e(os.path.basename(z))}">{e(os.path.basename(z))}</a></p>')

    tot_html = "".join(f'<div class="tot"><b style="color:var(--{ {"CRITICAL":"crit","HIGH":"high","MEDIUM":"med","LOW":"low","INFO":"info"}[s] })">{total[s]}</b>{s.title()}</div>' for s in SEV)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    miss = f'<p class="muted">Reports not found: {e(", ".join(missing))}</p>' if missing else ""
    page = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Security report - {e(a.app)} #{e(a.build)}</title><style>{CSS}</style></head><body><main>'
            f'<h1>Security scan summary</h1><div class="muted">{e(a.app)} &middot; build #{e(a.build)} &middot; {now}</div>'
            f'<div class="totals">{tot_html}</div>{miss}{"".join(parts)}'
            f'<p class="muted">Counts above cover Gitleaks, SCA, SAST, image and DAST reports found in this folder. Raw files are kept alongside this page.</p>'
            f'</main></body></html>')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"wrote {out}  totals={total}  missing={missing}")


if __name__ == "__main__":
    main()

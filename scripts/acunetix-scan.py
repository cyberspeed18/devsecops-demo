#!/usr/bin/env python3
"""Run one Acunetix scan through its REST API and write reports/acunetix.json.

Standard library only (runs in python:3.12-slim). API key comes from env ACUNETIX_API_KEY.
Exit code: 0 ok, 3 = findings at/above --fail-on, 2 = scan failed/timeout/API error.
"""
import argparse, json, os, ssl, sys, time, urllib.request, urllib.error

SEV = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True, help="Acunetix base URL, e.g. https://acunetix.local:3443")
    ap.add_argument("--target", required=True, help="address of the app AS SEEN FROM the Acunetix server")
    ap.add_argument("--profile", default="11111111-1111-1111-1111-111111111111", help="scan profile id (default = Full Scan)")
    ap.add_argument("--out", default="reports/acunetix.json")
    ap.add_argument("--fail-on", default="high", choices=list(SEV) + ["none"])
    ap.add_argument("--timeout", type=int, default=1800, help="max seconds to wait for the scan")
    ap.add_argument("--poll", type=int, default=15)
    ap.add_argument("--insecure", action="store_true", help="skip TLS verification (Acunetix default cert is self-signed)")
    a = ap.parse_args()

    key = os.environ.get("ACUNETIX_API_KEY", "")
    if not key:
        print("ACUNETIX_API_KEY is not set", file=sys.stderr)
        return 2
    base = a.url.rstrip("/") + "/api/v1"
    ctx = ssl._create_unverified_context() if a.insecure else None

    def call(method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(base + path, data=data, method=method,
                                     headers={"X-Auth": key, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}

    try:
        t = call("POST", "/targets", {"address": a.target, "description": "jenkins " + os.environ.get("BUILD_TAG", ""), "criticality": 10})
        tid = t["target_id"]
        s = call("POST", "/scans", {"target_id": tid, "profile_id": a.profile,
                                    "schedule": {"disable": False, "start_date": None, "time_sensitive": False}})
        sid = s["scan_id"] if "scan_id" in s else s.get("id")
        print(f"target {tid} scan {sid} started for {a.target}")
        deadline = time.time() + a.timeout
        status, counts = "unknown", {}
        while time.time() < deadline:
            info = call("GET", f"/scans/{sid}")
            cur = info.get("current_session") or {}
            status, counts = cur.get("status", "unknown"), cur.get("severity_counts") or {}
            print(f"status={status} counts={counts}")
            if status in ("completed", "failed", "aborted"):
                break
            time.sleep(a.poll)
        else:
            print("timeout waiting for scan", file=sys.stderr)
            status = "timeout"

        vulns = []
        if status == "completed":
            res = call("GET", f"/scans/{sid}/results")["results"][0]["result_id"]
            cursor = ""
            while True:
                page = call("GET", f"/scans/{sid}/results/{res}/vulnerabilities?l=100" + (f"&c={cursor}" if cursor else ""))
                for v in page.get("vulnerabilities", []):
                    vulns.append({"name": v.get("vt_name", ""), "severity": v.get("severity", 0),
                                  "url": v.get("affects_url", ""), "recommendation": v.get("recommendation", "")})
                cursor = (page.get("pagination") or {}).get("next_cursor") or ""
                if not cursor:
                    break
    except (urllib.error.URLError, KeyError, IndexError, ValueError) as ex:
        print(f"Acunetix API error: {ex}", file=sys.stderr)
        return 2

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"scan_id": sid, "target": a.target, "status": status, "severity_counts": counts, "vulnerabilities": vulns}, f, indent=2)
    print(f"wrote {a.out}: {len(vulns)} vulnerabilities, status={status}")
    if status != "completed":
        return 2
    if a.fail_on != "none" and any(v["severity"] >= SEV[a.fail_on] for v in vulns):
        print(f"findings at or above '{a.fail_on}' -> exit 3", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())

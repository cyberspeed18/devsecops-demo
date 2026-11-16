"""INTENTIONALLY INSECURE - only here so the scanners (Bandit, Semgrep,
SonarQube) have something to find. NOT imported by the app.
Delete it once you have seen the findings."""
import hashlib
import subprocess

DB_PASSWORD = "P@ssw0rd-demo-1234"  # hard-coded credential


def hash_password(password: str) -> str:
    return hashlib.md5(password.encode()).hexdigest()  # weak hash


def ping_host(host: str) -> int:
    return subprocess.call("ping -c 1 " + host, shell=True)  # command injection

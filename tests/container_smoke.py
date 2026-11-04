"""Isolated container acceptance: no published ports, live targets, or production data.

Run after building the repository image:
    python3 tests/container_smoke.py goreecloud-monitor:ci

The test runner invokes Docker locally. The target container has no network
interfaces except loopback and tests the actual server through HTTP inside it.
"""
from __future__ import annotations

import json
import subprocess
import sys

TEST_PASSWORD = "local-ci-fixture-not-a-secret"

IN_CONTAINER = r'''
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:3001"
PASSWORD = "local-ci-fixture-not-a-secret"
checks = []

def request(method, path, body=None, cookie="", csrf=""):
    headers = {}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if cookie:
        headers["Cookie"] = cookie
    if csrf:
        headers["X-CSRF-Token"] = csrf
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        BASE + path, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=3) as response:
            return response.status, json.load(response), response.headers
    except urllib.error.HTTPError as error:
        return error.code, json.load(error), error.headers

def check(condition, label):
    assert condition, label
    checks.append(label)

process = subprocess.Popen(
    [sys.executable, "-m", "monitor.server"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(50):
        if process.poll() is not None:
            raise AssertionError("Monitor process exited before readiness")
        try:
            status, payload, _ = request("GET", "/readyz")
            if status == 200 and payload.get("ready") is True:
                break
        except (OSError, ValueError):
            pass
        time.sleep(0.15)
    else:
        raise AssertionError("Monitor did not become ready")
    check(True, "database readiness")

    status, public, _ = request("GET", "/api/public")
    check(status == 200 and public["monitors"] == [], "empty public status")

    status, _, _ = request("GET", "/api/monitors")
    check(status == 401, "unauthenticated monitor denial")

    status, _, _ = request("GET", "/metrics")
    check(status == 403, "metrics denied without configured token")

    status, _, _ = request("POST", "/api/login", {"password": "wrong"})
    check(status == 401, "invalid password denied")

    status, payload, headers = request(
        "POST", "/api/login", {"password": PASSWORD})
    check(status == 200 and payload.get("authenticated") is True,
          "operator login")
    csrf = payload["csrf"]
    raw_cookie = headers.get("Set-Cookie", "")
    check(all(flag in raw_cookie for flag in
              ("HttpOnly", "SameSite=Strict", "Secure")),
          "session cookie protections")
    cookie = raw_cookie.split(";", 1)[0]

    monitor = {"name": "Private local smoke",
               "kind": "push", "public": False}
    status, _, _ = request("POST", "/api/monitors", monitor, cookie)
    check(status == 403, "CSRF write denial")

    status, created, _ = request(
        "POST", "/api/monitors", monitor, cookie, csrf)
    check(status == 201 and created.get("id") and created.get("push_token"),
          "authenticated private push-monitor creation")
    mid, push_token = created["id"], created["push_token"]

    status, public, _ = request("GET", "/api/public")
    check(status == 200 and public["monitors"] == [],
          "private monitor hidden from public status")

    status, private, _ = request("GET", "/api/monitors", cookie=cookie)
    check(status == 200 and len(private["monitors"]) == 1 and
          private["monitors"][0]["id"] == mid,
          "authenticated inventory includes private monitor")

    status, _, _ = request(
        "POST", "/push/" + push_token, {"status": "up"})
    check(status == 200, "push heartbeat accepted")

    status, private, _ = request("GET", "/api/monitors", cookie=cookie)
    check(status == 200 and private["monitors"][0]["state"] == "up",
          "push heartbeat updates service state")

    status, _, _ = request(
        "DELETE", "/api/monitors/" + str(mid), cookie=cookie, csrf=csrf)
    check(status == 200, "authenticated service deletion")

    status, _, _ = request("POST", "/api/logout", cookie=cookie, csrf=csrf)
    check(status == 200, "session logout")

    status, _, _ = request("GET", "/api/monitors", cookie=cookie)
    check(status == 401, "revoked session denied")

    print("PASS: " + str(len(checks)) +
          " local-only container runtime acceptance checks")
finally:
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
'''

def main() -> None:
    image = sys.argv[1] if len(sys.argv) == 2 else "goreecloud-monitor:ci"
    metadata = json.loads(subprocess.check_output(
        ["docker", "image", "inspect", image], text=True))[0]
    config = metadata["Config"]
    if config.get("User") != "10001:10001":
        raise AssertionError("Container image must run with unprivileged UID/GID")
    health = config.get("Healthcheck") or {}
    if not health.get("Test") or "/readyz" not in " ".join(health["Test"]):
        raise AssertionError("Image must retain /readyz healthcheck")

    command = [
        "docker", "run", "--rm", "--network=none", "--read-only",
        "--tmpfs", "/data:rw,nosuid,nodev,size=32m,mode=1777",
        "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=16m,mode=1777",
        "--cap-drop=ALL", "--security-opt=no-new-privileges",
        "--pids-limit=64", "--memory=256m",
        "-e", "GC_HOST=127.0.0.1",
        "-e", "GC_ADMIN_PASSWORD=" + TEST_PASSWORD,
        "-e", "GC_COOKIE_SECURE=1",
        image, "python", "-c", IN_CONTAINER
    ]
    subprocess.run(command, check=True, timeout=90)
    print("PASS: nonroot image metadata, healthcheck and isolated runtime")

if __name__ == "__main__":
    main()

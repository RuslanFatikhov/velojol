#!/usr/bin/env python3
import argparse
import json
import sys
import urllib.error
import urllib.request


def request(url):
    with urllib.request.urlopen(url, timeout=10) as response:
        body = response.read().decode("utf-8", errors="replace")
        return response.status, body, response.headers.get("Content-Type", "")


def check_endpoint(url, expected_status=200, contains=None, content_type=None):
    status, body, response_content_type = request(url)
    if status != expected_status:
        raise RuntimeError(f"{url} returned {status}, expected {expected_status}")
    if contains:
        markers = contains if isinstance(contains, (list, tuple)) else [contains]
        if not any(marker in body for marker in markers):
            raise RuntimeError(f"{url} did not contain any expected marker: {markers}")
    if content_type and content_type not in response_content_type:
        raise RuntimeError(f"{url} content-type {response_content_type!r} did not contain {content_type!r}")


def check_healthz(url):
    status, body, response_content_type = request(url)
    if status != 200:
        raise RuntimeError(f"{url} returned {status}, expected 200")
    if "application/json" not in response_content_type:
        raise RuntimeError(f"{url} content-type {response_content_type!r} did not contain 'application/json'")

    payload = json.loads(body)
    if payload.get("status") != "ok":
        raise RuntimeError(f"{url} returned unexpected payload: {payload}")


def main():
    parser = argparse.ArgumentParser(description="Smoke-test a deployed Velojol instance.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8020", help="Base application URL")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    try:
        check_healthz(f"{base_url}/healthz")
        check_endpoint(
            f"{base_url}/",
            contains=["<title>Главная - VELOJOL", "<title>Главная - Velojol"],
            content_type="text/html",
        )
        check_endpoint(f"{base_url}/auth/login", contains="<title>Вход", content_type="text/html")
        print(json.dumps({"status": "ok", "base_url": base_url}))
    except (RuntimeError, urllib.error.URLError) as exc:
        print(json.dumps({"status": "failed", "base_url": base_url, "error": str(exc)}), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()

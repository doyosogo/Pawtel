"""Read-only deployment checks: no logins, provider calls or database writes."""

import argparse
import json
from urllib.parse import urlsplit

import httpx


def origin(value, allow_local=False):
    parsed = urlsplit(value)
    if (
        parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
        or not parsed.hostname
    ):
        raise ValueError("Supply a plain HTTPS origin without credentials or paths.")
    if parsed.scheme != "https" and not (
        allow_local
        and parsed.scheme == "http"
        and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    ):
        raise ValueError("HTTPS required; local HTTP needs explicit opt-in.")
    return value.rstrip("/")


def read(client, url):
    with client.stream("GET", url) as response:
        response.raise_for_status()
        if response.is_redirect:
            raise ValueError("Unexpected redirect; use the final HTTPS origin.")
        body = bytearray()
        for chunk in response.iter_bytes():
            body.extend(chunk)
            if len(body) > 1024 * 1024:
                raise ValueError("Smoke response exceeds 1 MiB.")
        return response, bytes(body)


def check(client, frontend, backend):
    results = []
    response, body = read(client, frontend + "/")
    if (
        "text/html" not in response.headers.get("content-type", "")
        or b'id="root"' not in body
    ):
        raise ValueError("Frontend is not the compiled React application.")
    results.append("Frontend React shell: PASS")
    for path, expected in (("/health", "ok"), ("/ready", "ready")):
        response, body = read(client, backend + path)
        if json.loads(body) != {"status": expected} or not response.headers.get(
            "x-request-id"
        ):
            raise ValueError("Unexpected diagnostic contract.")
        results.append(path + ": PASS")
    _, body = read(client, backend + "/api/v1/listings?limit=1")
    data = json.loads(body)
    if not isinstance(data.get("items"), list):
        raise ValueError("Unexpected discovery contract.")
    results.append("Public Listing discovery: PASS (empty collection is valid)")
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend", required=True)
    parser.add_argument(
        "--backend",
        help="Defaults to frontend origin (selected same-origin deployment).",
    )
    parser.add_argument("--allow-local-http", action="store_true")
    args = parser.parse_args()
    try:
        front = origin(args.frontend, args.allow_local_http)
        back = origin(args.backend or args.frontend, args.allow_local_http)
        with httpx.Client(timeout=8, follow_redirects=False) as client:
            for result in check(client, front, back):
                print(result)
    except Exception:
        # No URL/header/body/exception dumping; supplied arguments could be sensitive.
        print("Deployment smoke FAILED. Check origin, TLS, release logs and readiness.")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()

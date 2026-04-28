#!/usr/bin/env python3
"""Query codex daily quota usage from the upstream API."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any


LOGIN_URL = "https://deepl.micosoft.icu/api/users/card-login"
WHOAMI_URL = "https://deepl.micosoft.icu/api/users/whoami"
DEFAULT_CARD = "02B0A553-33B8-4045-B46E-1280139A241B"
DEFAULT_DAILY_QUOTA = 90.0
TIMEOUT_SECONDS = 20
PROXY_BYPASS_ENV_KEYS = (
    "http_proxy",
    "https_proxy",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "all_proxy",
    "ALL_PROXY",
)


class ApiError(RuntimeError):
    """Raised when the upstream API returns an error."""


def build_opener(disable_proxy: bool) -> urllib.request.OpenerDirector:
    if not disable_proxy:
        return urllib.request.build_opener()
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def post_json(
    opener: urllib.request.OpenerDirector,
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)

    request = urllib.request.Request(
        url=url,
        data=data,
        headers=request_headers,
        method="POST",
    )
    return load_json(opener, request)


def get_json(
    opener: urllib.request.OpenerDirector,
    url: str,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    request = urllib.request.Request(url=url, headers=headers or {}, method="GET")
    return load_json(opener, request)


def load_json(
    opener: urllib.request.OpenerDirector,
    request: urllib.request.Request,
) -> dict[str, Any]:
    try:
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise ApiError(f"HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise ApiError(f"Network error: {exc.reason}") from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ApiError(f"Invalid JSON response: {raw[:200]}") from exc

    if payload.get("code") != 0:
        raise ApiError(payload.get("msg") or payload.get("message") or "API error")

    data = payload.get("data")
    if not isinstance(data, dict):
        raise ApiError("API returned unexpected data")
    return data


def login_by_card(
    opener: urllib.request.OpenerDirector,
    card: str,
    agent: str,
) -> dict[str, Any]:
    return post_json(opener, LOGIN_URL, {"card": card, "agent": agent})


def query_whoami(
    opener: urllib.request.OpenerDirector,
    token: str,
) -> dict[str, Any]:
    return get_json(opener, WHOAMI_URL, {"x-auth-token": token})


def build_summary(
    user_data: dict[str, Any],
    daily_quota: float,
    agent: str,
    proxy_disabled: bool,
) -> dict[str, Any]:
    used = float(user_data.get("day_score_used") or 0.0)
    remaining = max(daily_quota - used, 0.0)
    remaining_percent = (remaining / daily_quota * 100.0) if daily_quota > 0 else 0.0
    used_percent = (used / daily_quota * 100.0) if daily_quota > 0 else 0.0

    vip = user_data.get("vip") or {}
    return {
        "account": user_data.get("account"),
        "nickname": user_data.get("nickname"),
        "product": vip.get("product"),
        "remark": vip.get("remark"),
        "expire_at": vip.get("expire_at"),
        "day_score_date": user_data.get("day_score_date"),
        "daily_quota": daily_quota,
        "used": used,
        "remaining": remaining,
        "used_percent": round(used_percent, 2),
        "remaining_percent": round(remaining_percent, 2),
        "agent": agent,
        "proxy_disabled": proxy_disabled,
    }


def format_text(summary: dict[str, Any]) -> str:
    lines = [
        f"account: {summary.get('account') or '-'}",
        f"product: {summary.get('product') or '-'}",
        f"remark: {summary.get('remark') or '-'}",
        f"expire_at: {summary.get('expire_at') or '-'}",
        f"day_score_date: {summary.get('day_score_date') or '-'}",
        f"daily_quota: {summary['daily_quota']:.3f}".rstrip("0").rstrip("."),
        f"used: {summary['used']:.3f}".rstrip("0").rstrip("."),
        f"remaining: {summary['remaining']:.3f}".rstrip('0').rstrip('.') ,
        f"used_percent: {summary['used_percent']:.2f}%",
        f"remaining_percent: {summary['remaining_percent']:.2f}%",
    ]
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Query codex daily quota usage from the vendor API."
    )
    parser.add_argument(
        "--card",
        default=DEFAULT_CARD,
        help="Activation card. Defaults to the built-in card.",
    )
    parser.add_argument(
        "--agent",
        default="main",
        help="Login agent passed to the upstream API. Default: main.",
    )
    parser.add_argument(
        "--daily-quota",
        type=float,
        default=DEFAULT_DAILY_QUOTA,
        help="Daily quota used to compute percentages. Default: 90.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the result as JSON.",
    )
    parser.add_argument(
        "--keep-proxy",
        action="store_true",
        help="Keep current proxy environment instead of bypassing local proxy.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.card:
        print("Error: missing card. Use --card or set DEFAULT_CARD.", file=sys.stderr)
        return 2
    if args.daily_quota <= 0:
        print("Error: --daily-quota must be greater than 0.", file=sys.stderr)
        return 2

    proxy_disabled = not args.keep_proxy
    if proxy_disabled:
        for key in PROXY_BYPASS_ENV_KEYS:
            os.environ.pop(key, None)

    opener = build_opener(disable_proxy=proxy_disabled)

    try:
        login_data = login_by_card(opener, args.card, args.agent)
        token = str(login_data.get("token") or "").strip()
        if not token:
            raise ApiError("Missing token in login response")
        whoami_data = query_whoami(opener, token)
        summary = build_summary(
            user_data=whoami_data,
            daily_quota=args.daily_quota,
            agent=args.agent,
            proxy_disabled=proxy_disabled,
        )
    except ApiError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(format_text(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())

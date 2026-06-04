#!/usr/bin/env python3
"""Trigger an outbound Mr. Med follow-up call via the running agent server."""

from __future__ import annotations

import argparse
import json
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv(override=True)

DEFAULT_PORT = 7860
DEFAULT_PRODUCT = "Oxiage LG Tablet"
DEFAULT_QUANTITY = 10
DEFAULT_WHEN = "1 week ago"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Initiate an outbound Exotel call through the Mr. Med agent"
    )
    parser.add_argument(
        "--phone",
        required=True,
        help="Customer mobile number (10 digits, with or without +91)",
    )
    parser.add_argument(
        "--name",
        default="Customer",
        help="Customer name for identity verification",
    )
    parser.add_argument(
        "--product",
        default=DEFAULT_PRODUCT,
        help="Product for reorder follow-up",
    )
    parser.add_argument(
        "--quantity",
        type=int,
        default=DEFAULT_QUANTITY,
        help="Units purchased previously",
    )
    parser.add_argument(
        "--when",
        default=DEFAULT_WHEN,
        help="When they last purchased (e.g. '1 week ago')",
    )
    parser.add_argument(
        "--server-url",
        default=os.getenv("AGENT_SERVER_URL", f"http://127.0.0.1:{DEFAULT_PORT}"),
        help="Agent server base URL (must be running with -t exotel)",
    )
    args = parser.parse_args()

    phone = "".join(c for c in args.phone if c.isdigit())
    if phone.startswith("91") and len(phone) > 10:
        phone = phone[2:]
    if len(phone) != 10:
        print(f"Error: invalid phone number {args.phone!r} — need 10-digit Indian mobile")
        return 1

    payload = {
        "dialout_settings": {
            "phone_number": phone,
            "custom_field": {
                "call_type": "outbound",
                "name": args.name,
                "product": args.product,
                "last_purchase_quantity": args.quantity,
                "last_purchase_when": args.when,
            },
        }
    }

    url = f"{args.server_url.rstrip('/')}/dialout"
    print(f"POST {url}")
    print(json.dumps(payload, indent=2))

    try:
        resp = requests.post(url, json=payload, timeout=30)
    except requests.RequestException as e:
        print(f"Error: could not reach agent server at {url}")
        print(f"  {e}")
        print("Ensure the agent is running: uv run server.py -t exotel")
        return 1

    try:
        body = resp.json()
    except ValueError:
        body = {"raw": resp.text}

    if resp.status_code != 200:
        print(f"Dial-out failed ({resp.status_code}):")
        print(json.dumps(body, indent=2))
        return 1

    print("Call initiated successfully:")
    print(json.dumps(body, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

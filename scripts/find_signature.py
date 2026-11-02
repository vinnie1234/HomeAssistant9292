"""Offline check: which message format reproduces the x-validation-token from a real browser request.

Uses only the values from the browser request (no network). Run: python scripts/find_signature.py "<full request URL copied from the browser>"
The URL is read from the command line so no personal address is stored in the repo.
"""

import hashlib
import hmac
import itertools
import sys
from urllib.parse import unquote

KEY = "ZVWm_Qytmq.Bo-guenFtRfUPi_vMFq4yrdDA6RYZAijNi4qocHmq6oZ"
REQUEST_TIME = "1793621658981"
TOKEN = "77e28b65453ccb8a9c52f384726caf70383bd0fded5104a2a8c4d8b84c014983"
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36 Edg/156.0.0.0",
    "",
]
if len(sys.argv) != 2 or "?" not in sys.argv[1]:
    sys.exit('Usage: python scripts/find_signature.py "https://web-api.9292.nl/api/v1/plans?from=...&to=..."')
QUERY = sys.argv[1].split("?", 1)[1]
QUERIES = {"encoded": QUERY, "decoded": unquote(QUERY), "slash-decoded": QUERY.replace("%2F", "/"), "none": ""}
URLS = [
    "/api/v1/plans", "api/v1/plans", "/v1/plans", "v1/plans", "/plans", "plans", "",
    "https://web-api.9292.nl/api/v1/plans", "web-api.9292.nl/api/v1/plans",
    "https://web-api.9292.nl/v1/plans", "https://web-api.9292.nl/plans",
]
SEPARATORS = ["?", ""]

found = False
for url, (qname, query), separator, agent in itertools.product(URLS, QUERIES.items(), SEPARATORS, USER_AGENTS):
    suffix = f"{separator}{query}" if query else ""
    message = f"{REQUEST_TIME}{url}{suffix}{agent}"
    if hmac.new(KEY.encode(), message.encode(), hashlib.sha256).hexdigest() == TOKEN:
        print(f"MATCH url={url!r} query={qname} separator={separator!r} user_agent={'yes' if agent else 'no'}")
        found = True
if not found:
    print("No match: send the code around the request (where url/params are set and the params serializer).")

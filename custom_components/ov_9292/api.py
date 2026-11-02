"""Client for the 9292 journey planner, including the request signature its web app sends."""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from datetime import datetime, timezone
from urllib.parse import quote

import aiohttp

from .const import API_URL, PLANS_AFTER

_LOGGER = logging.getLogger(__name__)

# The 9292 web app signs every request: HMAC-SHA256(key, f"{time}{url}{user_agent}") as hex,
# sent as x-validation-token next to x-request-time.
SIGNING_KEY = "ZVWm_Qytmq.Bo-guenFtRfUPi_vMFq4yrdDA6RYZAijNi4qocHmq6oZ"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36 Edg/156.0.0.0"
)
# What the web app puts in front of the query in the signature is not certain
# (path only, or full URL), so these are tried in order until one is accepted.
SIGNED_URL_VARIANTS = ("/api/v1/plans", "/plans", "/v1/plans", API_URL)

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "nl",
    "origin": "https://9292.nl",
    "referer": "https://9292.nl/",
    "user-agent": USER_AGENT,
    "x-origin": "Plan",
}
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)


def sign(request_time: int, signed_url: str, query: str) -> str:
    message = f"{request_time}{signed_url}{'?' + query if query else ''}{USER_AGENT}"
    return hmac.new(SIGNING_KEY.encode(), message.encode(), hashlib.sha256).hexdigest()


def slugify(place: str) -> str:
    """'Veenendaal/Ida Gerhardtlaan 28' -> 'veenendaal/ida-gerhardtlaan-28' (the 9292 location id)."""
    return "/".join("-".join(part.lower().split()) for part in place.strip().split("/"))


def build_query(route: dict, when: datetime | None = None) -> str:
    when = (when or datetime.now(timezone.utc)).astimezone(timezone.utc)
    less_walking = str(bool(route.get("less_walking"))).lower()
    params = {
        "from": slugify(route["from"]),
        "to": slugify(route["to"]),
        "requestType": "Departure",
        "dateTime": when.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
    }
    if route.get("excluded_modes"):
        params["excludedTravelModes"] = ",".join(route["excluded_modes"])
    params |= {
        "planWithAccessibility": str(bool(route.get("accessibility"))).lower(),
        "extraInterchangeTime": str(int(route.get("extra_interchange_time", 0))),
        "firstMileLessWalking": less_walking,
        "lastMileLessWalking": less_walking,
        "firstMileModality": "Walking",
        "lastMileModality": "Walking",
        "previewsBefore": "0",
        "previewsAfter": str(PLANS_AFTER),
    }
    return "&".join(f"{key}={quote(value, safe='')}" for key, value in params.items())


class NineTwoNineTwoClient:
    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        self._variant = 0  # index in SIGNED_URL_VARIANTS that was accepted last

    async def async_plans(self, route: dict) -> dict:
        """The raw plans response for a route, departing now."""
        query = build_query(route)
        order = [*range(self._variant, len(SIGNED_URL_VARIANTS)), *range(self._variant)]
        for index in order:
            request_time = int(time.time() * 1000)
            headers = {
                **HEADERS,
                "x-request-time": str(request_time),
                "x-validation-token": sign(request_time, SIGNED_URL_VARIANTS[index], query),
            }
            async with self._session.get(
                f"{API_URL}?{query}", headers=headers, timeout=REQUEST_TIMEOUT
            ) as response:
                if response.status == 401:
                    _LOGGER.debug("9292 rejected signature variant %s", SIGNED_URL_VARIANTS[index])
                    continue
                response.raise_for_status()
                self._variant = index
                return await response.json()
        raise aiohttp.ClientError("9292 rejected the request signature (401)")

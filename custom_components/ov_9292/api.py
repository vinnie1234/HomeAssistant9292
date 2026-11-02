"""Client for the 9292 journey planner, including the request signature its web app sends."""

from __future__ import annotations

import hashlib
import hmac
import time
from datetime import datetime, timezone
from urllib.parse import quote, quote_plus

import aiohttp
from yarl import URL

from .const import API_BASE_URL, PLANS_AFTER, TRAVEL_MODES

# The 9292 web app signs every request: HMAC-SHA256(key, f"{time}{path}?{query}{user_agent}") as hex,
# sent as x-validation-token next to x-request-time.
SIGNING_KEY = "ZVWm_Qytmq.Bo-guenFtRfUPi_vMFq4yrdDA6RYZAijNi4qocHmq6oZ"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36 Edg/156.0.0.0"
)

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "nl",
    "origin": "https://9292.nl",
    "referer": "https://9292.nl/",
    "user-agent": USER_AGENT,
    "x-origin": "Plan",
}
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)


def sign(request_time: int, signed_path: str, user_agent: str = USER_AGENT) -> str:
    """Token for a request; signed_path is the path plus '?query', as the web app builds it."""
    message = f"{request_time}{signed_path}{user_agent}"
    return hmac.new(SIGNING_KEY.encode(), message.encode(), hashlib.sha256).hexdigest()


def encode_query(params: dict[str, str]) -> str:
    """Encoded like the browser's URLSearchParams: '/' as %2F, ':' as %3A, space as '+'."""
    return "&".join(f"{quote_plus(key)}={quote_plus(value)}" for key, value in params.items())


def slugify(place: str) -> str:
    """'Utrecht/Voorbeeldstraat 1' -> 'utrecht/voorbeeldstraat-1' (the 9292 location id)."""
    return "/".join("-".join(part.lower().split()) for part in place.strip().split("/"))


def plan_params(route: dict, when: datetime | None = None, request_type: str = "Departure") -> dict[str, str]:
    """Query for a route; request_type "Arrival" makes `when` the time to be there by."""
    when = (when or datetime.now(timezone.utc)).astimezone(timezone.utc)
    less_walking = str(bool(route.get("less_walking"))).lower()
    params = {
        "from": slugify(route["from"]),
        "to": slugify(route["to"]),
        "requestType": request_type,
        "dateTime": when.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
    }
    if route.get("excluded_modes"):
        params["excludedTravelModes"] = ",".join(TRAVEL_MODES[mode] for mode in route["excluded_modes"])
    return params | {
        "planWithAccessibility": str(bool(route.get("accessibility"))).lower(),
        "extraInterchangeTime": str(int(route.get("extra_interchange_time", 0))),
        "firstMileLessWalking": less_walking,
        "lastMileLessWalking": less_walking,
        "firstMileModality": "Walking",
        "lastMileModality": "Walking",
        "previewsBefore": "0",
        "previewsAfter": str(PLANS_AFTER),
    }


def parse_lat_long(text: str | None) -> list[float] | None:
    """'52.019739,5.549046' -> [52.019739, 5.549046]."""
    try:
        latitude, longitude = (float(part) for part in (text or "").split(","))
    except ValueError:
        return None
    return [latitude, longitude]


class NineTwoNineTwoClient:
    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def async_plans(
        self, route: dict, when: datetime | None = None, request_type: str = "Departure"
    ) -> dict:
        """The raw plans response for a route; departing now unless a time is given."""
        return await self._get("plans", plan_params(route, when, request_type))

    async def async_locations(self, query: str, rows: int = 10) -> list[dict]:
        """Places, stations and stops matching the text, as 9292.nl suggests them."""
        raw = await self._get("locations", {"query": query, "rows": str(rows)})
        return raw.get("locations", [])

    async def async_journey(self, journey_id: str) -> dict:
        """The legs, stops and route of one journey from the plans response."""
        return await self._get(f"journey/{quote(journey_id, safe='')}", {})

    async def _get(self, endpoint: str, params: dict[str, str]) -> dict:
        path = f"/api/v1/{endpoint}"
        # Without parameters the web app signs the bare path, without a '?'
        signed_path = f"{path}?{encode_query(params)}" if params else path
        request_time = int(time.time() * 1000)
        headers = {
            **HEADERS,
            "x-request-time": str(request_time),
            "x-validation-token": sign(request_time, signed_path),
        }
        # encoded=True: aiohttp must send the query exactly as signed (it would otherwise
        # turn %2F and %3A back into "/" and ":", which changes the signature)
        async with self._session.get(
            URL(f"{API_BASE_URL}{signed_path}", encoded=True), headers=headers, timeout=REQUEST_TIMEOUT
        ) as response:
            response.raise_for_status()
            return await response.json()

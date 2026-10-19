"""Bounded, single-request access to Amap's fixed Web Service endpoints."""

import json
import re
from typing import Any

import probatio as vol
from aiohttp import ClientError, ClientSession, ClientTimeout

MAX_AMAP_BYTES = 262_144
_LOCATION = re.compile(
    r"(-?[0-9]{1,3}(?:\.[0-9]{1,6})?),(-?[0-9]{1,2}(?:\.[0-9]{1,6})?)\Z"
)
_PATHS = frozenset(
    {
        "/v5/place/text",
        "/v5/place/around",
        "/v3/geocode/geo",
        "/v5/direction/driving",
        "/v5/direction/walking",
        "/v5/direction/bicycling",
        "/v5/direction/motor",
        "/v3/direction/transit/integrated",
        "/v4/etd/driving",
    }
)


def validate_location(value: Any) -> str:
    """Accept explicit GCJ-02 longitude,latitude, without conversion or guessing."""
    if not isinstance(value, str) or not _LOCATION.fullmatch(value.strip()):
        raise vol.Invalid("Expected GCJ-02 longitude,latitude with at most 6 decimals")
    value = value.strip()
    longitude, latitude = map(float, value.split(","))
    if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
        raise vol.Invalid("Coordinates are outside longitude/latitude bounds")
    return value


class AmapError(Exception):
    """A fixed category only; never carry provider bodies, URLs, or credentials."""


class AmapClient:
    """No retries, redirects, response cache, arbitrary URLs or raw error output."""

    def __init__(self, session: ClientSession, api_key: str) -> None:
        self._session = session
        self._api_key = api_key

    async def _request(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        if path not in _PATHS:
            raise AmapError("unsupported_endpoint")
        try:
            async with self._session.get(
                f"https://restapi.amap.com{path}",
                params={**params, "key": self._api_key, "output": "json"},
                allow_redirects=False,
                timeout=ClientTimeout(total=10),
            ) as response:
                if response.status != 200:
                    raise AmapError("http_error")
                body = bytearray()
                async for chunk in response.content.iter_chunked(16_384):
                    if len(body) + len(chunk) > MAX_AMAP_BYTES:
                        raise AmapError("response_too_large")
                    body.extend(chunk)
        except ClientError, TimeoutError:
            raise AmapError("request_failed") from None
        try:
            data = json.loads(body)
        except ValueError, UnicodeError, RecursionError:
            raise AmapError("invalid_response") from None
        if not isinstance(data, dict):
            raise AmapError("invalid_response")
        accepted = data.get("status") == "1"
        if path == "/v4/etd/driving":
            accepted = type(data.get("errcode")) in {int, str} and data["errcode"] in (
                0,
                "0",
            )
        if not accepted:
            # This includes invalid/unauthorized keys and exhausted quotas.
            raise AmapError("provider_rejected")
        return data

    def _text(self, value: Any) -> str | None:
        """Amap sometimes represents missing strings as empty arrays."""
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            value.encode("utf-8")
        except UnicodeError:
            raise AmapError("invalid_response") from None
        return re.sub(
            re.escape(self._api_key), "[redacted]", value, flags=re.IGNORECASE
        )

    @staticmethod
    def _coordinates(value: Any) -> dict[str, float] | None:
        if value in (None, "", []):
            return None
        try:
            longitude, latitude = map(float, validate_location(value).split(","))
        except vol.Invalid:
            raise AmapError("invalid_response") from None
        return {"longitude": longitude, "latitude": latitude}

    async def find_places(
        self,
        query: str,
        *,
        city: str = "",
        location: str = "",
        radius: int = 5000,
        sort: str = "weight",
        limit: int = 5,
        types: str = "",
    ) -> dict[str, Any]:
        """Return only published POI fields from one bounded first page."""
        params = {
            "keywords": query,
            "page_size": limit,
            "page_num": 1,
            "show_fields": "business",
        }
        if city:
            params.update(region=city, city_limit="true")
        if types:
            params["types"] = types
        path = "/v5/place/text"
        if location:
            path = "/v5/place/around"
            params.update(location=location, radius=radius, sortrule=sort)
        data = await self._request(path, params)
        rows = data.get("pois")
        if not isinstance(rows, list):
            raise AmapError("invalid_response")
        results = []
        for row in rows[:limit]:
            if not isinstance(row, dict) or not (name := self._text(row.get("name"))):
                raise AmapError("invalid_response")
            place: dict[str, Any] = {"name": name}
            for source, target in (
                ("id", "id"),
                ("address", "address"),
                ("cityname", "city"),
                ("adname", "district"),
                ("adcode", "adcode"),
                ("distance", "distance_meters"),
            ):
                if text := self._text(row.get(source)):
                    place[target] = text
            if coordinates := self._coordinates(row.get("location")):
                place["location"] = coordinates
            business = row.get("business")
            if isinstance(business, dict):
                for source, target in (
                    ("tel", "phone"),
                    ("rating", "rating"),
                    ("opentime_today", "opening_hours_today"),
                    ("opentime_week", "regular_open_hours"),
                ):
                    if text := self._text(business.get(source)):
                        place[target] = text
            results.append(place)
        return {
            "source": "amap",
            "coordinate_system": "GCJ-02",
            "results": results,
            "returned_count": len(results),
            "results_limited": len(rows) > limit,
        }

    async def geocode(self, address: str, *, city: str = "") -> dict[str, Any]:
        """Keep multiple address candidates; never silently choose a destination."""
        params = {"address": address}
        if city:
            params["city"] = city
        data = await self._request("/v3/geocode/geo", params)
        rows = data.get("geocodes")
        if not isinstance(rows, list):
            raise AmapError("invalid_response")
        results = []
        for row in rows[:5]:
            if not isinstance(row, dict):
                raise AmapError("invalid_response")
            address = self._text(row.get("formatted_address"))
            location = self._coordinates(row.get("location"))
            if not address or not location:
                raise AmapError("invalid_response")
            place = {"address": address, "location": location}
            for source, target in (
                ("province", "province"),
                ("city", "city"),
                ("district", "district"),
                ("adcode", "adcode"),
                ("level", "match_level"),
            ):
                if text := self._text(row.get(source)):
                    place[target] = text
            results.append(place)
        return {
            "source": "amap",
            "coordinate_system": "GCJ-02",
            "results": results,
            "ambiguous": len(rows) > 1,
            "returned_count": len(results),
            "results_limited": len(rows) > 5,
        }

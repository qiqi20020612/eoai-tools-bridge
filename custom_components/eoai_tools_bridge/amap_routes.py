"""Amap route resolution and explicit mode/time mapping; no implicit location."""

import math
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import probatio as vol

from .amap_client import AmapClient, AmapError, validate_location
from .validation import validate_query

ROUTE_MODES = ("DRIVE", "WALK", "BICYCLE", "TRANSIT", "TWO_WHEELER")
ROUTE_PATHS = {
    "DRIVE": "/v5/direction/driving",
    "WALK": "/v5/direction/walking",
    "BICYCLE": "/v5/direction/bicycling",
    "TRANSIT": "/v3/direction/transit/integrated",
    "TWO_WHEELER": "/v5/direction/motor",
}
FUTURE_DRIVING_PATH = "/v4/etd/driving"
_CHINA = ZoneInfo("Asia/Shanghai")
_NUMERIC_COORDINATES = re.compile(r"[0-9+\-.eEnNaAiIfF,;|\s]+\Z", re.ASCII)
_RELATIVE = frozenset(
    {
        "home",
        "here",
        "my location",
        "current location",
        "我家",
        "家",
        "这里",
        "当前位置",
    }
)


def validate_endpoint(value: Any) -> str:
    """Accept a bounded address or strictly formatted, already-GCJ-02 point."""
    value = validate_query(value)
    if value.casefold() in _RELATIVE:
        raise vol.Invalid(
            "Use an address/GCJ-02 point; omit origin for configured home"
        )
    if _NUMERIC_COORDINATES.fullmatch(value):
        return validate_location(value)
    return value


def validate_departure_time(value: Any) -> str:
    """Do not turn malformed, naive or historical times into current estimates."""
    value = validate_query(value)
    try:
        parsed = datetime.fromisoformat(value)
        if "T" not in value or parsed.utcoffset() is None:
            raise ValueError
        parsed.astimezone(UTC)
    except ValueError, OverflowError:
        raise vol.Invalid("Expected ISO 8601 departure time with timezone") from None
    return value


def _point(location: dict[str, float]) -> str:
    return ",".join(
        f"{location[key]:.6f}".rstrip("0").rstrip(".")
        for key in ("longitude", "latitude")
    )


def _measure(value: Any) -> int | float:
    """Provider distances/times must be real non-negative numbers, never defaults."""
    if isinstance(value, str):
        if len(value) > 20 or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value, re.ASCII):
            raise AmapError("invalid_response")
    elif type(value) not in {int, float}:
        raise AmapError("invalid_response")
    try:
        number = float(value)
    except OverflowError:
        raise AmapError("invalid_response") from None
    if not math.isfinite(number) or not 0 <= number <= 1_000_000_000:
        raise AmapError("invalid_response")
    return int(number) if number.is_integer() else number


def _duration(seconds: int | float) -> str:
    hours, remaining = divmod(round(seconds), 3600)
    minutes, seconds = divmod(remaining, 60)
    return (
        " ".join(
            f"{value} {unit}"
            for value, unit in ((hours, "hr"), (minutes, "min"), (seconds, "sec"))
            if value
        )
        or "0 sec"
    )


class AmapRoutes:
    """At most two geocodes and one route request, each freshly authorized."""

    def __init__(
        self, client: AmapClient, check: Callable[[], Awaitable[None]]
    ) -> None:
        self._client = client
        self._check = check

    async def _resolve(self, query: str, city: str) -> dict[str, Any]:
        try:
            location = validate_location(query)
        except vol.Invalid:
            await self._check()
            result = await self._client.geocode(query, city=city)
            if result["ambiguous"] or not result["results"]:
                return {
                    "status": (
                        "needs_clarification" if result["ambiguous"] else "no_match"
                    ),
                    "query": query,
                    "candidates": result["results"],
                    "ambiguous": result["ambiguous"],
                    "results_limited": result["results_limited"],
                }
            row = result["results"][0]
            return {**({"city_hint": city} if city else {}), "query": query, **row}
        return {
            "query": query,
            "location": self._client._coordinates(location),
            **({"city_hint": city} if city else {}),
        }

    async def get_route(
        self,
        *,
        origin: str,
        destination: str,
        mode: str,
        origin_city: str = "",
        destination_city: str = "",
        departure_time: str | None = None,
    ) -> dict[str, Any]:
        departure = None
        if departure_time is not None:
            departure = datetime.fromisoformat(departure_time).astimezone(UTC)
            if mode not in {"DRIVE", "TRANSIT"}:
                raise AmapError("departure_time_unsupported")
            departure = departure.replace(microsecond=0)
            if mode == "TRANSIT":
                departure = departure.replace(second=0)
            self._validate_future(departure)
        result: dict[str, Any] = {
            "source": "amap",
            "coordinate_system": "GCJ-02",
            "travel_mode": mode,
            "route": None,
        }
        points = {}
        for endpoint, query, city in (
            ("origin", origin, origin_city),
            ("destination", destination, destination_city),
        ):
            point = await self._resolve(query, city)
            if "status" in point:
                return {**result, **point, "endpoint": endpoint}
            points[endpoint] = point
        result.update(points)
        params: dict[str, Any] = {
            name: _point(point["location"]) for name, point in points.items()
        }
        path = ROUTE_PATHS[mode]
        if mode == "TRANSIT":
            for name, param in (("origin", "city"), ("destination", "cityd")):
                city = points[name].get("city") or points[name].get("city_hint")
                if not city or (city.isdecimal() and len(city) not in {3, 4}):
                    return {
                        **result,
                        "status": "city_required",
                        "endpoint": name,
                    }
                params[param] = city
            params.update(strategy=0, extensions="base")
            if departure:
                local = departure.astimezone(_CHINA)
                params.update(
                    date=local.strftime("%Y-%m-%d"), time=local.strftime("%H:%M")
                )
        else:
            params["show_fields"] = "cost"
            if mode == "DRIVE":
                params["strategy"] = 32  # Amap default recommendation with traffic.
        if departure and mode == "DRIVE":
            path = FUTURE_DRIVING_PATH
            params = {
                "origin": params["origin"],
                "destination": params["destination"],
                "firsttime": int(departure.timestamp()),
                "interval": 60,
                "count": 1,
                "strategy": 1,
            }
        if departure:
            self._validate_future(departure)
        await self._check()
        data = await self._client._request(path, params)
        route, alternatives = self._parse(
            data, mode, departure=departure if path == FUTURE_DRIVING_PATH else None
        )
        result.update(
            status="ok" if route else "no_route",
            route=route,
            alternatives_available=alternatives,
            time_basis=(
                "future_traffic_estimate"
                if departure and mode == "DRIVE"
                else "timetable"
                if mode == "TRANSIT"
                else "current_traffic_estimate"
                if mode == "DRIVE"
                else "untimed_estimate"
            ),
        )
        if departure:
            result["departure_time"] = departure.isoformat()
            if route:
                result["estimated_arrival"] = (
                    departure + timedelta(seconds=route["duration_seconds"])
                ).isoformat()
        return result

    @staticmethod
    def _validate_future(departure: datetime) -> None:
        now = datetime.now(UTC)
        if not now < departure <= now + timedelta(days=7):
            raise AmapError("departure_time_out_of_range")

    @staticmethod
    def _parse(
        data: dict, mode: str, *, departure: datetime | None
    ) -> tuple[dict | None, bool]:
        parent = data.get("data" if departure else "route")
        if not isinstance(parent, dict):
            raise AmapError("invalid_response")
        paths = parent.get("transits" if mode == "TRANSIT" else "paths")
        if paths is None and data.get("count") == "0":
            paths = []
        if not isinstance(paths, list):
            raise AmapError("invalid_response")
        if not paths:
            return None, False
        path = paths[0]
        if not isinstance(path, dict):
            raise AmapError("invalid_response")
        distance = _measure(path.get("distance"))
        if departure:
            infos = parent.get("time_infos")
            if not isinstance(infos, list) or len(infos) != 1:
                raise AmapError("invalid_response")
            info = infos[0]
            start = info.get("starttime") if isinstance(info, dict) else None
            if type(start) not in {str, int} or str(start) != str(
                int(departure.timestamp()) * 1000
            ):
                raise AmapError("invalid_response")
            elements = info.get("elements") if isinstance(info, dict) else None
            if not isinstance(elements, list):
                raise AmapError("invalid_response")
            matching = [
                e
                for e in elements
                if isinstance(e, dict) and str(e.get("pathindex")) == "0"
            ]
            if len(matching) != 1:
                raise AmapError("invalid_response")
            seconds = _measure(matching[0].get("duration")) * 60  # v4 ETD: minutes.
        elif mode == "TRANSIT":
            seconds = _measure(path.get("duration"))
        elif mode == "BICYCLE" and "duration" in path:
            # The live v5 bicycle API returns duration here despite show_fields.
            seconds = _measure(path["duration"])
        else:
            cost = path.get("cost")
            if not isinstance(cost, dict):
                raise AmapError("invalid_response")
            seconds = _measure(cost.get("duration"))
        return {
            "distance_meters": distance,
            "duration_seconds": seconds,
            "distance": f"{distance / 1000:.1f} km"
            if distance >= 1000
            else f"{distance:g} m",
            "duration": _duration(seconds),
        }, len(paths) > 1

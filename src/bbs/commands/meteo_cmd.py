"""
Meteo command for MeshCore BBS.

Weather forecasts via Open-Meteo API (free, no API key required).

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import asyncio
import json
import logging
import urllib.request
import urllib.parse
from time import time
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from .base import BaseCommand, CommandContext, CommandResult, CommandRegistry

logger = logging.getLogger(__name__)

# Cache with size limits
_meteo_cache = {}  # "lat,lon" -> (timestamp, data)
_geo_cache = {}    # "city" -> (timestamp, lat, lon, name)
CACHE_TTL = 600    # 10 minutes
CACHE_MAX = 50     # max entries per cache
HTTP_TIMEOUT = 3   # seconds (was 10, reduced for faster feedback)


def _evict_cache(cache, max_size=CACHE_MAX):
    """Remove expired entries and oldest if over limit."""
    now = time()
    expired = [k for k, v in cache.items() if now - v[0] > CACHE_TTL]
    for k in expired:
        del cache[k]
    while len(cache) > max_size:
        oldest = min(cache, key=lambda k: cache[k][0])
        del cache[oldest]

# WMO weather codes -> compact Italian text
_WMO = {
    0: "Sereno", 1: "Quasi sereno", 2: "Parz.nuvoloso", 3: "Nuvoloso",
    45: "Nebbia", 48: "Nebbia gelata",
    51: "Pioggerella", 53: "Pioggerella", 55: "Pioggerella forte",
    61: "Pioggia", 63: "Pioggia mod.", 65: "Pioggia forte",
    71: "Neve", 73: "Neve mod.", 75: "Neve forte",
    80: "Rovesci", 81: "Rovesci mod.", 82: "Rovesci forti",
    85: "Neve rovesci", 86: "Neve forte",
    95: "Temporale", 96: "Temporale grandine", 99: "Temporale grandine",
}


def _geocode(city: str) -> Optional[Tuple[float, float, str]]:
    """Convert city name to coordinates via Open-Meteo Geocoding API."""
    key = city.lower().strip()
    now = time()
    if key in _geo_cache:
        ts, lat, lon, name = _geo_cache[key]
        if now - ts < CACHE_TTL:
            return lat, lon, name

    encoded = urllib.parse.quote(city)
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={encoded}&count=1&language=it"
    try:
        resp = urllib.request.urlopen(url, timeout=HTTP_TIMEOUT)
        data = json.loads(resp.read())
        results = data.get("results", [])
        if not results:
            return None
        r = results[0]
        lat, lon = r["latitude"], r["longitude"]
        name = r.get("name", city)
        _evict_cache(_geo_cache)
        _geo_cache[key] = (now, lat, lon, name)
        return lat, lon, name
    except Exception as e:
        logger.error(f"Geocoding error for '{city}': {e}")
        return None


def _fetch_meteo(lat: float, lon: float) -> Optional[dict]:
    """Fetch weather from Open-Meteo API."""
    cache_key = f"{lat:.2f},{lon:.2f}"
    now = time()
    if cache_key in _meteo_cache:
        ts, data = _meteo_cache[cache_key]
        if now - ts < CACHE_TTL:
            return data

    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code"
        f"&daily=weather_code,temperature_2m_max,temperature_2m_min"
        f"&timezone=Europe/Rome&forecast_days=3"
    )
    try:
        resp = urllib.request.urlopen(url, timeout=HTTP_TIMEOUT)
        data = json.loads(resp.read())
        _evict_cache(_meteo_cache)
        _meteo_cache[cache_key] = (now, data)
        return data
    except Exception as e:
        logger.error(f"Meteo fetch error: {e}")
        return None


def _format_meteo(data: dict, location: str) -> str:
    """Format weather data into compact string."""
    c = data.get("current", {})
    d = data.get("daily", {})

    temp = c.get("temperature_2m", "?")
    hum = c.get("relative_humidity_2m", "?")
    wind = c.get("wind_speed_10m", "?")
    code = c.get("weather_code", 0)

    lines = [f"[BBS] {location}: {temp}C {_WMO.get(code, '?')} U:{hum}% V:{wind}km/h"]

    times = d.get("time", [])
    mins = d.get("temperature_2m_min", [])
    maxs = d.get("temperature_2m_max", [])
    codes = d.get("weather_code", [])

    for i in range(min(3, len(times))):
        day = times[i][5:]  # "MM-DD"
        lines.append(f"  {day}: {mins[i]}/{maxs[i]}C {_WMO.get(codes[i], '?')}")

    return "\n".join(lines)


@CommandRegistry.register
class MeteoCommand(BaseCommand):
    """Show weather forecast."""

    name = "meteo"
    description = "Previsioni meteo"
    usage = "!meteo [citta]\n  !meteo Roma\n  !meteo (usa posizione BBS)"
    aliases = ["weather", "tempo"]

    def __init__(self, session: Session):
        self.session = session

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        if args:
            # !meteo <city>
            city = " ".join(args)
            geo = await asyncio.to_thread(_geocode, city)
            if not geo:
                return CommandResult.fail(f"[BBS] Citta '{city}' non trovata")
            lat, lon, name = geo
        else:
            # !meteo without args = BBS location
            from utils.config import get_config
            cfg = get_config()
            lat = cfg.latitude
            lon = cfg.longitude
            name = "Qui"

            if not lat or not lon:
                return CommandResult.fail(
                    "[BBS] Posizione BBS non configurata.\nUsa: !meteo <citta>"
                )

        data = await asyncio.to_thread(_fetch_meteo, lat, lon)
        if not data:
            return CommandResult.fail("[BBS] Meteo non disponibile")

        return CommandResult.ok(_format_meteo(data, name))

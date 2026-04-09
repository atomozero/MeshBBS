# modules/meteo.py — Meteo via Open-Meteo API (gratuita, no API key)
import asyncio
import json
import logging
import urllib.request
import urllib.parse
from time import time

from dispatcher import command
from config import (
    NODE_LAT, NODE_LON,
    METEO_CACHE_TTL, METEO_HTTP_TIMEOUT, METEO_CACHE_MAX, GEOCACHE_MAX,
)

log = logging.getLogger(__name__)
_cache: dict[str, tuple[float, dict]] = {}
_geocache: dict[str, tuple[float, float, float, str]] = {}  # nome -> (ts, lat, lon, nome)

# Codici WMO meteo -> testo compatto
_WMO_CODES = {
    0: "Sereno", 1: "Quasi sereno", 2: "Parz.nuvoloso", 3: "Nuvoloso",
    45: "Nebbia", 48: "Nebbia gelata",
    51: "Pioggerella", 53: "Pioggerella", 55: "Pioggerella forte",
    61: "Pioggia", 63: "Pioggia mod.", 65: "Pioggia forte",
    71: "Neve", 73: "Neve mod.", 75: "Neve forte",
    80: "Rovesci", 81: "Rovesci mod.", 82: "Rovesci forti",
    85: "Neve rovesci", 86: "Neve forte",
    95: "Temporale", 96: "Temporale grandine", 99: "Temporale grandine",
}

# Riferimento alla connessione companion per leggere le coordinate
_conn = None


def set_connection(conn):
    global _conn
    _conn = conn


def _evict_cache(cache: dict, max_size: int, ttl: float):
    """Rimuove entry scaduti; se ancora troppi, rimuove i piu' vecchi."""
    now = time()
    expired = [k for k, (ts, *_) in cache.items() if now - ts > ttl]
    for k in expired:
        del cache[k]
    while len(cache) > max_size:
        oldest = min(cache, key=lambda k: cache[k][0])
        del cache[oldest]


def _get_coords() -> tuple[float, float]:
    """Restituisce lat, lon dal companion o default."""
    if _conn and _conn.self_info:
        si = _conn.self_info
        lat = si.get("adv_lat", 0)
        lon = si.get("adv_lon", 0)
        if lat and lon:
            return lat, lon
    return NODE_LAT, NODE_LON


def _geocode(city: str) -> tuple[float, float, str] | None:
    """Converte nome citta' in coordinate via Open-Meteo Geocoding API."""
    key = city.lower().strip()
    if key in _geocache:
        _ts, lat, lon, name = _geocache[key]
        return lat, lon, name

    encoded = urllib.parse.quote(city)
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={encoded}&count=1&language=it"
    try:
        resp = urllib.request.urlopen(url, timeout=METEO_HTTP_TIMEOUT)
        data = json.loads(resp.read())
        results = data.get("results", [])
        if not results:
            return None
        r = results[0]
        lat = r["latitude"]
        lon = r["longitude"]
        name = r.get("name", city)
        _evict_cache(_geocache, GEOCACHE_MAX, METEO_CACHE_TTL)
        _geocache[key] = (time(), lat, lon, name)
        return lat, lon, name
    except Exception as e:
        log.error("Errore geocoding '%s': %s", city, e)
        return None


def _fetch_meteo(lat: float, lon: float) -> dict | None:
    """Fetch meteo da Open-Meteo API."""
    cache_key = f"{lat:.2f},{lon:.2f}"
    now = time()
    if cache_key in _cache:
        cached_time, cached_data = _cache[cache_key]
        if now - cached_time < METEO_CACHE_TTL:
            return cached_data

    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code"
        f"&daily=weather_code,temperature_2m_max,temperature_2m_min"
        f"&timezone=Europe/Rome&forecast_days=3"
    )
    try:
        resp = urllib.request.urlopen(url, timeout=METEO_HTTP_TIMEOUT)
        data = json.loads(resp.read())
        _evict_cache(_cache, METEO_CACHE_MAX, METEO_CACHE_TTL)
        _cache[cache_key] = (now, data)
        return data
    except Exception as e:
        log.error("Errore fetch meteo: %s", e)
        return None


def _wmo(code: int) -> str:
    return _WMO_CODES.get(code, f"cod.{code}")


def _format_meteo(data: dict, location: str) -> str:
    """Formatta i dati meteo in una stringa compatta."""
    c = data.get("current", {})
    d = data.get("daily", {})

    temp = c.get("temperature_2m", "?")
    hum = c.get("relative_humidity_2m", "?")
    wind = c.get("wind_speed_10m", "?")
    code = c.get("weather_code", 0)

    lines = [f"{location}: {temp}C {_wmo(code)} U:{hum}% V:{wind}km/h"]

    times = d.get("time", [])
    mins = d.get("temperature_2m_min", [])
    maxs = d.get("temperature_2m_max", [])
    codes = d.get("weather_code", [])

    for i in range(min(3, len(times))):
        day = times[i][5:]  # "MM-DD"
        lines.append(f"{day}: {mins[i]}/{maxs[i]}C {_wmo(codes[i])}")

    return "\n".join(lines)


@command("!meteo")
async def cmd_meteo(from_pubkey, args, db) -> str:
    if args:
        # !meteo <citta'> — HTTP in thread per non bloccare event loop
        city = " ".join(args)
        geo = await asyncio.to_thread(_geocode, city)
        if not geo:
            return f"Citta' '{city}' non trovata"
        lat, lon, name = geo
        data = await asyncio.to_thread(_fetch_meteo, lat, lon)
        if not data:
            return "Meteo non disponibile"
        return _format_meteo(data, name)
    else:
        # !meteo senza argomenti = posizione BBS
        lat, lon = _get_coords()
        data = await asyncio.to_thread(_fetch_meteo, lat, lon)
        if not data:
            return "Meteo non disponibile"
        return _format_meteo(data, "Qui")

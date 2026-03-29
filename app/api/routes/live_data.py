"""Live Data API — real-time stock, crypto, and weather data.
All three data types use free, no-key APIs with optional upgrade paths.
  - Stocks: Yahoo Finance (free via yfinance) → Alpha Vantage if key set
  - Crypto: CoinGecko (free, no key needed)
  - Weather: Open-Meteo (free, no key needed)
Mounted at: GET /data/live?type=stock&symbol=AAPL
Called by: frontend LiveDataWidget component via SSE [[LIVE:...]] markers."""

import logging
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional, Any, Dict

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data", tags=["live-data"])


class LiveDataResponse(BaseModel):
    """Response from any live data endpoint."""
    type: str           # "stock" | "crypto" | "weather"
    symbol: str
    data: Dict[str, Any]
    source: str         # which API was used
    cached: bool = False


@router.get("/live", response_model=LiveDataResponse)
async def get_live_data(
    type: str = Query(..., description="stock | crypto | weather"),
    symbol: str = Query(..., description="Ticker (AAPL), coin id (bitcoin), or city (London)"),
    lat: Optional[float] = Query(None, description="Latitude for weather"),
    lon: Optional[float] = Query(None, description="Longitude for weather"),
):
    """Fetch fresh real-time data for stocks, crypto, or weather.

    Examples:
      GET /data/live?type=stock&symbol=AAPL
      GET /data/live?type=crypto&symbol=bitcoin
      GET /data/live?type=weather&symbol=London
      GET /data/live?type=weather&symbol=weather&lat=40.7&lon=-74.0
    """
    data_type = type.lower()

    try:
        if data_type == "stock":
            return await _fetch_stock(symbol)
        elif data_type == "crypto":
            return await _fetch_crypto(symbol)
        elif data_type == "weather":
            return await _fetch_weather(symbol, lat, lon)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown type '{type}'. Use: stock, crypto, weather")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Live data fetch failed ({type}/{symbol}): {e}")
        raise HTTPException(status_code=502, detail=f"Data fetch failed: {str(e)}")


# ---------------------------------------------------------------------------
# Stock data — yfinance (free) with Alpha Vantage upgrade
# ---------------------------------------------------------------------------

async def _fetch_stock(symbol: str) -> LiveDataResponse:
    """Fetch real-time stock quote. Uses yfinance (free, no key)."""
    import asyncio
    symbol = symbol.upper().strip()

    def _sync_fetch():
        try:
            import yfinance as yf  # type: ignore[import]
            ticker = yf.Ticker(symbol)
            info = ticker.fast_info
            hist = ticker.history(period="1d", interval="5m")

            price = getattr(info, "last_price", None) or getattr(info, "regularMarketPrice", None)
            prev_close = getattr(info, "previous_close", None)
            change_pct = None
            if price and prev_close:
                change_pct = round(((price - prev_close) / prev_close) * 100, 2)

            return {
                "symbol": symbol,
                "price": round(float(price), 2) if price else None,
                "change_pct": change_pct,
                "prev_close": round(float(prev_close), 2) if prev_close else None,
                "currency": getattr(info, "currency", "USD"),
                "market_cap": getattr(info, "market_cap", None),
            }
        except ImportError:
            raise RuntimeError("yfinance not installed. Run: pip install yfinance")

    data = await asyncio.to_thread(_sync_fetch)
    return LiveDataResponse(type="stock", symbol=symbol, data=data, source="yfinance")


# ---------------------------------------------------------------------------
# Crypto — CoinGecko (free, no key)
# ---------------------------------------------------------------------------

async def _fetch_crypto(coin_id: str) -> LiveDataResponse:
    """Fetch real-time crypto price from CoinGecko."""
    import httpx

    coin_id = coin_id.lower().strip()
    url = "https://api.coingecko.com/api/v3/simple/price"

    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.get(
            url,
            params={
                "ids": coin_id,
                "vs_currencies": "usd",
                "include_24hr_change": "true",
                "include_market_cap": "true",
                "include_24hr_vol": "true",
            },
        )
        resp.raise_for_status()
        raw = resp.json()

    if coin_id not in raw:
        raise HTTPException(status_code=404, detail=f"Coin '{coin_id}' not found in CoinGecko")

    coin_data = raw[coin_id]
    return LiveDataResponse(
        type="crypto",
        symbol=coin_id,
        data={
            "price_usd": coin_data.get("usd"),
            "change_24h_pct": coin_data.get("usd_24h_change"),
            "market_cap_usd": coin_data.get("usd_market_cap"),
            "volume_24h_usd": coin_data.get("usd_24h_vol"),
        },
        source="coingecko",
    )


# ---------------------------------------------------------------------------
# Weather — Open-Meteo (free, no key, GDPR-compliant)
# ---------------------------------------------------------------------------

async def _fetch_weather(location: str, lat: Optional[float], lon: Optional[float]) -> LiveDataResponse:
    """Fetch current weather from Open-Meteo (always free)."""
    import httpx

    # Geocode location name if lat/lon not provided
    if lat is None or lon is None:
        lat, lon, resolved_name = await _geocode(location)
    else:
        resolved_name = location

    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
                "timezone": "auto",
                "forecast_days": 1,
            },
        )
        resp.raise_for_status()
        raw = resp.json()

    current = raw.get("current", {})
    return LiveDataResponse(
        type="weather",
        symbol=location,
        data={
            "location": resolved_name,
            "temperature_c": current.get("temperature_2m"),
            "feels_like_c": current.get("apparent_temperature"),
            "humidity_pct": current.get("relative_humidity_2m"),
            "wind_speed_kmh": current.get("wind_speed_10m"),
            "weather_code": current.get("weather_code"),
            "condition": _wmo_description(current.get("weather_code", 0)),
            "lat": lat,
            "lon": lon,
        },
        source="open-meteo",
    )


async def _geocode(location: str) -> tuple[float, float, str]:
    """Resolve location name → lat/lon using Open-Meteo geocoding."""
    import httpx
    async with httpx.AsyncClient(timeout=6.0) as client:
        resp = await client.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": location, "count": 1, "language": "en", "format": "json"},
        )
        resp.raise_for_status()
        data = resp.json()

    results = data.get("results", [])
    if not results:
        raise HTTPException(status_code=404, detail=f"Location '{location}' not found")

    r = results[0]
    name = f"{r.get('name', location)}, {r.get('country', '')}"
    return float(r["latitude"]), float(r["longitude"]), name


def _wmo_description(code: int) -> str:
    """Map WMO weather code to human-readable condition."""
    _MAP = {
        0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Foggy", 48: "Icy fog",
        51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
        61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
        71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
        80: "Slight showers", 81: "Moderate showers", 82: "Violent showers",
        95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail",
    }
    return _MAP.get(code, f"Code {code}")


# ---------------------------------------------------------------------------
# Paper full text — Phase 4C (user-triggered arXiv PDF extraction)
# ---------------------------------------------------------------------------

class PaperTextResponse(BaseModel):
    """Response from the paper-text endpoint."""
    url: str
    text: str
    char_count: int
    source: str = "arxiv"


@router.get("/paper-text", response_model=PaperTextResponse)
async def get_paper_text(
    url: str = Query(..., description="Direct PDF URL from arXiv (e.g. https://arxiv.org/pdf/...)"),
    max_chars: int = Query(default=20000, ge=1000, le=60000, description="Max characters to extract"),
):
    """Extract and return full text from an arXiv PDF. User-triggered endpoint.
    Called by: frontend CitationsPanel 'Read full paper' button on arxiv sources.
    Uses PyMuPDF (fitz) for extraction. Returns error text if unavailable."""
    # Safety: only allow arxiv.org PDF URLs
    if "arxiv.org" not in url and "ar5iv.org" not in url:
        raise HTTPException(status_code=400, detail="Only arXiv PDF URLs are supported")

    from app.services.sources.arxiv_source import fetch_full_text
    text = await fetch_full_text(url, max_chars=max_chars)
    return PaperTextResponse(url=url, text=text, char_count=len(text))

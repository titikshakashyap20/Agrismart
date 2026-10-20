"""
AgriSmart Review 2 - Data Layer (Member 1's layer, extended)

Fetches real historical daily weather from NASA POWER (free, no API key)
for a configurable location/date range, caches it locally so re-runs don't
hit the network, and derives daily reference evapotranspiration (ET0) via
the Hargreaves-Samani equation - a standard, widely-cited simplified ET0
method that needs only Tmax/Tmin and the site's latitude (no solar-radiation
sensor or full Penman-Monteith input set required).

HOW TO USE:
    from data_layer import get_weather
    weather = get_weather()   # uses config.py values by default
    # -> DataFrame with columns: date, rain_mm, et0_mm

If NASA POWER is unreachable (e.g. no internet in a sandboxed environment),
this falls back to a synthetic weather generator so the rest of the
pipeline can still be exercised - clearly labelled, and NOT what should be
used for your reported Review 2 results.
"""

import os
import math
import numpy as np
import pandas as pd
import requests

import config

CACHE_DIR = "weather_cache"


def _cache_path(lat, lon, start, end):
    os.makedirs(CACHE_DIR, exist_ok=True)
    fname = f"power_{lat}_{lon}_{start}_{end}.csv"
    return os.path.join(CACHE_DIR, fname)


def _fetch_from_power(lat, lon, start, end):
    """One request to NASA POWER's free daily point API."""
    url = "https://power.larc.nasa.gov/api/temporal/daily/point"
    params = {
        "parameters": "T2M_MAX,T2M_MIN,PRECTOTCORR",
        "community": "AG",
        "longitude": lon,
        "latitude": lat,
        "start": start,
        "end": end,
        "format": "JSON",
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    payload = resp.json()["properties"]["parameter"]

    dates = sorted(payload["T2M_MAX"].keys())
    df = pd.DataFrame({
        "date": pd.to_datetime(dates, format="%Y%m%d"),
        "t2m_max": [payload["T2M_MAX"][d] for d in dates],
        "t2m_min": [payload["T2M_MIN"][d] for d in dates],
        "rain_mm": [payload["PRECTOTCORR"][d] for d in dates],
    })
    return df


def _synthetic_fallback(start, end, seed=config.RANDOM_SEED):
    """
    OFFLINE FALLBACK ONLY - used if NASA POWER can't be reached, so the
    pipeline can still be developed/tested without network access. Do not
    use this data for your reported Review 2 results; run get_weather()
    with network access at least once beforehand so the real data is cached.
    """
    rng = np.random.default_rng(seed)
    dates = pd.date_range(pd.to_datetime(start, format="%Y%m%d"),
                           pd.to_datetime(end, format="%Y%m%d"))
    n = len(dates)
    t2m_max = 30 + 3 * np.sin(np.linspace(0, 3.14, n)) + rng.normal(0, 1, n)
    t2m_min = t2m_max - 8 + rng.normal(0, 1, n)
    rain = rng.exponential(2.0, n) * (rng.random(n) < 0.3)
    return pd.DataFrame({"date": dates, "t2m_max": t2m_max,
                          "t2m_min": t2m_min, "rain_mm": rain})


def _hargreaves_et0(df, lat):
    """
    Hargreaves-Samani reference evapotranspiration (mm/day).
    ET0 = 0.0023 * (Tmean + 17.8) * sqrt(Tmax - Tmin) * 0.408*Ra
    where Ra (extraterrestrial radiation) is computed from latitude and
    day-of-year using the standard FAO-56 formulation.
    """
    doy = df["date"].dt.dayofyear.values
    lat_rad = math.radians(lat)

    dr = 1 + 0.033 * np.cos(2 * np.pi * doy / 365)
    delta = 0.409 * np.sin(2 * np.pi * doy / 365 - 1.39)
    ws = np.arccos(np.clip(-np.tan(lat_rad) * np.tan(delta), -1, 1))
    ra = (24 * 60 / np.pi) * 0.0820 * dr * (
        ws * np.sin(lat_rad) * np.sin(delta) +
        np.cos(lat_rad) * np.cos(delta) * np.sin(ws)
    )  # MJ m-2 day-1

    tmax, tmin = df["t2m_max"].values, df["t2m_min"].values
    tmean = (tmax + tmin) / 2
    et0 = 0.0023 * (tmean + 17.8) * np.sqrt(np.clip(tmax - tmin, 0, None)) * ra * 0.408
    return np.clip(et0, 0, None)


def get_weather(lat=config.LATITUDE, lon=config.LONGITUDE,
                 start=config.START_DATE, end=config.END_DATE,
                 use_cache=True):
    """Returns a DataFrame with columns: date, rain_mm, et0_mm."""
    path = _cache_path(lat, lon, start, end)

    if use_cache and os.path.exists(path):
        df = pd.read_csv(path, parse_dates=["date"])
        return df[["date", "rain_mm", "et0_mm"]]

    try:
        raw = _fetch_from_power(lat, lon, start, end)
        source = "NASA POWER"
    except Exception as e:
        print(f"[data_layer] NASA POWER request failed ({e}); "
              f"using synthetic fallback weather for offline testing only.")
        raw = _synthetic_fallback(start, end)
        source = "SYNTHETIC (offline fallback - do not use for reported results)"

    raw["et0_mm"] = _hargreaves_et0(raw, lat)
    raw["source"] = source
    raw.to_csv(path, index=False)
    print(f"[data_layer] Weather loaded from {source}, {len(raw)} days, cached at {path}")
    return raw[["date", "rain_mm", "et0_mm"]]


if __name__ == "__main__":
    w = get_weather()
    print(w.head())
    print(w.describe())
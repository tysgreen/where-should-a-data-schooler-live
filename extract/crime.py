"""Step 4: download street-level crimes within RADIUS_M of every station.

API:   https://data.police.uk/api/crimes-street/all-crime  (free, no key)
Saves: data/raw/police/{YYYY-MM}.jsonl.gz  (one file per month, one line per station)

Incremental: a month that is already saved is skipped. Police data is published
~2 months late, so each monthly run only needs to fetch the newest month.
"""
import gzip
import json
import math
import time

from api_helpers import envelope, make_session
from config import CRIME_MONTHS, RADIUS_M, RAW_DIR
from stations import load_station_points

OUT_DIR = RAW_DIR / "police"


def circle_polygon(lat: float, lon: float, radius_m: float, points: int = 16) -> str:
    """Approximate a circle around a point as a 16-sided polygon, in the
    'lat,lng:lat,lng:...' format the police API expects."""
    coords = []
    for i in range(points):
        angle = 2 * math.pi * i / points
        dlat = (radius_m * math.cos(angle)) / 111_320                       # metres per degree latitude
        dlon = (radius_m * math.sin(angle)) / (111_320 * math.cos(math.radians(lat)))
        coords.append(f"{lat + dlat:.6f},{lon + dlon:.6f}")
    return ":".join(coords)


def latest_months(session, n: int) -> list[str]:
    """Ask the API which month is the newest available, then count back n months."""
    r = session.get("https://data.police.uk/api/crime-last-updated", timeout=30)
    r.raise_for_status()
    year, month = map(int, r.json()["date"][:7].split("-"))
    months = []
    for _ in range(n):
        months.append(f"{year}-{month:02d}")
        year, month = (year, month - 1) if month > 1 else (year - 1, 12)
    return months


def main():
    session = make_session()
    stations = load_station_points()
    for month in latest_months(session, CRIME_MONTHS):
        path = OUT_DIR / f"{month}.jsonl.gz"
        if path.exists():
            print(f"  {month}: already saved, skipping")
            continue
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".gz.tmp")
        total = 0
        with gzip.open(tmp, "wt", encoding="utf-8") as f:
            for s in stations:
                params = {"poly": circle_polygon(s["lat"], s["lon"], RADIUS_M), "date": month}
                r = session.get("https://data.police.uk/api/crimes-street/all-crime",
                                params=params, timeout=60)
                r.raise_for_status()
                total += len(r.json())
                line = envelope(r.json(), api="police_crimes_street", station_key=s["station_key"],
                                month=month, radius_m=RADIUS_M)
                f.write(json.dumps(line) + "\n")
                time.sleep(0.1)  # police.uk allows 15 requests/second
        tmp.replace(path)  # only mark the month as done once every station succeeded
        print(f"  {month}: {total:,} crimes across {len(stations)} stations")


if __name__ == "__main__":
    main()

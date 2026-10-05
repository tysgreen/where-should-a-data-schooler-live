"""Step 3: plan a weekday-morning journey from every station to the office.

API:   https://api.tfl.gov.uk/Journey/JourneyResults/{from}/to/{to}
Saves: data/raw/tfl_journeys/{station_key}.json.gz  (one file per station)

Incremental: stations that already have a saved journey are skipped, so if the run
is interrupted you can just start it again. Use --refresh to re-plan everything.
"""
import sys
import time
from datetime import date, timedelta

from api_helpers import envelope, load_json_gz, make_session, save_json_gz, tfl_params
from config import ARRIVE_BY, RAW_DIR
from stations import load_station_points

OUT_DIR = RAW_DIR / "tfl_journeys"


def next_tuesday() -> date:
    """A 'typical' weekday: Tuesday avoids Monday bank holidays and Friday quirks."""
    today = date.today()
    days_ahead = (1 - today.weekday()) % 7 or 7
    return today + timedelta(days=days_ahead)


def main(refresh: bool = False):
    session = make_session()
    office = load_json_gz(RAW_DIR / "postcodes" / "office.json.gz")["response"]["result"]
    to = f"{office['latitude']},{office['longitude']}"
    travel_date = next_tuesday().strftime("%Y%m%d")

    stations = load_station_points()
    todo = [s for s in stations if refresh or not (OUT_DIR / f"{s['station_key']}.json.gz").exists()]
    print(f"  {len(stations) - len(todo)} already saved, {len(todo)} to fetch (arriving {ARRIVE_BY} on {travel_date})")

    for i, s in enumerate(todo, 1):
        frm = f"{s['lat']},{s['lon']}"
        params = tfl_params(date=travel_date, time=ARRIVE_BY, timeIs="Arriving",
                            journeyPreference="LeastTime")
        r = session.get(f"https://api.tfl.gov.uk/Journey/JourneyResults/{frm}/to/{to}",
                        params=params, timeout=60)
        if r.status_code == 404:
            # TfL occasionally can't plan from a station's exact coordinates
            # (e.g. Camden Town) - retry using the station's own ID instead.
            frm = s["station_key"]
            r = session.get(f"https://api.tfl.gov.uk/Journey/JourneyResults/{frm}/to/{to}",
                            params=params, timeout=60)
        if r.status_code != 200:
            print(f"  ! {s['name']}: HTTP {r.status_code}, skipping")
            continue
        info = {k: v for k, v in params.items() if k != "app_key"}  # never save the key
        save_json_gz(envelope(r.json(), api="tfl_journey", station_key=s["station_key"],
                              **{"from": frm, "to": to}, **info),
                     OUT_DIR / f"{s['station_key']}.json.gz")
        if i % 50 == 0:
            print(f"  {i}/{len(todo)}")
        time.sleep(0.2)  # stay well under TfL's 500 requests/minute limit


if __name__ == "__main__":
    main(refresh="--refresh" in sys.argv)

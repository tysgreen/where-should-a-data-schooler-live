"""Step 2: look up the office's coordinates, and which borough each station is in.

API:   https://api.postcodes.io  (free, no key)
Saves: data/raw/postcodes/office.json.gz
       data/raw/postcodes/stations.json.gz
"""
from api_helpers import envelope, make_session, save_json_gz
from config import OFFICE_POSTCODE, RAW_DIR
from stations import load_station_points

OUT_DIR = RAW_DIR / "postcodes"
BATCH_SIZE = 100  # postcodes.io accepts up to 100 locations per request


def main():
    session = make_session()

    # 1. The office postcode -> latitude/longitude (used as the commute destination).
    r = session.get(f"https://api.postcodes.io/postcodes/{OFFICE_POSTCODE}", timeout=30)
    r.raise_for_status()
    save_json_gz(envelope(r.json(), api="postcodes_lookup", postcode=OFFICE_POSTCODE),
                 OUT_DIR / "office.json.gz")
    print(f"  office {OFFICE_POSTCODE}: {r.json()['result']['admin_district']}")

    # 2. Each station's coordinates -> nearest postcode (which tells us the borough).
    stations = load_station_points()
    batches = []
    for i in range(0, len(stations), BATCH_SIZE):
        chunk = stations[i:i + BATCH_SIZE]
        payload = {"geolocations": [
            {"latitude": s["lat"], "longitude": s["lon"], "radius": 1000, "limit": 1}
            for s in chunk
        ]}
        r = session.post("https://api.postcodes.io/postcodes", json=payload, timeout=60)
        r.raise_for_status()
        # Keep the station keys alongside, in the same order as the results.
        batches.append({"station_keys": [s["station_key"] for s in chunk], "body": r.json()})
    save_json_gz(envelope(batches, api="postcodes_reverse_geocode"), OUT_DIR / "stations.json.gz")
    print(f"  reverse-geocoded {len(stations)} stations in {len(batches)} requests")


if __name__ == "__main__":
    main()

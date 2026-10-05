"""Step 1: download every tube, DLR, Overground and Elizabeth line station from TfL.

API:   https://api.tfl.gov.uk/StopPoint/Mode/{mode}
Saves: data/raw/tfl_stations/{mode}.json.gz  (one file per network)
"""
from api_helpers import envelope, load_json_gz, make_session, save_json_gz, tfl_params
from config import RAW_DIR, TFL_MODES

OUT_DIR = RAW_DIR / "tfl_stations"
STATION_TYPES = {"NaptanMetroStation", "NaptanRailStation"}  # skip entrances, bus stops etc.


def fetch_mode(session, mode: str) -> dict:
    """Download all stop points for one network, following pagination if TfL uses it."""
    url = f"https://api.tfl.gov.uk/StopPoint/Mode/{mode}"
    stop_points, page = [], 1
    while True:
        r = session.get(url, params=tfl_params(page=page), timeout=60)
        r.raise_for_status()
        body = r.json()
        stop_points += body.get("stopPoints", [])
        total = body.get("total") or 0
        if not body.get("stopPoints") or len(stop_points) >= total:
            break
        page += 1
    return {"stopPoints": stop_points, "total": len(stop_points)}


def load_station_points() -> list[dict]:
    """Read the saved station files and return one point per physical station.

    A station served by several networks (e.g. Whitechapel) appears in several
    files with different IDs but the same 'hub' code, so we keep one per hub.
    Used by later extract steps that need a lat/lon for every station.
    """
    stations = {}
    for path in sorted(OUT_DIR.glob("*.json.gz")):
        for sp in load_json_gz(path)["response"]["stopPoints"]:
            if sp.get("stopType") not in STATION_TYPES:
                continue
            key = sp.get("hubNaptanCode") or sp["naptanId"]
            stations.setdefault(key, {"station_key": key, "name": sp["commonName"],
                                      "lat": sp["lat"], "lon": sp["lon"]})
    return sorted(stations.values(), key=lambda s: s["station_key"])


def main():
    session = make_session()
    for mode in TFL_MODES:
        data = fetch_mode(session, mode)
        save_json_gz(envelope(data, api="tfl_stoppoint_mode", mode=mode), OUT_DIR / f"{mode}.json.gz")
        print(f"  {mode:15} {data['total']:>5} stop points")
    print(f"  -> {len(load_station_points())} unique stations")


if __name__ == "__main__":
    main()

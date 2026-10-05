"""Step 5: download every pub, café, gym, supermarket and park in Greater London.

API:   OpenStreetMap Overpass API  (free, no key)
Saves: data/raw/overpass/amenities.json.gz

One request gets everything; counting what's near each station happens later in SQL.
"""
from api_helpers import envelope, make_session, save_json_gz
from config import AMENITIES, RAW_DIR

OUT_PATH = RAW_DIR / "overpass" / "amenities.json.gz"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def build_query() -> str:
    """Overpass QL: find the Greater London boundary, then every matching feature inside it.
    'out center' gives parks and other shapes a single centre point."""
    selectors = "\n  ".join(f"{sel}(area.london);" for sel in AMENITIES.values())
    return f"""
[out:json][timeout:300];
area["boundary"="administrative"]["name"="Greater London"]->.london;
(
  {selectors}
);
out center tags;
"""


def main():
    session = make_session()
    query = build_query()
    r = session.post(OVERPASS_URL, data={"data": query}, timeout=400)
    r.raise_for_status()
    save_json_gz(envelope(r.json(), api="overpass", query=query), OUT_PATH)
    print(f"  {len(r.json()['elements']):,} amenities saved")


if __name__ == "__main__":
    main()

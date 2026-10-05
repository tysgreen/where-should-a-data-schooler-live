"""Step 7: download the ONS 'Private rental market in London' statistics:
rents by borough and by type of home - including a single ROOM in a shared home,
which is what most Data Schoolers will actually be renting.

Source: ONS ad hoc release (free). The link lives in config.py (LONDON_RENTS_URL).
Saves:  data/raw/ons/london_rental_stats.xlsx  (+ a small JSON note of where it came from)
"""
import json
from datetime import datetime, timezone

from api_helpers import make_session
from config import LONDON_RENTS_URL, RAW_DIR

OUT_DIR = RAW_DIR / "ons"


def main():
    meta_path = OUT_DIR / "london_rental_stats.source.json"
    if meta_path.exists() and json.loads(meta_path.read_text())["url"] == LONDON_RENTS_URL:
        print("  this release is already downloaded, skipping")
        return
    r = make_session().get(LONDON_RENTS_URL, timeout=120)
    r.raise_for_status()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "london_rental_stats.xlsx").write_bytes(r.content)
    meta_path.write_text(json.dumps({
        "url": LONDON_RENTS_URL,
        "extracted_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}, indent=2))
    print(f"  saved {len(r.content) / 1e3:.0f} KB")


if __name__ == "__main__":
    main()

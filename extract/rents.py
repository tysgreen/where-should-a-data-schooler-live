"""Step 6: download the ONS 'Price Index of Private Rents' spreadsheet
(average monthly rent by local authority, including every London borough).

Source: ONS dataset page (free). The file URL changes with every monthly release,
so we read the dataset page and follow its newest .xlsx link.
Saves:  data/raw/ons/pipr_monthly.xlsx  (+ a small JSON note of where it came from)
"""
import json
import re
from datetime import datetime, timezone

from api_helpers import make_session
from config import RAW_DIR

DATASET_PAGE = ("https://www.ons.gov.uk/economy/inflationandpriceindices/datasets/"
                "priceindexofprivaterentsukmonthlypricestatistics")
OUT_DIR = RAW_DIR / "ons"


def main():
    session = make_session()
    page = session.get(DATASET_PAGE, timeout=60)
    page.raise_for_status()
    links = re.findall(r'href="(/file\?uri=[^"]+\.xlsx)"', page.text)
    if not links:
        raise RuntimeError("No .xlsx link found on the ONS dataset page - has the page layout changed?")
    url = "https://www.ons.gov.uk" + links[0]  # the first link is the latest release

    meta_path = OUT_DIR / "pipr_monthly.source.json"
    if meta_path.exists() and json.loads(meta_path.read_text())["url"] == url:
        print("  latest release already downloaded, skipping")
        return

    r = session.get(url, timeout=120)
    r.raise_for_status()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "pipr_monthly.xlsx").write_bytes(r.content)
    meta_path.write_text(json.dumps({
        "url": url, "extracted_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}, indent=2))
    print(f"  saved {len(r.content) / 1e6:.1f} MB from {url}")


if __name__ == "__main__":
    main()

"""Run every extract step in order.

    python extract/run_extract.py            # normal run (skips anything already saved)
    python extract/run_extract.py --refresh  # re-plan every commute too

Order matters: later steps need the station list and the office location.
"""
import sys
import time

import amenities
import crime
import journeys
import london_rents
import postcodes
import rents
import stations

STEPS = [
    ("1/7 TfL stations", stations.main),
    ("2/7 postcodes.io (office + station boroughs)", postcodes.main),
    ("3/7 TfL commute to the office", lambda: journeys.main(refresh="--refresh" in sys.argv)),
    ("4/7 police.uk crime", crime.main),
    ("5/7 OpenStreetMap amenities", amenities.main),
    ("6/7 ONS rents (all UK, by bedrooms)", rents.main),
    ("7/7 ONS London rents (incl. rooms)", london_rents.main),
]

if __name__ == "__main__":
    for label, step in STEPS:
        start = time.time()
        print(f"\n== {label}")
        step()
        print(f"   done in {time.time() - start:.0f}s")

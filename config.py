"""Project-wide settings. Change things here, not inside the scripts."""
from pathlib import Path

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "data" / "raw"
DB_PATH = ROOT / "data" / "where_to_live.duckdb"

# Where Data Schoolers commute to every day.
OFFICE_POSTCODE = "EC4M 9BR"          # The Data School, 1st Floor, 25 Watling Street
ARRIVE_BY = "0900"                    # plan journeys arriving by 9am on a weekday

# Which TfL networks count as "a station you could live near".
TFL_MODES = ["tube", "dlr", "overground", "elizabeth-line"]

# "Nearby" = within this many metres of the station (~6 minute walk).
RADIUS_M = 500

# How many of the most recent months of crime data to use.
CRIME_MONTHS = 3

# Amenities to count near each station, as OpenStreetMap tags.
AMENITIES = {
    "pub": 'nwr["amenity"="pub"]',
    "cafe": 'nwr["amenity"="cafe"]',
    "gym": 'nwr["leisure"="fitness_centre"]',
    "supermarket": 'nwr["shop"="supermarket"]',
    "park": 'nwr["leisure"="park"]',
}

# Be a polite API citizen: identify ourselves.
USER_AGENT = "where-should-a-data-schooler-live/1.0 (The Information Lab Data School example project)"

# ONS "Private rental market in London" statistics (made for the Greater London Authority).
# Published a few times a year as an ad hoc release, so the link can't be discovered
# automatically - update it when a newer release appears:
# https://www.ons.gov.uk/economy/inflationandpriceindices/adhocs (search "private rental market in London")
LONDON_RENTS_URL = ("https://www.ons.gov.uk/file?uri=/economy/inflationandpriceindices/adhocs/"
                    "3389privaterentalmarketinlondonapril2025tomarch2026/londonrentalstatsaccessibleq12026.xlsx")

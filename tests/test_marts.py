"""Data quality tests on the final table the app uses (data/marts/stations.parquet).

If any of these fail, something upstream changed (an API, a file layout)
and the app would show wrong numbers - so CI stops before that happens.
"""
import sys
from pathlib import Path

import duckdb
import pytest

sys.path.append(str(Path(__file__).parent.parent))
from config import ROOT  # noqa: E402

MART = ROOT / "data" / "marts" / "stations.parquet"


@pytest.fixture(scope="module")
def con():
    if not MART.exists():
        pytest.skip("run pipeline/run_models.py first")
    c = duckdb.connect()
    c.execute(f"CREATE VIEW stations AS SELECT * FROM '{MART.as_posix()}'")
    return c


def scalar(con, sql):
    return con.execute(sql).fetchone()[0]


def test_there_are_hundreds_of_stations(con):
    assert 300 <= scalar(con, "SELECT count(*) FROM stations") <= 500


def test_one_row_per_station(con):
    assert scalar(con, "SELECT count(*) - count(DISTINCT station_key) FROM stations") == 0


def test_station_names_are_unique_and_clean(con):
    assert scalar(con, "SELECT count(*) - count(DISTINCT station_name) FROM stations") == 0
    assert scalar(con, "SELECT count(*) FROM stations WHERE station_name ILIKE '%underground station%'") == 0


def test_every_station_is_in_greater_london(con):
    # a generous box around Greater London
    assert scalar(con, """SELECT count(*) FROM stations
                          WHERE lat NOT BETWEEN 51.25 AND 51.72 OR lon NOT BETWEEN -0.56 AND 0.34""") == 0


def test_almost_every_station_has_a_commute(con):
    assert scalar(con, "SELECT avg((commute_min IS NOT NULL)::INT) FROM stations") >= 0.98


def test_commute_times_are_realistic(con):
    assert scalar(con, "SELECT count(*) FROM stations WHERE commute_min NOT BETWEEN 1 AND 120") == 0


def test_rent_is_missing_only_in_the_city_of_london(con):
    # ONS publishes no rent figure for the City of London - anywhere else is a bug
    assert scalar(con, """SELECT count(*) FROM stations
                          WHERE (room_rent_gbp IS NULL OR rent_1bed_gbp IS NULL)
                            AND borough_name <> 'City of London'""") == 0


def test_rents_are_realistic(con):
    assert scalar(con, "SELECT count(*) FROM stations WHERE room_rent_gbp NOT BETWEEN 300 AND 2000") == 0
    assert scalar(con, "SELECT count(*) FROM stations WHERE rent_1bed_gbp NOT BETWEEN 500 AND 6000") == 0


def test_a_room_is_cheaper_than_a_whole_flat(con):
    assert scalar(con, "SELECT count(*) FROM stations WHERE room_rent_gbp >= rent_1bed_gbp") == 0


def test_crime_and_amenity_counts_are_not_negative(con):
    assert scalar(con, """SELECT count(*) FROM stations
                          WHERE crimes_per_month < 0 OR personal_crimes_per_month > crimes_per_month
                             OR pubs < 0 OR cafes < 0 OR gyms < 0 OR supermarkets < 0""") == 0


@pytest.mark.parametrize("col", ["score_commute", "score_rent", "score_safety", "score_amenities", "score_green"])
def test_scores_are_between_0_and_100(con, col):
    assert scalar(con, f"SELECT count(*) FROM stations WHERE {col} NOT BETWEEN 0 AND 100") == 0

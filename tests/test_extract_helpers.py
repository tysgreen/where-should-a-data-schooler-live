"""Unit tests for the extract helpers. These need no internet or data files."""
import math
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "extract"))

from crime import circle_polygon  # noqa: E402
from journeys import next_tuesday  # noqa: E402


def distance_m(lat1, lon1, lat2, lon2):
    """Haversine distance - the same formula the SQL uses."""
    r = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    return 2 * r * math.asin(math.sqrt(math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2))


def test_circle_polygon_points_are_the_right_distance_away():
    lat, lon = 51.5130, -0.0939  # the office
    points = [tuple(map(float, p.split(","))) for p in circle_polygon(lat, lon, 500).split(":")]
    assert len(points) == 16
    for plat, plon in points:
        assert abs(distance_m(lat, lon, plat, plon) - 500) < 5  # within 5 metres


def test_next_tuesday_is_a_future_tuesday():
    d = next_tuesday()
    assert d.weekday() == 1
    assert 0 < (d - date.today()).days <= 7

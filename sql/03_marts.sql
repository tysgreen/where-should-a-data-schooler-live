-- =====================================================================
-- LAYER 3: MARTS
-- Combine the staging tables into one row per station, ready for the app.
-- {radius_m} is filled in by pipeline/run_models.py from config.py.
-- =====================================================================
CREATE SCHEMA IF NOT EXISTS marts;

-- Straight-line distance in metres between two lat/lon points (the haversine formula).
CREATE OR REPLACE MACRO haversine_m(lat1, lon1, lat2, lon2) AS
    2 * 6371000 * asin(sqrt(
        pow(sin(radians(lat2 - lat1) / 2), 2) +
        cos(radians(lat1)) * cos(radians(lat2)) * pow(sin(radians(lon2 - lon1) / 2), 2)
    ));

-- ---------------------------------------------------------------------
-- Amenities within {radius_m} of each station.
-- Pairs every station with every amenity (~420 x 15,000 = 6m pairs, easy for DuckDB),
-- keeps the close ones, and counts them by type.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE marts.station_amenities AS
WITH distances AS (
    SELECT s.station_key, a.amenity_type,
           haversine_m(s.lat, s.lon, a.lat, a.lon) AS distance_m
    FROM staging.stations s
    CROSS JOIN staging.amenities a
)
SELECT
    station_key,
    count(*) FILTER (amenity_type = 'pub'         AND distance_m <= {radius_m}) AS pubs,
    count(*) FILTER (amenity_type = 'cafe'        AND distance_m <= {radius_m}) AS cafes,
    count(*) FILTER (amenity_type = 'gym'         AND distance_m <= {radius_m}) AS gyms,
    count(*) FILTER (amenity_type = 'supermarket' AND distance_m <= {radius_m}) AS supermarkets,
    count(*) FILTER (amenity_type = 'park'        AND distance_m <= {radius_m}) AS parks,
    round(min(distance_m) FILTER (amenity_type = 'park'))                      AS nearest_park_m
FROM distances
GROUP BY station_key;

-- ---------------------------------------------------------------------
-- Average crimes per month within {radius_m} of each station.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE marts.station_crime AS
SELECT
    station_key,
    count(DISTINCT month)                                          AS crime_months,
    min(month) || ' to ' || max(month)                             AS crime_period,
    round(count(*) / count(DISTINCT month))                        AS crimes_per_month,
    round(count(*) FILTER (is_personal_crime) / count(DISTINCT month)) AS personal_crimes_per_month
FROM staging.crimes
-- only the most recent {crime_months} months (older files may be kept between runs)
WHERE month IN (SELECT DISTINCT month FROM staging.crimes ORDER BY month DESC LIMIT {crime_months})
GROUP BY station_key;

-- ---------------------------------------------------------------------
-- The final table: one row per station with every measure side by side,
-- plus a 0-100 score per theme (100 = best in London) for the app to weight.
-- percent_rank() puts each station on a 0-1 scale relative to all the others.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE marts.stations AS
WITH joined AS (
    SELECT
        s.station_key,
        -- a few different stations share a name (e.g. Bethnal Green on the tube
        -- and on the Overground) -> add the network to tell them apart
        CASE WHEN count(*) OVER (PARTITION BY s.station_name) > 1
             THEN s.station_name || ' (' || array_to_string(s.networks, ', ') || ')'
             ELSE s.station_name END        AS station_name,
        s.lat,
        s.lon,
        s.fare_zone,
        array_to_string(s.lines, ', ')      AS lines,
        b.borough_name,
        c.commute_min,
        c.changes,
        c.route_modes,
        c.peak_fare_gbp,
        rr.room_rent_gbp,
        rr.room_rent_sample,
        rr.room_rent_period,
        r.rent_1bed_gbp,
        r.rent_2bed_gbp,
        r.rent_month,
        cr.crime_period,
        cr.crimes_per_month,
        cr.personal_crimes_per_month,
        a.pubs, a.cafes, a.gyms, a.supermarkets, a.parks, a.nearest_park_m,
        -- one simple "things to do nearby" number: pubs + cafes + gyms + supermarkets
        a.pubs + a.cafes + a.gyms + a.supermarkets   AS amenities_total
    FROM staging.stations s
    LEFT JOIN staging.station_boroughs b USING (station_key)
    LEFT JOIN staging.commutes         c USING (station_key)
    LEFT JOIN staging.rents            r ON r.borough_code = b.borough_code
    LEFT JOIN staging.room_rents      rr ON rr.borough_name = b.borough_name
    LEFT JOIN marts.station_crime     cr USING (station_key)
    LEFT JOIN marts.station_amenities  a USING (station_key)
    -- The Elizabeth line and Overground run beyond London (e.g. Reading, Watford).
    -- Our amenity data and the Data School commute only make sense inside Greater London.
    WHERE b.region = 'London'
)
SELECT
    *,
    -- lower is better for commute, rent and crime, so rank those descending
    CASE WHEN commute_min   IS NOT NULL THEN round(100 * percent_rank() OVER (PARTITION BY commute_min IS NULL ORDER BY commute_min DESC)) END   AS score_commute,
    CASE WHEN room_rent_gbp IS NOT NULL THEN round(100 * percent_rank() OVER (PARTITION BY room_rent_gbp IS NULL ORDER BY room_rent_gbp DESC)) END AS score_rent,
    CASE WHEN personal_crimes_per_month IS NOT NULL THEN round(100 * percent_rank() OVER (PARTITION BY personal_crimes_per_month IS NULL ORDER BY personal_crimes_per_month DESC)) END AS score_safety,
    round(100 * percent_rank() OVER (ORDER BY amenities_total))                                          AS score_amenities,
    round(100 * percent_rank() OVER (ORDER BY -nearest_park_m))                                          AS score_green
FROM joined
ORDER BY station_name;

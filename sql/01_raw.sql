-- =====================================================================
-- LAYER 1: RAW
-- Load the saved API responses into DuckDB, one row per record.
-- No cleaning happens here: every value is kept exactly as the API sent it
-- (as JSON), so we can always trace a number back to its source.
-- {raw_dir} is filled in by pipeline/run_models.py.
-- =====================================================================
CREATE SCHEMA IF NOT EXISTS raw;

-- TfL stop points: one row per stop point (stations, platforms, entrances...).
-- Each file holds one network; unnest() turns its list of stop points into rows
CREATE OR REPLACE TABLE raw.tfl_stop_points AS
WITH files AS (
    SELECT
        json ->> '$.request.mode'            AS network,
        json ->> '$.extracted_at'            AS extracted_at,
        json -> '$.response.stopPoints[*]'   AS stop_points
    FROM read_json_objects('{raw_dir}/tfl_stations/*.json.gz', maximum_object_size = 50000000)
)
SELECT network, extracted_at, unnest(stop_points) AS stop_point
FROM files;

-- postcodes.io: the office lookup (one row).
CREATE OR REPLACE TABLE raw.postcodes_office AS
SELECT json -> '$.response.result' AS result
FROM read_json_objects('{raw_dir}/postcodes/office.json.gz');

-- postcodes.io: nearest postcode to each station.
-- Each request batch stored the station keys in the same order as the results,
-- so we unnest both lists side by side to pair them back up.
CREATE OR REPLACE TABLE raw.postcodes_stations AS
WITH batches AS (
    SELECT unnest(json -> '$.response[*]') AS batch
    FROM read_json_objects('{raw_dir}/postcodes/stations.json.gz')
)
SELECT
    unnest(batch ->> '$.station_keys[*]') AS station_key,
    unnest(batch -> '$.body.result[*]')          AS result
FROM batches;

-- TfL Journey Planner: one row per station (the whole response, several journey options).
CREATE OR REPLACE TABLE raw.tfl_journeys AS
SELECT
    json ->> '$.request.station_key' AS station_key,
    json ->> '$.extracted_at'        AS extracted_at,
    json -> '$.response'             AS response
FROM read_json_objects('{raw_dir}/tfl_journeys/*.json.gz');

-- police.uk: one row per crime per station per month.
-- (A crime near two stations appears once for each - that's intended.)
CREATE OR REPLACE TABLE raw.police_crimes AS
WITH station_months AS (
    -- pull out the small fields first; unnesting next to the whole JSON line
    -- would copy that (large) line onto every crime row and exhaust memory
    SELECT
        json ->> '$.request.station_key' AS station_key,
        json ->> '$.request.month'       AS month,
        json -> '$.response[*]'          AS crimes
    FROM read_json_objects('{raw_dir}/police/*.jsonl.gz', format = 'newline_delimited')
)
SELECT station_key, month, unnest(crimes) AS crime
FROM station_months;

-- OpenStreetMap: one row per pub / cafe / gym / supermarket / park.
CREATE OR REPLACE TABLE raw.osm_elements AS
SELECT unnest(json -> '$.response.elements[*]') AS element
FROM read_json_objects('{raw_dir}/overpass/amenities.json.gz');

-- raw.ons_rents is loaded from the ONS spreadsheet by pipeline/run_models.py
-- (DuckDB can't read .xlsx without an extra extension, so pandas does that step).

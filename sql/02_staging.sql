-- =====================================================================
-- LAYER 2: STAGING
-- Turn raw JSON into clean, typed tables: pick the fields we need, give them
-- clear names and types, fix quirks, and remove duplicates.
-- =====================================================================
CREATE SCHEMA IF NOT EXISTS staging;

-- ---------------------------------------------------------------------
-- Stations: one row per physical station.
-- Quirks handled:
--  * TfL returns platforms, entrances etc. too -> keep only station records.
--  * A station on several networks (e.g. Stratford) appears once per network
--    with different IDs but the same hub code -> group by hub code.
--  * Names carry suffixes ("Acton Town Underground Station") -> strip them.
--  * Zones come as '2', '2/3' or '2+3' -> take the lowest (cheapest) zone.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE staging.stations AS
WITH station_records AS (
    SELECT
        network,
        stop_point ->> '$.naptanId'                                   AS naptan_id,
        coalesce(stop_point ->> '$.hubNaptanCode',
                 stop_point ->> '$.naptanId')                          AS station_key,
        stop_point ->> '$.commonName'                                  AS raw_name,
        CAST(stop_point ->> '$.lat' AS DOUBLE)                         AS lat,
        CAST(stop_point ->> '$.lon' AS DOUBLE)                         AS lon,
        stop_point ->> '$.lines[*].name'                               AS lines,
        -- the zone is hidden in a list of key/value "additional properties":
        -- find where 'Zone' sits in the list of keys, take the value at that position
        (stop_point ->> '$.additionalProperties[*].value')[
            list_position(stop_point ->> '$.additionalProperties[*].key', 'Zone')] AS zone_raw
    FROM raw.tfl_stop_points
    WHERE stop_point ->> '$.stopType' IN ('NaptanMetroStation', 'NaptanRailStation')
)
SELECT
    station_key,
    -- shortest cleaned name wins, e.g. 'Stratford' over 'Stratford International'
    arg_min(clean_name, length(clean_name))  AS station_name,
    avg(lat)                                 AS lat,
    avg(lon)                                 AS lon,
    min(fare_zone)                           AS fare_zone,
    list_sort(list_distinct(flatten(list(lines))))  AS lines,
    list_sort(list_distinct(list(network)))         AS networks
FROM (
    SELECT *,
           -- '2/3' or '2+3' -> [2, 3] -> 2
           list_min(list_transform(string_split(replace(zone_raw, '+', '/'), '/'),
                                   lambda z: TRY_CAST(z AS INTEGER)))      AS fare_zone,
           trim(regexp_replace(raw_name,
                ' (ELL )?(Underground Station|Rail Station|DLR Station|Station)$', '')) AS clean_name
    FROM station_records
)
GROUP BY station_key;

-- ---------------------------------------------------------------------
-- The office location (commute destination).
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE staging.office AS
SELECT
    result ->> '$.postcode'                    AS postcode,
    CAST(result ->> '$.latitude'  AS DOUBLE)   AS lat,
    CAST(result ->> '$.longitude' AS DOUBLE)   AS lon
FROM raw.postcodes_office;

-- ---------------------------------------------------------------------
-- Which borough (local authority) each station is in, via its nearest postcode.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE staging.station_boroughs AS
SELECT
    station_key,
    result -> '$.result[0]' ->> '$.postcode'                    AS nearest_postcode,
    result -> '$.result[0]' ->> '$.admin_district'              AS borough_name,
    result -> '$.result[0]' -> '$.codes' ->> '$.admin_district' AS borough_code,
    result -> '$.result[0]' ->> '$.region'                      AS region
FROM raw.postcodes_stations;

-- ---------------------------------------------------------------------
-- Commutes: the fastest of TfL's suggested journeys for each station.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE staging.commutes AS
WITH options AS (
    SELECT
        station_key,
        unnest(response -> '$.journeys[*]') AS journey
    FROM raw.tfl_journeys
),
typed AS (
    SELECT
        station_key,
        CAST(journey ->> '$.duration' AS INTEGER)                  AS duration_min,
        TRY_CAST(journey -> '$.fare' ->> '$.totalCost' AS INTEGER) AS fare_pence,
        journey ->> '$.legs[*].mode.id'                            AS leg_modes
    FROM options
)
SELECT
    station_key,
    duration_min                                                   AS commute_min,
    fare_pence / 100.0                                             AS peak_fare_gbp,
    -- changes = number of non-walking legs minus one
    greatest(len(list_filter(leg_modes, lambda m: m <> 'walking')) - 1, 0) AS changes,
    array_to_string(list_filter(leg_modes, lambda m: m <> 'walking'), ' > ') AS route_modes
FROM typed
QUALIFY row_number() OVER (PARTITION BY station_key ORDER BY duration_min, fare_pence) = 1;

-- ---------------------------------------------------------------------
-- Crimes: one row per crime per station, with a flag for crimes against people
-- (the ones that matter for "is this area safe to live in?", unlike e.g.
-- shoplifting, which mostly tracks how many shops there are).
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE staging.crimes AS
SELECT
    station_key,
    month,
    CAST(crime ->> '$.id' AS BIGINT)  AS crime_id,
    crime ->> '$.category'            AS category,
    crime ->> '$.category' IN ('violent-crime', 'robbery', 'theft-from-the-person',
                               'burglary', 'possession-of-weapons') AS is_personal_crime
FROM raw.police_crimes;

-- ---------------------------------------------------------------------
-- Amenities: one row per place, with a single point location.
-- OSM points ("nodes") have lat/lon; shapes ("ways"/"relations") have a centre.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE staging.amenities AS
WITH typed AS (
    SELECT
        element ->> '$.type' || '/' || (element ->> '$.id')                       AS osm_id,
        element -> '$.tags' ->> '$.name'                                          AS name,
        CAST(coalesce(element ->> '$.lat', element -> '$.center' ->> '$.lat') AS DOUBLE) AS lat,
        CAST(coalesce(element ->> '$.lon', element -> '$.center' ->> '$.lon') AS DOUBLE) AS lon,
        CASE
            WHEN element -> '$.tags' ->> '$.amenity' = 'pub'            THEN 'pub'
            WHEN element -> '$.tags' ->> '$.amenity' = 'cafe'           THEN 'cafe'
            WHEN element -> '$.tags' ->> '$.leisure' = 'fitness_centre' THEN 'gym'
            WHEN element -> '$.tags' ->> '$.shop'    = 'supermarket'    THEN 'supermarket'
            WHEN element -> '$.tags' ->> '$.leisure' = 'park'           THEN 'park'
        END AS amenity_type
    FROM raw.osm_elements
)
SELECT DISTINCT * FROM typed
WHERE amenity_type IS NOT NULL AND lat IS NOT NULL;

-- ---------------------------------------------------------------------
-- Rents: average monthly rent per local authority for the latest month.
-- ONS marks missing values as '[x]' -> TRY_CAST turns those into NULL.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE staging.rents AS
SELECT
    "Area code"                                        AS borough_code,
    "Area name"                                        AS borough_name,
    CAST("Time period" AS DATE)                        AS rent_month,
    TRY_CAST("Rental price" AS INTEGER)                AS rent_all_gbp,
    TRY_CAST("Rental price one bed" AS INTEGER)        AS rent_1bed_gbp,
    TRY_CAST("Rental price two bed" AS INTEGER)        AS rent_2bed_gbp
FROM raw.ons_rents
QUALIFY CAST("Time period" AS DATE) = max(CAST("Time period" AS DATE)) OVER ();

-- ---------------------------------------------------------------------
-- Room rents: median monthly rent for a single ROOM in a shared home, per
-- London borough (ONS 'Private rental market in London'). This is what most
-- Data Schoolers will actually pay, rather than renting a whole flat.
-- Figures based on fewer than 5 rents are hidden by the ONS as '..' -> NULL.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE staging.room_rents AS
SELECT
    "Borough"                              AS borough_name,
    TRY_CAST("Median" AS INTEGER)          AS room_rent_gbp,
    TRY_CAST("Count of rents" AS INTEGER)  AS room_rent_sample,
    period                                 AS room_rent_period
FROM raw.ons_london_rents
WHERE "Bedroom Category" = 'Room';

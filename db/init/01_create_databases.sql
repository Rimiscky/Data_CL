-- ============================================================
--  Initialisation PostgreSQL — Bases de données du projet
-- ============================================================

-- Base dédiée aux données énergie/météo
CREATE DATABASE energy_db;

-- Connexion à energy_db pour créer le schéma
\c energy_db;

-- Schéma principal
CREATE SCHEMA IF NOT EXISTS energy;

-- ── Table consommation énergie ──────────────────────────
CREATE TABLE energy.consumption (
    id              SERIAL PRIMARY KEY,
    datetime        TIMESTAMPTZ NOT NULL,
    date            DATE NOT NULL,
    hour            SMALLINT,
    day_of_week     SMALLINT,
    is_weekend      BOOLEAN DEFAULT FALSE,
    region          VARCHAR(100),
    consommation_brute_electricite_rte  DOUBLE PRECISION,
    consommation_brute_gaz_terega       DOUBLE PRECISION,
    consommation_brute_gaz_grtgaz       DOUBLE PRECISION,
    consommation_brute_totale           DOUBLE PRECISION,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Table données météo ─────────────────────────────────
CREATE TABLE energy.weather (
    id                    SERIAL PRIMARY KEY,
    datetime              TIMESTAMPTZ NOT NULL,
    temperature_2m        DOUBLE PRECISION,
    apparent_temperature  DOUBLE PRECISION,
    relative_humidity_2m  DOUBLE PRECISION,
    wind_speed_10m        DOUBLE PRECISION,
    precipitation         DOUBLE PRECISION,
    cloud_cover           DOUBLE PRECISION,
    surface_pressure      DOUBLE PRECISION,
    created_at            TIMESTAMPTZ DEFAULT NOW()
);

-- ── Vue croisée énergie × météo ────────────────────────
CREATE VIEW energy.consumption_weather AS
SELECT
    c.datetime,
    c.date,
    c.hour,
    c.day_of_week,
    c.is_weekend,
    c.region,
    c.consommation_brute_electricite_rte,
    w.temperature_2m,
    w.apparent_temperature,
    w.relative_humidity_2m,
    w.wind_speed_10m,
    w.precipitation,
    w.cloud_cover,
    w.surface_pressure
FROM energy.consumption c
LEFT JOIN energy.weather w ON c.datetime = w.datetime;

-- ── Table qualité (gouvernance) ─────────────────────────
CREATE TABLE energy.quality_reports (
    id            SERIAL PRIMARY KEY,
    dataset_name  VARCHAR(100) NOT NULL,
    score         DOUBLE PRECISION,
    total_rows    INTEGER,
    total_columns INTEGER,
    passed        BOOLEAN,
    report_json   JSONB,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ── Table lignage (gouvernance) ─────────────────────────
CREATE TABLE energy.lineage (
    id             SERIAL PRIMARY KEY,
    pipeline_name  VARCHAR(100) NOT NULL,
    step_name      VARCHAR(100),
    source         VARCHAR(255),
    destination    VARCHAR(255),
    operation      VARCHAR(50),
    rows_in        INTEGER,
    rows_out       INTEGER,
    executed_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Index pour les requêtes fréquentes
CREATE INDEX idx_consumption_datetime ON energy.consumption(datetime);
CREATE INDEX idx_consumption_date ON energy.consumption(date);
CREATE INDEX idx_weather_datetime ON energy.weather(datetime);
CREATE INDEX idx_quality_dataset ON energy.quality_reports(dataset_name);

-- Permissions
GRANT ALL PRIVILEGES ON DATABASE energy_db TO airflow;
GRANT ALL PRIVILEGES ON SCHEMA energy TO airflow;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA energy TO airflow;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA energy TO airflow;

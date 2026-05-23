-- OddsFlow V3 — Database Schema
-- All tables for fixtures, stats, H2H, emit log, and results.

CREATE TABLE IF NOT EXISTS leagues (
    id             INTEGER PRIMARY KEY,
    sportmonks_id  INTEGER UNIQUE,
    name           TEXT    NOT NULL,
    country        TEXT,
    tier           INTEGER NOT NULL DEFAULT 2
);

CREATE TABLE IF NOT EXISTS teams (
    id             INTEGER PRIMARY KEY,
    sportmonks_id  INTEGER UNIQUE,
    name           TEXT    NOT NULL,
    short_name     TEXT,
    league_id      INTEGER REFERENCES leagues(id)
);

CREATE TABLE IF NOT EXISTS fixtures (
    id              INTEGER PRIMARY KEY,
    league_id       INTEGER REFERENCES leagues(id),
    tier            INTEGER,
    date            TEXT,
    status          TEXT    DEFAULT 'scheduled',  -- scheduled | settled
    home_team_id    INTEGER,
    away_team_id    INTEGER,
    home_team_name  TEXT,
    away_team_name  TEXT,
    -- odds
    home_odd              REAL,
    draw_odd              REAL,
    away_odd              REAL,
    btts_yes_odd          REAL,
    btts_no_odd           REAL,
    goals_over_15_odd     REAL,
    goals_over_25_odd     REAL,
    goals_over_35_odd     REAL,
    corners_over_75_odd   REAL,
    corners_over_85_odd   REAL,
    corners_over_95_odd   REAL,
    -- classification (computed on insert)
    draw_zone   TEXT,
    bts_pocket  TEXT,
    -- results (filled when settled)
    home_score   INTEGER,
    away_score   INTEGER,
    total_goals  INTEGER,
    sportmonks_id INTEGER UNIQUE,
    created_at    TEXT DEFAULT (datetime('now')),
    updated_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS fixture_stats (
    fixture_id      INTEGER PRIMARY KEY REFERENCES fixtures(id),
    home_corners    INTEGER,
    away_corners    INTEGER,
    total_corners   INTEGER,
    home_tackles    INTEGER,
    away_tackles    INTEGER,
    fouls_h         INTEGER,
    fouls_a         INTEGER,
    yellow_cards_h  INTEGER,
    yellow_cards_a  INTEGER,
    xg_h            REAL,
    xg_a            REAL
);

CREATE TABLE IF NOT EXISTS h2h_meetings (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    anchor_fixture_id   INTEGER REFERENCES fixtures(id),
    meeting_date        TEXT,
    home_team_id        INTEGER,
    away_team_id        INTEGER,
    home_score          INTEGER,
    away_score          INTEGER,
    total_goals         INTEGER,
    total_corners       INTEGER,
    combined_tackles    INTEGER
);

CREATE TABLE IF NOT EXISTS emit_log (
    pick_uuid       TEXT PRIMARY KEY,
    emitted_at      TEXT DEFAULT (datetime('now')),
    fixture_id      INTEGER REFERENCES fixtures(id),
    zone            TEXT,
    bts_pocket      TEXT,
    tier            INTEGER,
    market          TEXT,
    pick            TEXT,
    pick_odd        REAL,
    natural_line    REAL,
    confidence      REAL,
    prev_chain_hash TEXT,
    chain_hash      TEXT
);

CREATE TABLE IF NOT EXISTS pick_results (
    pick_uuid   TEXT PRIMARY KEY REFERENCES emit_log(pick_uuid),
    settled_at  TEXT,
    outcome     TEXT,        -- WIN | LOSS | VOID
    actual_value REAL,
    notes       TEXT
);

CREATE TABLE IF NOT EXISTS system_health (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    metric      TEXT NOT NULL,
    value       TEXT,
    recorded_at TEXT DEFAULT (datetime('now'))
);

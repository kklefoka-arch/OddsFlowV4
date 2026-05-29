"""OddsFlow V4 — Application settings.

Uses pydantic-settings for environment-variable overrides.
Set DATABASE_URL, APP_ENV, or LOG_LEVEL via a .env file or shell env.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./data/oddsflow_v4.db"
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    # V3.1 (2026-05-28): Sportmonks API token. Falls back to embedded literal
    # to keep existing deployments working; override via .env or shell env for
    # rotation / multi-environment. Used by fetch_upcoming.py, fetch_results.py,
    # routes_results.py, refresh_odds.py, refresh_stats.py.
    SPORTMONKS_TOKEN: str = (
        "2AWINN4fYPiQkY2lfHee9TASZubv74uP1RIY4ILY15Mzg4bw5bH2v2SeKGAN"
    )

    # Bundle 3 (Session 23d): HMAC shared secret for the Sportmonks Push
    # webhook receiver. Empty string disables the receiver — requests will
    # 401 until the operator sets a value via .env or shell env.
    SPORTMONKS_WEBHOOK_SECRET: str = ""

    # Bundle 5 (Session 23d): Runbook thresholds per pipeline task in hours.
    # /diagnostics/runbook flags a metric as overdue when (now - last_ok_ts)
    # exceeds the threshold. Per-task tuned to the natural cadence of the
    # cron job that owns the metric (fetch_results = 8h matches the 23:30/
    # 03:15/06:15 SAST rotation, emit_picks 26h matches the daily morning).
    RUNBOOK_THRESHOLDS: dict[str, float] = {
        "fetch_upcoming":          26.0,
        "emit_picks":              26.0,
        "emit_picks_reemit":       30.0,
        "refresh_odds":            26.0,
        "refresh_stats":           36.0,
        "fetch_results":            8.0,
        "settle":                   8.0,
        "reconcile_orphans":       30.0,
        "sportmonks_webhook":       6.0,
        "emit_partition_invalid": 168.0,  # 7d — informational, not a failure
    }

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def sqlite_path(self) -> str:
        """Extract the filesystem path from a sqlite:/// DATABASE_URL.

        Supports both relative (sqlite:///./foo.db) and absolute
        (sqlite:////abs/path/foo.db) URL forms.

        Returns:
            The raw path string suitable for sqlite3.connect().
        """
        url = self.DATABASE_URL
        if url.startswith("sqlite:///"):
            return url[len("sqlite:///"):]
        raise ValueError(f"Unsupported DATABASE_URL scheme: {url!r}")


settings = Settings()

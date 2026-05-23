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

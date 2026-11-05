"""Supabase PostgreSQL connection configuration."""

import os

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict
from sqlalchemy.engine import URL

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DOTENV_PATH = os.path.join(PROJECT_DIR, ".env")

ENV_USER = "SUPABASE_DB_USER"
ENV_PASSWORD = "SUPABASE_DB_PASSWORD"
ENV_HOST = "SUPABASE_DB_HOST"
ENV_PORT = "SUPABASE_DB_PORT"
ENV_NAME = "SUPABASE_DB_NAME"
REQUIRED_ENV_VARS = (ENV_USER, ENV_PASSWORD, ENV_HOST, ENV_PORT, ENV_NAME)


class SupabaseConnectionConfig(BaseModel):
    """Supabase PostgreSQL connection credentials.

    Attributes:
        username: Database username (e.g. ``"postgres.<project-ref>"``).
        password: Database password.
        host: Pooler hostname.
        port: Database port (typically ``6543``).
        database: Database name (typically ``"postgres"``).
    """

    model_config = ConfigDict(frozen=True)

    username: str
    password: str
    host: str
    port: int
    database: str

    @staticmethod
    def from_env() -> "SupabaseConnectionConfig":
        """Load credentials from environment variables.

        Reads ``SUPABASE_DB_USER``, ``SUPABASE_DB_PASSWORD``, ``SUPABASE_DB_HOST``,
        ``SUPABASE_DB_PORT`` and ``SUPABASE_DB_NAME``. A ``.env`` file in the
        project root is loaded first; variables already present in the
        environment take precedence over the file.

        Returns:
            A frozen :class:`SupabaseConnectionConfig` instance.

        Raises:
            ValueError: If any required variable is missing or empty, or if
                ``SUPABASE_DB_PORT`` is not an integer.
        """
        load_dotenv(DOTENV_PATH)
        missing = [name for name in REQUIRED_ENV_VARS if not os.environ.get(name)]
        if missing:
            raise ValueError(
                f"Missing Supabase credentials: {', '.join(missing)}. "
                "Set them as environment variables or in a .env file in the project root "
                "(see .env.example and README.md)."
            )
        raw_port = os.environ[ENV_PORT]
        try:
            port = int(raw_port)
        except ValueError as exc:
            raise ValueError(f"{ENV_PORT} must be an integer, got {raw_port!r}") from exc
        return SupabaseConnectionConfig(
            username=os.environ[ENV_USER],
            password=os.environ[ENV_PASSWORD],
            host=os.environ[ENV_HOST],
            port=port,
            database=os.environ[ENV_NAME],
        )

    def get_connection_url(self) -> str:
        """Build the SQLAlchemy connection URL for the psycopg 3 driver.

        ``sslmode=require`` is set because Supabase requires TLS. The
        transaction pooler (port 6543) multiplexes many clients over one server
        connection; the provider disables psycopg's prepared-statement cache so
        cached statements cannot collide across clients. Credentials are
        URL-encoded automatically by :func:`sqlalchemy.engine.URL.create`.

        Returns:
            A connection URL string, e.g.
            ``"postgresql+psycopg://user:pass@host:6543/postgres?sslmode=require"``.
        """
        url = URL.create(
            drivername="postgresql+psycopg",
            username=self.username,
            password=self.password,
            host=self.host,
            port=self.port,
            database=self.database,
            query={"sslmode": "require"},
        )
        # str(url) would redact the password ("***"); the engine needs the real one.
        return url.render_as_string(hide_password=False)

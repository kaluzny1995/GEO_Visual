"""Load parametrized SQL scripts from the project's ``sql/`` folder."""

from pathlib import Path
from typing import Final

SQL_DIR: Final = Path(__file__).resolve().parents[1] / "sql"


def load_sql(name: str) -> str:
    """Return the contents of ``sql/<name>.sql``.

    Args:
        name: File stem without the ``.sql`` suffix, e.g.
            ``avalanche_metrics_timeline``.

    Returns:
        The SQL text, including its leading comments.

    Raises:
        FileNotFoundError: If the script does not exist.
    """
    return (SQL_DIR / f"{name}.sql").read_text(encoding="utf-8")

from typing import Protocol

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    item TEXT NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


class OrderRepo(Protocol):
    def create(self, item: str, quantity: int) -> dict: ...
    def get(self, order_id: int) -> dict | None: ...
    def list_orders(self, limit: int = 50) -> list[dict]: ...
    def ping(self) -> bool: ...


class PostgresRepo:
    def __init__(self, dsn: str):
        self.pool = ConnectionPool(
            dsn,
            min_size=1,
            max_size=5,
            kwargs={"row_factory": dict_row},
            open=False,
        )

    def open(self) -> None:
        self.pool.open(wait=True, timeout=30)
        with self.pool.connection() as conn:
            conn.execute(SCHEMA)

    def close(self) -> None:
        self.pool.close()

    def create(self, item: str, quantity: int) -> dict:
        with self.pool.connection() as conn:
            return conn.execute(
                "INSERT INTO orders (item, quantity) VALUES (%s, %s) "
                "RETURNING id, item, quantity, created_at",
                (item, quantity),
            ).fetchone()

    def get(self, order_id: int) -> dict | None:
        with self.pool.connection() as conn:
            return conn.execute(
                "SELECT id, item, quantity, created_at FROM orders WHERE id = %s",
                (order_id,),
            ).fetchone()

    def list_orders(self, limit: int = 50) -> list[dict]:
        with self.pool.connection() as conn:
            return conn.execute(
                "SELECT id, item, quantity, created_at FROM orders "
                "ORDER BY id DESC LIMIT %s",
                (limit,),
            ).fetchall()

    def ping(self) -> bool:
        with self.pool.connection() as conn:
            conn.execute("SELECT 1")
        return True

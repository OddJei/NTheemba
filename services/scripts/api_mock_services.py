"""Bootstrap a SQLite mock datastore based on API service design docs."""

from __future__ import annotations

import argparse
import json
import logging
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple
from uuid import uuid4

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = Path(__file__).resolve().parent
SERVICE_ROOT = PROJECT_ROOT / "api-services"
DB_PATH = SCRIPT_ROOT / "mock_services.db"

TYPE_MAP: Dict[str, str] = {
    "UUID": "TEXT",
    "TEXT": "TEXT",
    "VARCHAR": "TEXT",
    "CHAR": "TEXT",
    "STRING": "TEXT",
    "TIMESTAMP": "TEXT",
    "DATETIME": "TEXT",
    "DATE": "TEXT",
    "TIME": "TEXT",
    "BOOLEAN": "INTEGER",
    "BOOL": "INTEGER",
    "INTEGER": "INTEGER",
    "INT": "INTEGER",
    "BIGINT": "INTEGER",
    "SMALLINT": "INTEGER",
    "SERIAL": "INTEGER",
    "BIGSERIAL": "INTEGER",
    "NUMERIC": "REAL",
    "DECIMAL": "REAL",
    "FLOAT": "REAL",
    "DOUBLE": "REAL",
    "JSON": "TEXT",
    "JSONB": "TEXT",
    "TEXT[]": "TEXT",
    "UUID[]": "TEXT",
    "ARRAY": "TEXT",
    "ENUM": "TEXT",
}

IGNORED_FILENAMES = {"design_template.txt"}
TABLE_PATTERN = re.compile(r"^Table:\s*(.+)$", re.IGNORECASE)
COLUMN_PATTERN = re.compile(r"^-\s*([A-Za-z0-9_]+)\s*:\s*(.+)$")

ROLE_DESCRIPTIONS: Dict[str, str] = {
    "msme": "Micro and small enterprise operator",
    "affiliate": "Affiliate partner user",
    "default": "Default platform participant",
    "admin": "Platform administrator",
}

DEFAULT_USER_PROFILE = {
    "username": "default_user",
    "email": "jchisulokt@gmail.com",
    "phone": "260952675580",
    "password_hash": "mock-password-hash",
}


logger = logging.getLogger(__name__)


class ColumnDefinition:
    """Simplified representation of a column extracted from design docs."""

    __slots__ = ("name", "sqlite_type", "primary_key", "unique", "not_null")

    def __init__(
        self,
        name: str,
        sqlite_type: str,
        *,
        primary_key: bool = False,
        unique: bool = False,
        not_null: bool = False,
    ) -> None:
        self.name = name
        self.sqlite_type = sqlite_type
        self.primary_key = primary_key
        self.unique = unique
        self.not_null = not_null


class TableDefinition:
    """Table definition composed of multiple columns."""

    __slots__ = ("raw_name", "columns")

    def __init__(self, raw_name: str) -> None:
        self.raw_name = raw_name
        self.columns: List[ColumnDefinition] = []

    @property
    def table_name(self) -> str:
        return normalize_table_name(self.raw_name)

    def create_statement(self) -> Optional[str]:
        if not self.columns:
            return None
        column_clauses: List[str] = []
        pk_columns = [col.name for col in self.columns if col.primary_key]
        for column in self.columns:
            parts = [f'"{column.name}"', column.sqlite_type]
            inline_pk = column.primary_key and len(pk_columns) == 1
            if inline_pk:
                parts.append("PRIMARY KEY")
            if column.not_null and not inline_pk:
                parts.append("NOT NULL")
            if column.unique:
                parts.append("UNIQUE")
            column_clauses.append(" ".join(parts))
        if len(pk_columns) > 1:
            pk_clause = ", ".join(f'"{name}"' for name in pk_columns)
            column_clauses.append(f"PRIMARY KEY ({pk_clause})")
        columns_sql = ",\n    ".join(column_clauses)
        return f"CREATE TABLE IF NOT EXISTS \"{self.table_name}\" (\n    {columns_sql}\n);"


def normalize_table_name(raw_name: str) -> str:
    sanitized = raw_name.strip().replace(".", "_").replace("/", "_")
    sanitized = re.sub(r"[^A-Za-z0-9_]+", "_", sanitized)
    sanitized = re.sub(r"_+", "_", sanitized)
    sanitized = sanitized.strip("_") or "table"
    return sanitized.lower()


def map_sqlite_type(type_token: str) -> str:
    token = type_token.upper().strip()
    token = token.replace("[]", "[]")
    for key, mapped in TYPE_MAP.items():
        if token.startswith(key):
            return mapped
    return "TEXT"


def parse_column_line(line: str) -> Optional[ColumnDefinition]:
    match = COLUMN_PATTERN.match(line)
    if not match:
        return None
    column_name = match.group(1).strip()
    definition = match.group(2).split("--")[0].strip()
    context_tokens = [token.strip() for token in re.findall(r"\(([^)]+)\)", definition)]
    base_type_match = re.match(r"([A-Za-z0-9_\[\]]+)", definition)
    base_type = base_type_match.group(1) if base_type_match else "TEXT"

    primary_key = any("PK" in token.upper() or "PRIMARY KEY" in token.upper() for token in context_tokens)
    unique = any("UNIQUE" in token.upper() for token in context_tokens)
    not_null = any("NOT NULL" in token.upper() for token in context_tokens)
    optional = any("OPTIONAL" in token.upper() for token in context_tokens)

    return ColumnDefinition(
        name=column_name,
        sqlite_type=map_sqlite_type(base_type),
        primary_key=primary_key,
        unique=unique,
        not_null=not_null and not optional,
    )


def parse_design_file(path: Path) -> List[TableDefinition]:
    tables: List[TableDefinition] = []
    current: Optional[TableDefinition] = None

    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            table_match = TABLE_PATTERN.match(line)
            if table_match:
                table_name = table_match.group(1).strip()
                current = TableDefinition(table_name)
                tables.append(current)
                continue

            if current is None:
                continue

            column = parse_column_line(line)
            if column:
                current.columns.append(column)
                continue

    return tables


def discover_design_files(root: Path) -> List[Path]:
    files: List[Path] = []
    for txt_file in root.rglob("*.txt"):
        name_lower = txt_file.name.lower()
        if "design" not in name_lower:
            continue
        if txt_file.name in IGNORED_FILENAMES:
            continue
        files.append(txt_file)
    return files


def create_tables(connection: sqlite3.Connection, tables: Iterable[TableDefinition]) -> None:
    for table in tables:
        statement = table.create_statement()
        if not statement:
            continue
        connection.execute(statement)


def table_exists(connection: sqlite3.Connection, name: str) -> bool:
    query = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
    return connection.execute(query, (name,)).fetchone() is not None


def get_table_columns(connection: sqlite3.Connection, name: str) -> List[str]:
    return [row[1] for row in connection.execute(f"PRAGMA table_info('{name}')")]


def seed_roles(connection: sqlite3.Connection) -> Dict[str, str]:
    table_name = "auth_service_roles"
    if not table_exists(connection, table_name):
        return {}
    columns = set(get_table_columns(connection, table_name))
    if not {"id", "name"}.issubset(columns):
        return {}

    now = datetime.utcnow().isoformat()
    role_ids: Dict[str, str] = {}
    for role_name, description in ROLE_DESCRIPTIONS.items():
        existing = connection.execute(
            f"SELECT id FROM {table_name} WHERE name = ?",
            (role_name,),
        ).fetchone()
        if existing:
            role_ids[role_name] = existing[0]
            continue

        role_id = str(uuid4())
        payload: Dict[str, object] = {
            "id": role_id,
            "name": role_name,
        }
        if "description" in columns:
            payload["description"] = description
        if "permissions" in columns:
            payload["permissions"] = "{}"
        if "created_at" in columns:
            payload["created_at"] = now

        placeholders = ", ".join("?" for _ in payload)
        connection.execute(
            f"INSERT INTO {table_name} ({', '.join(payload.keys())}) VALUES ({placeholders})",
            tuple(payload.values()),
        )
        role_ids[role_name] = role_id
    return role_ids


def seed_default_user(connection: sqlite3.Connection, default_role_id: Optional[str]) -> None:
    table_name = "auth_service_users"
    if not table_exists(connection, table_name):
        return
    columns = set(get_table_columns(connection, table_name))
    if not {"id", "email"}.issubset(columns):
        return

    existing = connection.execute(
        f"SELECT id FROM {table_name} WHERE email = ?",
        (DEFAULT_USER_PROFILE["email"],),
    ).fetchone()
    if existing:
        return

    now = datetime.utcnow().isoformat()
    user_id = str(uuid4())

    payload: Dict[str, object] = {
        "id": user_id,
        "email": DEFAULT_USER_PROFILE["email"],
    }
    if "username" in columns:
        payload["username"] = DEFAULT_USER_PROFILE["username"]
    if "phone" in columns:
        payload["phone"] = DEFAULT_USER_PROFILE["phone"]
    if "password_hash" in columns:
        payload["password_hash"] = DEFAULT_USER_PROFILE["password_hash"]
    if default_role_id and "role_id" in columns:
        payload["role_id"] = default_role_id
    if "is_active" in columns:
        payload["is_active"] = 1
    if "business_id" in columns:
        payload["business_id"] = None
    if "affiliate_id" in columns:
        payload["affiliate_id"] = None
    if "created_at" in columns:
        payload["created_at"] = now
    if "updated_at" in columns:
        payload["updated_at"] = now

    placeholders = ", ".join("?" for _ in payload)
    connection.execute(
        f"INSERT INTO {table_name} ({', '.join(payload.keys())}) VALUES ({placeholders})",
        tuple(payload.values()),
    )


def build_schema_from_design_docs(connection: sqlite3.Connection) -> None:
    design_files = discover_design_files(SERVICE_ROOT)
    created: Set[str] = set()
    for design_file in design_files:
        for table in parse_design_file(design_file):
            table_name = table.table_name
            if table_name in created:
                continue
            create_tables(connection, [table])
            created.add(table_name)


def query_categories(
    *,
    business_id: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0,
) -> Tuple[List[Dict[str, Optional[str]]], int]:
    """Fetch categories alongside total count for pagination."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        base_sql = (
            "SELECT id, business_id, name, description, parent_id, created_at, updated_at "
            "FROM catalog_service_categories"
        )
        clauses: List[str] = []
        params: List[object] = []

        if business_id:
            clauses.append("business_id = ?")
            params.append(business_id)

        where_clause = ""
        if clauses:
            where_clause = " WHERE " + " AND ".join(clauses)

        total_sql = f"SELECT COUNT(*) FROM catalog_service_categories{where_clause}"
        total = conn.execute(total_sql, params).fetchone()[0]

        sql = f"{base_sql}{where_clause} ORDER BY name"
        page_params = list(params)
        normalized_offset = max(offset, 0)
        if limit and limit > 0:
            sql += " LIMIT ? OFFSET ?"
            page_params.extend([limit, normalized_offset])
        elif normalized_offset > 0:
            sql += " LIMIT -1 OFFSET ?"
            page_params.append(normalized_offset)

        rows = conn.execute(sql, page_params).fetchall()
        categories = [
            {
                "id": row["id"],
                "business_id": row["business_id"],
                "name": row["name"],
                "description": row["description"],
                "parent_id": row["parent_id"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]
        return categories, int(total)
    finally:
        conn.close()


class MockApiRequestHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler to mock catalog-related endpoints."""

    server_version = "MockAPIServer/0.1"
    error_content_type = "application/json"

    def do_GET(self) -> None:  # noqa: N802 (keep BaseHTTPRequestHandler signature)
        parsed = urlparse(self.path)
        if parsed.path == "/categories":
            self._handle_categories(parsed.query)
        elif parsed.path == "/categories/all":
            self._handle_categories(parsed.query, include_all=True)
        else:
            self._send_json(404, {"error": "Not found"})

    def log_message(self, format: str, *args) -> None:  # noqa: A003 (method name from base class)
        logger.info("%s - %s", self.address_string(), format % args)

    def _handle_categories(self, query_string: str, *, include_all: bool = False) -> None:
        params = parse_qs(query_string)
        limit = None if include_all else self._parse_positive_int(params.get("limit", [None])[0])
        business_id = params.get("business_id", [None])[0]
        offset = 0 if include_all else self._parse_non_negative_int(params.get("offset", [None])[0]) or 0
        offset = max(offset, 0)

        try:
            categories, total = query_categories(
                business_id=business_id,
                limit=limit,
                offset=offset,
            )
        except sqlite3.Error as exc:
            logger.exception("Failed to fetch categories: %s", exc)
            self._send_json(500, {"error": "Failed to fetch categories"})
            return

        start_index = offset if categories else None
        end_index = (offset + len(categories) - 1) if categories else None
        has_more = (offset + len(categories)) < total if limit else False
        next_offset = (offset + len(categories)) if has_more else None

        self._send_json(
            200,
            {
                "count": len(categories),
                "total": total,
                "limit": limit,
                "offset": offset,
                "start_index": start_index,
                "end_index": end_index,
                "has_more": has_more,
                "next_offset": next_offset,
                "categories": categories,
            },
        )

    def _send_json(self, status: int, payload: Dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    @staticmethod
    def _parse_positive_int(value: Optional[str]) -> Optional[int]:
        if value is None:
            return None
        try:
            parsed = int(value)
            return parsed if parsed > 0 else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_non_negative_int(value: Optional[str]) -> Optional[int]:
        if value is None:
            return None
        try:
            parsed = int(value)
            return parsed if parsed >= 0 else None
        except (TypeError, ValueError):
            return None


def run_mock_api(host: str, port: int) -> None:
    """Start an HTTP server exposing mock endpoints."""
    server = ThreadingHTTPServer((host, port), MockApiRequestHandler)
    logger.info("Mock API server listening at http://%s:%s", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal. Stopping mock API server...")
    finally:
        server.server_close()


def prepare_database() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as connection:
        build_schema_from_design_docs(connection)
        roles = seed_roles(connection)
        seed_default_user(connection, roles.get("default"))
        connection.commit()


def main(argv: Optional[List[str]] = None) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="Mock API services scaffolding")
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start an HTTP server that exposes mock endpoints after seeding the database",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host interface for the mock API server")
    parser.add_argument("--port", type=int, default=9000, help="Port for the mock API server")
    args = parser.parse_args(argv)

    prepare_database()
    logger.info("Mock services database ready at %s", DB_PATH)

    if args.serve:
        run_mock_api(args.host, args.port)


if __name__ == "__main__":
    main()

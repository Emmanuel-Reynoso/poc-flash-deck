"""Prepares Azurite for local development: container, tables and CORS for browser uploads.

Usage (from the repo root, with Azurite running):  python scripts/dev_setup.py
"""

from __future__ import annotations

import os

from azure.core.exceptions import ResourceExistsError
from azure.data.tables import TableServiceClient
from azure.storage.blob import BlobServiceClient, CorsRule

CONN = os.getenv("STORAGE_CONNECTION_STRING", "UseDevelopmentStorage=true")
# 4280: SWA emulator, 5173: Vite, 4281: the web's end-to-end tests.
ORIGINS = ["http://localhost:4280", "http://localhost:5173", "http://localhost:4281"]
TABLES = [
    os.getenv(f"{name.upper()}_TABLE", name) for name in ("files", "shares", "users", "slugs", "labels")
]


def main() -> None:
    blobs = BlobServiceClient.from_connection_string(CONN)
    blobs.set_service_properties(
        cors=[
            CorsRule(
                allowed_origins=ORIGINS,
                allowed_methods=["PUT", "GET", "HEAD", "OPTIONS"],
                allowed_headers=["*"],
                exposed_headers=["*"],
                max_age_in_seconds=3600,
            )
        ]
    )
    try:
        blobs.create_container(os.getenv("HTML_CONTAINER", "html"))
    except ResourceExistsError:
        pass

    tables = TableServiceClient.from_connection_string(CONN)
    for name in TABLES:
        tables.create_table_if_not_exists(name)

    print("Azurite ready: container, tables and CORS for", ", ".join(ORIGINS))


if __name__ == "__main__":
    main()

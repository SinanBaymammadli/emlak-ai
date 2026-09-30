import sqlite3
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS listings (
            id TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            deal_type TEXT NOT NULL,
            price INTEGER,
            location TEXT,
            rooms TEXT,
            area_m2 REAL,
            land_area_sot REAL,
            lat REAL,
            lng REAL,
            has_repair INTEGER,
            photo_url TEXT,
            url TEXT,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            deleted_at TEXT
        );

        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id TEXT NOT NULL REFERENCES listings(id),
            price INTEGER NOT NULL,
            observed_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS scrape_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            deal_type TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            listings_found INTEGER DEFAULT 0,
            listings_new INTEGER DEFAULT 0,
            listings_updated INTEGER DEFAULT 0,
            listings_deleted INTEGER DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'running'
        );
    """)
    conn.commit()


def upsert_listing(
    conn: sqlite3.Connection,
    listing: dict,
    category: str,
    deal_type: str,
) -> str:
    """Insert or update a listing. Returns 'new', 'updated', or 'unchanged'."""
    now = _now()
    listing_id = listing["id"]
    url = f"https://bina.az/items/{listing_id}"

    row = conn.execute(
        "SELECT price, deleted_at FROM listings WHERE id = ?", (listing_id,)
    ).fetchone()

    if row is None:
        conn.execute(
            """INSERT INTO listings
               (id, category, deal_type, price, location, rooms, area_m2,
                land_area_sot, lat, lng, has_repair, photo_url, url,
                first_seen_at, last_seen_at, deleted_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL)""",
            (
                listing_id,
                category,
                deal_type,
                listing.get("price"),
                listing.get("location"),
                listing.get("rooms"),
                listing.get("area_m2"),
                listing.get("land_area_sot"),
                listing.get("lat"),
                listing.get("lng"),
                listing.get("has_repair"),
                listing.get("photo_url"),
                url,
                now,
                now,
            ),
        )
        if listing.get("price") is not None:
            conn.execute(
                "INSERT INTO price_history (listing_id, price, observed_at) VALUES (?,?,?)",
                (listing_id, listing["price"], now),
            )
        conn.commit()
        return "new"

    existing_price, deleted_at = row

    # Resurrect if it was previously deleted
    if deleted_at is not None:
        conn.execute(
            "UPDATE listings SET deleted_at = NULL, last_seen_at = ? WHERE id = ?",
            (now, listing_id),
        )

    new_price = listing.get("price")
    if new_price != existing_price:
        conn.execute(
            """UPDATE listings SET price=?, location=?, rooms=?, area_m2=?,
               land_area_sot=?, lat=?, lng=?, has_repair=?, photo_url=?,
               last_seen_at=? WHERE id=?""",
            (
                new_price,
                listing.get("location"),
                listing.get("rooms"),
                listing.get("area_m2"),
                listing.get("land_area_sot"),
                listing.get("lat"),
                listing.get("lng"),
                listing.get("has_repair"),
                listing.get("photo_url"),
                now,
                listing_id,
            ),
        )
        if new_price is not None:
            conn.execute(
                "INSERT INTO price_history (listing_id, price, observed_at) VALUES (?,?,?)",
                (listing_id, new_price, now),
            )
        conn.commit()
        return "updated"

    conn.execute(
        "UPDATE listings SET last_seen_at=? WHERE id=?", (now, listing_id)
    )
    conn.commit()
    return "unchanged"


def mark_deleted(
    conn: sqlite3.Connection,
    ids_still_active: set[str],
    category: str,
    deal_type: str,
) -> int:
    """Mark listings not seen in this scrape as deleted. Returns count deleted."""
    now = _now()
    if ids_still_active:
        placeholders = ",".join("?" * len(ids_still_active))
        conn.execute(
            f"""UPDATE listings SET deleted_at=?
                WHERE category=? AND deal_type=? AND deleted_at IS NULL
                AND id NOT IN ({placeholders})""",
            [now, category, deal_type, *ids_still_active],
        )
    else:
        conn.execute(
            """UPDATE listings SET deleted_at=?
               WHERE category=? AND deal_type=? AND deleted_at IS NULL""",
            (now, category, deal_type),
        )
    count = conn.execute("SELECT changes()").fetchone()[0]
    conn.commit()
    return count


def start_scrape_run(conn: sqlite3.Connection, category: str, deal_type: str) -> int:
    cur = conn.execute(
        "INSERT INTO scrape_runs (category, deal_type, started_at, status) VALUES (?,?,?,'running')",
        (category, deal_type, _now()),
    )
    conn.commit()
    return cur.lastrowid


def finish_scrape_run(
    conn: sqlite3.Connection,
    run_id: int,
    found: int,
    new: int,
    updated: int,
    deleted: int,
    status: str = "ok",
) -> None:
    conn.execute(
        """UPDATE scrape_runs SET finished_at=?, listings_found=?, listings_new=?,
           listings_updated=?, listings_deleted=?, status=? WHERE id=?""",
        (_now(), found, new, updated, deleted, status, run_id),
    )
    conn.commit()

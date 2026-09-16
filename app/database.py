"""Small SQLite catalogue reconciled from the fictional seed catalogue."""
from contextlib import contextmanager
import json
import sqlite3
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "campusswap.db"


@contextmanager
def connect():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY, title TEXT NOT NULL,
            description TEXT NOT NULL, category TEXT NOT NULL,
            price_cents INTEGER NOT NULL, condition TEXT NOT NULL,
            location TEXT NOT NULL, seller TEXT NOT NULL, icon TEXT NOT NULL
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS listing_embeddings (
            listing_id INTEGER PRIMARY KEY REFERENCES listings(id),
            model TEXT NOT NULL, content_hash TEXT NOT NULL,
            embedding_json TEXT NOT NULL
        )""")
        listings = json.loads((ROOT / "data" / "seed_listings.json").read_text(encoding="utf-8"))
        # The demo has no listing-management feature, so these stable IDs are
        # seed-owned. Reconcile them on startup so an existing local database
        # receives catalogue expansions without a manual database reset.
        db.executemany("""INSERT INTO listings VALUES
            (:id, :title, :description, :category, :price_cents,
             :condition, :location, :seller, :icon)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title, description = excluded.description,
                category = excluded.category, price_cents = excluded.price_cents,
                condition = excluded.condition, location = excluded.location,
                seller = excluded.seller, icon = excluded.icon""", listings)

        # Listing vectors are keyed by the exact text used for semantic search.
        # Preserve valid cached vectors and discard only entries made stale by a
        # seed change; new listings are embedded lazily by semantic_search.
        current_hashes = {
            item["id"]: embedding_hash(_indexed_text(item)) for item in listings
        }
        cached = db.execute("SELECT listing_id, content_hash FROM listing_embeddings").fetchall()
        stale_ids = [row["listing_id"] for row in cached
                     if current_hashes.get(row["listing_id"]) != row["content_hash"]]
        if stale_ids:
            db.executemany("DELETE FROM listing_embeddings WHERE listing_id = ?",
                           [(listing_id,) for listing_id in stale_ids])


def _indexed_text(item):
    """Keep cache reconciliation aligned with semantic_search.listing_text."""
    return "\n".join((item["title"], item["description"], item["category"], item["condition"]))


def browse(keyword="", category=""):
    # instr treats %, _ and quotes as literal text, not SQL patterns.
    with connect() as db:
        rows = db.execute("""SELECT * FROM listings
            WHERE (? = '' OR instr(lower(title || ' ' || description), lower(?)) > 0)
            AND (? = '' OR category = ?) ORDER BY id""",
            (keyword, keyword, category, category)).fetchall()
        return [dict(row) for row in rows]


def get_listing(listing_id):
    with connect() as db:
        row = db.execute("SELECT * FROM listings WHERE id = ?", (listing_id,)).fetchone()
        return dict(row) if row else None


def categories():
    with connect() as db:
        return [row[0] for row in db.execute("SELECT DISTINCT category FROM listings ORDER BY category")]


def embedding_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get_embedding(listing_id, model, text):
    with connect() as db:
        row = db.execute("""SELECT embedding_json FROM listing_embeddings
            WHERE listing_id = ? AND model = ? AND content_hash = ?""",
            (listing_id, model, embedding_hash(text))).fetchone()
    return json.loads(row["embedding_json"]) if row else None


def save_embedding(listing_id, model, text, vector):
    with connect() as db:
        db.execute("""INSERT INTO listing_embeddings
            (listing_id, model, content_hash, embedding_json) VALUES (?, ?, ?, ?)
            ON CONFLICT(listing_id) DO UPDATE SET model = excluded.model,
            content_hash = excluded.content_hash, embedding_json = excluded.embedding_json""",
            (listing_id, model, embedding_hash(text), json.dumps(vector)))


def embedding_count():
    with connect() as db:
        return db.execute("SELECT COUNT(*) FROM listing_embeddings").fetchone()[0]

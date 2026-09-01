"""
Extends the genre-subset catalog with books from the full UCSD dump.

The eight genre files cover ~1.24M editions of the corpus's 2.36M. The gap is
mostly general fiction, literary fiction, and non-fiction, which have no
subset file. This streams the full dump, skips every book_id already held,
and writes the remainder plus a corpus-wide genre map.

    python src/download-more-ucsd.py

Nothing is stored uncompressed: the 2GB stream is decompressed in flight and
only kept records reach disk.
"""

import gzip
import json
import os
from collections import Counter

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests
from tqdm import tqdm

BASE = "https://mcauleylab.ucsd.edu/public_datasets/gdrive/goodreads"

INITIAL = os.path.join("data", "initial")
RAW = os.path.join("data", "raw")

BOOKS_URL = f"{BASE}/goodreads_books.json.gz"
GENRES_URL = f"{BASE}/goodreads_book_genres_initial.json.gz"

BATCH = 50_000

SHELF_STOPWORDS = {"to-read", "currently-reading", "read", "want-to-read", "to-buy",
                   "owned", "owned-books", "books-i-own", "i-own", "my-books", "library",
                   "wish-list", "wishlist", "default", "favorites", "favourites",
                   "all-time-favorites", "shelfari-favorites", "re-read", "reread",
                   "dnf", "abandoned", "unfinished", "on-hold", "maybe",
                   "kindle", "ebook", "ebooks", "audiobook", "audiobooks", "audible",
                   "paperback", "hardcover", "book-club", "series", "novels", "books"}


def clean_shelves(shelves) -> list:
    if shelves is None:
        return []
    return [s for s in shelves
            if str(s.get("name", "")).strip().lower() not in SHELF_STOPWORDS]


def existing_book_ids() -> set:
    """book_ids already covered by the eight genre parquets."""
    have = set()
    files = sorted(f for f in os.listdir(INITIAL) if f.endswith(".parquet"))
    if not files:
        raise SystemExit(f"no parquet files in {INITIAL} — run download-ucsd.py first")

    for name in files:
        ids = pd.read_parquet(os.path.join(INITIAL, name), columns=["book_id"]).book_id
        have.update(ids.astype(str))
        print(f"  {name:<48} {len(ids):>9,}")

    print(f"  {'TOTAL DISTINCT':<48} {len(have):>9,}")
    return have


def stream_lines(url: str, desc: str):
    """Yield decoded lines from a remote .json.gz without storing it."""
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length", 0))
        bar = tqdm(total=total or None, unit="B", unit_scale=True,
                   unit_divisor=1024, desc=desc)

        raw = r.raw
        read = raw.read

        def counting_read(n):                 # advance the bar by compressed bytes
            chunk = read(n)
            bar.update(len(chunk))
            return chunk

        raw.read = counting_read
        try:
            for line in gzip.GzipFile(fileobj=raw):
                yield line
        finally:
            bar.close()


def download_genre_map(dest: str) -> dict:
    """book_id -> list of genres, corpus-wide. Includes fiction/non-fiction,
    which the subset filenames never provided."""
    if os.path.exists(dest):
        print(f"  cached {dest}")
        df = pd.read_parquet(dest)
        return dict(zip(df.book_id, df.genres))

    rows = []
    for line in stream_lines(GENRES_URL, "genre map"):
        rec = json.loads(line)
        g = rec.get("genres") or {}
        # keys are compound strings: "history, historical fiction, biography"
        flat = sorted({part.strip() for key in g for part in key.split(",") if part.strip()})
        rows.append({"book_id": str(rec["book_id"]), "genres": flat})

    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    df.to_parquet(dest, index=False, compression="zstd")
    print(f"  {len(df):,} books mapped -> {dest}")
    return dict(zip(df.book_id, df.genres))


def download_new_books(have: set, genre_map: dict, dest: str, min_desc_words: int) -> int:
    writer, batch, kept = None, [], 0
    stats = Counter()

    def flush(rows):
        nonlocal writer
        table = pa.Table.from_pandas(pd.DataFrame(rows), preserve_index=False)
        if writer is None:
            writer = pq.ParquetWriter(dest, table.schema, compression="zstd")
        writer.write_table(table)

    for line in stream_lines(BOOKS_URL, "books"):
        rec = json.loads(line)
        stats["seen"] += 1

        bid = str(rec.get("book_id"))
        if bid in have:
            stats["already_have"] += 1
            continue

        desc = (rec.get("description") or "").strip()
        if len(desc.split()) < min_desc_words:
            stats["thin_description"] += 1
            continue

        rec["book_id"] = bid
        rec["popular_shelves"] = clean_shelves(rec.get("popular_shelves"))
        rec["genre"] = genre_map.get(bid, [])

        batch.append(rec)
        kept += 1

        if len(batch) >= BATCH:
            flush(batch)
            batch = []

    if batch:
        flush(batch)
    if writer is not None:
        writer.close()

    print(f"\n  seen              {stats['seen']:>9,}")
    print(f"  already have      {stats['already_have']:>9,}")
    print(f"  thin description  {stats['thin_description']:>9,}")
    print(f"  NEW               {kept:>9,}")
    return kept


def main():
    os.makedirs(INITIAL, exist_ok=True)
    os.makedirs(RAW, exist_ok=True)

    print("existing catalog:")
    have = existing_book_ids()

    print("\ngenre map:")
    genre_map = download_genre_map(os.path.join(RAW, "book_genres.parquet"))

    raw = input("\nminimum description words to keep [25, 0 = keep all]: ").strip()
    min_desc_words = int(raw) if raw else 25

    dest = os.path.join(INITIAL, "goodreads_books_extra.parquet")
    print(f"\nstreaming full dump -> {dest}")
    kept = download_new_books(have, genre_map, dest, min_desc_words)

    if kept:
        size = os.path.getsize(dest) / 1e6
        print(f"\nwrote {dest}  ({size:,.0f} MB)")
    else:
        print("\nnothing new")


if __name__ == "__main__":
    main()
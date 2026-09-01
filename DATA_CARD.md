# Data card — UCSD Goodreads Book Graph

## Source

| | |
|---|---|
| Dataset | UCSD Book Graph (Goodreads) |
| Maintainers | Mengting Wan, Julian McAuley (UCSD) |
| Landing page | https://cseweb.ucsd.edu/~jmcauley/datasets/goodreads.html |
| File host | `https://mcauleylab.ucsd.edu/public_datasets/gdrive/goodreads` |
| Collected | Late 2017, from public Goodreads shelves |
| Snapshot | Static — not updated. Ratings and shelf counts are frozen at 2017. |

## License and use

**Academic use only. Do not redistribute. No commercial use.**

User IDs and review IDs are anonymised by the maintainers. Only publicly
visible shelves were scraped.

If this data backs a publicly deployed demo, review the terms first — a public
site serving the raw records is arguably redistribution.

### Required citation

> Mengting Wan, Julian McAuley. "Item Recommendation on Monotonic Behavior
> Chains." RecSys 2018.

> Mengting Wan, Rishabh Misra, Ndapa Nakashole, Julian McAuley. "Fine-Grained
> Spoiler Detection from Large-Scale Review Corpora." ACL 2019.

## Scope

Full corpus: 2,360,655 books · 1,521,962 works · 829,529 authors ·
876,145 users · 228,648,342 user–book interactions.

This project uses the **genre subsets**, which the maintainers recommend for
experimentation. Book counts per subset:

| Genre slug | Books |
|---|---|
| `children` | 124,082 |
| `comics_graphic` | 89,411 |
| `fantasy_paranormal` | 258,585 |
| `history_biography` | 302,935 |
| `mystery_thriller_crime` | 219,235 |
| `poetry` | 36,514 |
| `romance` | 335,449 |
| `young_adult` | 93,398 |

Subsets overlap — a book can appear in several — and are **not
self-contained**: a subset may reference authors, works, or series whose
records live only in the full corpus files.

There is no literary-fiction, classics, or general-fiction subset. Queries
about canonical literary works are not answerable from any genre subset alone.

## Files used

| File | Purpose |
|---|---|
| `byGenre/goodreads_books_<genre>.json.gz` | Book metadata, one JSON object per line |
| `goodreads_book_authors.json.gz` | `author_id` → author name (corpus-wide, not genre-split) |
| `goodreads_book_genres_initial.json.gz` | Pre-extracted genre tags (corpus-wide) |

Not currently used: `goodreads_interactions_*`, `goodreads_reviews_*`,
`goodreads_book_works.json.gz`, `goodreads_book_series.json.gz`.

## Fields

29 fields per book record. All values arrive as **strings**, including
numerics and booleans.

**Identifiers** — `book_id`, `work_id`, `isbn`, `isbn13`, `asin`, `kindle_asin`

**Text** — `title`, `title_without_series`, `description`

**Attributes** — `authors` (list of `{author_id, role}`), `language_code`,
`num_pages`, `format`, `publisher`, `edition_information`,
`publication_year`, `publication_month`, `publication_day`, `is_ebook`,
`country_code`

**Signals** — `average_rating`, `ratings_count`, `text_reviews_count`,
`popular_shelves` (list of `{name, count}`), `similar_books` (list of
`book_id`), `series` (list of series ids)

**Links** — `url`, `link`, `image_url`

### Field notes

- `authors` contains IDs only. Names require joining `goodreads_book_authors.json.gz`.
- `series` ids cannot be used to construct Goodreads URLs (documented upstream).
- `title_without_series` is usually preferable to `title` for display and embedding.
- Missing numerics are the empty string `""`, not `null`.

## Known issues

**Editions inflate row counts.** 2.36M book records map to ~1.52M works.
Roughly a third of rows are alternate editions of a book already present.
Deduplicating on `work_id` is necessary or recommendation output will repeat
the same title several times. Which edition to keep is a real choice —
first-seen-wins tends to select obscure reprints over canonical editions;
selecting by highest `ratings_count` is more robust.

**Descriptions are frequently empty.** Books with no description are invisible
to text-based retrieval. Measure the rate on your chosen subset before
treating the advertised book count as your catalog size.

**`popular_shelves` mixes content tags with reading status.** The highest-count
shelves are almost always `to-read`, `currently-reading`, and `owned`. Below
those sit genuine descriptors (`unreliable-narrator`, `magical-realism`) and a
long tail of personal shelves (`jos-tbr-2015`). A stopword list handles the
first category; only a count threshold handles the third.

**Multilingual.** `language_code` is often empty rather than absent, so a
strict equality filter on `eng` silently drops records of unknown language.

**Boilerplate in descriptions.** A minority begin with Goodreads edition notes
("Alternate Cover Edition ISBN...") that run directly into the real text with
no sentence terminator.

**Popularity skew.** `ratings_count` spans several orders of magnitude.
Unweighted models will surface the same well-known titles regardless of query.

## Processing applied

Pipeline: `download → decompress → filter shelves → parquet`

1. Download `goodreads_books_<genre>.json.gz` (streamed, 1 MB chunks) to `data/`.
2. Parse line by line as JSONL.
3. Remove stopword entries from `popular_shelves` — reading status, ownership,
   and format shelves. Counts and structure preserved for surviving entries.
4. Write to `data/initial/goodreads_books_<genre>.parquet`, zstd-compressed.

**All other fields retained unmodified.** No field selection, no type coercion,
no deduplication, no language filtering, no row filtering at this stage.

### Outputs

| Path | Contents |
|---|---|
| `data/goodreads_books_<genre>.json.gz` | Unmodified source download |
| `data/initial/goodreads_books_<genre>.parquet` | Shelf-filtered, all fields |

Reproduce with `python <script>.py`, entering the genre slug when prompted.

## Statistics

<!-- Fill in after running. Suggested commands below. -->

| Metric | Value |
|---|---|
| Genre | _TBD_ |
| Rows | _TBD_ |
| Distinct `work_id` | _TBD_ |
| Empty descriptions | _TBD_ |
| Median description length | _TBD_ |
| `language_code == "eng"` | _TBD_ |
| `language_code == ""` | _TBD_ |
| Books with no shelves after filtering | _TBD_ |
| Source `.json.gz` size | _TBD_ |
| Parquet size | _TBD_ |

```python
import pandas as pd
d = pd.read_parquet("data/initial/goodreads_books_<genre>.parquet")

len(d)
d.work_id.nunique()
d.description.eq("").mean()
d.description.str.len().median()
d.language_code.value_counts(normalize=True).head()
d.popular_shelves.map(len).eq(0).mean()
```

## Suitability

**Good for** — content-based retrieval over descriptions and shelf tags;
item-item similarity; genre and metadata filtering; offline evaluation.

**Limited for** — anything needing current data (2017 snapshot; books published
since are absent); literary or general fiction (no such subset); non-English
readers; long-tail discovery within a single genre subset.

**Requires additional files** — collaborative filtering, which needs
`goodreads_interactions_*`, not downloaded by this pipeline.
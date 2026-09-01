# Book Recommendation Engine

## Data

Check data card. Taken from UCSD Goodreads data.

### Books Data
- Downloaded with `src/download-ucsd.py` script. Enter a genre, return a full URL, chunk and load into parquet via `pyarrow`.
- Cleaned with `notebooks/book_data.ipynb`. All the different parquet files were combined into 1.
- `popular_shelves` have goodreads tags as keys like 'enemies-to-lovers' or 'gothic' with their count as their value. Converted to 2 columns - `tags` and `tag_counts`.
- A book can be in more than one genre (Frankenstein can be romance and fantasy). Rows were identical apart from the genre so collapsed them into one row per `book_id` with genre as a list.
- Box sets, omnibuses and trilogy collections flagged with `is_bundle`. Not dropped, just labelled.
- Every edition of a book has its own `book_id` but shares a `work_id`, like there were 520 copies of Pride and Prejudice. Collapsed editions into works, keeping one canonical edition. English first, then one with a description, then most rated. Everything else mostly aggregated or averaged.
- Used `langdetect` to detect languages of books without one. Filtered for English.
- Saved to `english_works.parquet`.
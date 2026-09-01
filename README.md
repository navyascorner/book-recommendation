# NoraBot: Book Recommendation Engine

## What is it?

User Input = `i want to read something feel-good and short.`

Output = `The Little Prince`

## Data

Check data card. Taken from UCSD Goodreads data.

### Books Data Cleanup
1.  Downloaded with `src/download-ucsd.py` script. Enter a genre, return a full URL, chunk and load into parquet via `pyarrow`.
2. Cleaned with `notebooks/book_data.ipynb`. All the different parquet files were combined into 1.
3. `popular_shelves` have goodreads tags as keys like 'enemies-to-lovers' or 'gothic' with their count as their value. Converted to 2 columns - `tags` and `tag_counts`.
4. A book can be in more than one genre (Frankenstein can be romance and fantasy). Rows were identical apart from the genre so collapsed them into one row per `book_id` with genre as a list.
5. Box sets labelled. Every edition of a book has its own `book_id` but shares a `work_id`, like there were 520 copies of Pride and Prejudice. Collapsed editions into works, keeping one canonical edition. English first, then one with a description, then most rated. Everything else mostly aggregated or averaged.
6. Used `langdetect` to detect languages of books without one. Filtered for English.
7. Saved to `english_works.parquet`.

## Books Dataset

```
I will be using The Little Prince as an example.
```

1. Tags by themselves were not enough for the goal.

```
77 tags total, 0 affective
'classics(3833138)', 'fiction(2121014)', 'fantasy(1531321)', 'childrens(1092573)', 'children(897490)', 'classic(749796)', 'french(636833)', 'children-s(487124)', 'young-adult(448546)', 'philosophy(429403)', 'children-s-books(385261)', 'childhood(300490)', 'literature(296692)', 'kids(279183)', 'childrens-books(237639)'
```

2. I tried `sentence-transformers` to embedd them. If the threshold was too high, tags like sci-fi would get combined into fiction. If too low, tags like classic-s or classic would be separate only.

3. It did not make sense to include tags. They were too many, and did not add any real value. And I cannot possibly apply enough manual rules for all 500k books.
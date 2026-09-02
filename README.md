# NoraBot: Book Recommendation Engine

## What is it?

User Input = `i want to read something feel-good and short.`

Output = `The Little Prince`

## Data
1. 1002607 (1M+) books
2. 827,743 users
3. 105.7M interactions across  and 996,177 works, with only 0.0128% density

## About the Code and Decisions

### Books Data Cleanup
1.  Downloaded with `src/download-ucsd.py` script. Enter a genre, return a full URL, chunk and load into parquet via `pyarrow`.
2. Cleaned with `notebooks/book_data.ipynb`. All the different parquet files were combined into 1.
3. `popular_shelves` have goodreads tags as keys like 'enemies-to-lovers' or 'gothic' with their count as their value. Converted to 2 columns - `tags` and `tag_counts`.
4. A book can be in more than one genre (Frankenstein can be romance and fantasy). Rows were identical apart from the genre so collapsed them into one row per `book_id` with genre as a list.
5. Box sets labelled. Every edition of a book has its own `book_id` but shares a `work_id`, like there were 520 copies of Pride and Prejudice. Collapsed editions into works, keeping one canonical edition. English first, then one with a description, then most rated. Everything else mostly aggregated or averaged.
6. Used `langdetect` to detect languages of books without one. Filtered for English.
7. Saved to `english_works.parquet`.

### Books Dataset
1. Tags by themselves were not enough for the goal. They were veery messy, like `'classics(3833138)', 'fiction(2121014)', 'fantasy(1531321)', 'childrens(1092573)', 'children(897490)', 'classic(749796)'`.
2. I tried `sentence-transformers` to embedd them. If the threshold was too high, tags like sci-fi would get combined into fiction. If too low, tags like classic-s or classic would be separate only.
3. Tags preserved for now because if reviews turn out to be worse, I can just use tags.

### Train/Test Split

#### User Split
1. 10k for test, 10k for eval, rest 800k+ for training. CF would mean reducing more based on number of interactions. Both positive and negative signals preserved.
2. For val/test sets, the condition is to have more than 20 ratings of 4 or 5.
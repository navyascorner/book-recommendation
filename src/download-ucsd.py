import requests
from tqdm import tqdm
import os
import gzip
import pandas as pd
import json

# Configs
# url for UCSD goodreads dataset
BASE = "https://mcauleylab.ucsd.edu/public_datasets/gdrive/goodreads"
os.makedirs("data", exist_ok=True)

GENRES = ['children', 'comics_graphic', 'fantasy_paranormal', 'history_biography',
          'mystery_thriller_crime', 'poetry', 'romance', 'young_adult']

SHELF_STOPWORDS = { "to-read", "currently-reading", "read", "want-to-read", "to-buy",
                   "owned", "owned-books", "books-i-own", "i-own", "my-books", "library",
                   "wish-list", "wishlist", "default", "favorites", "favourites",
                   "all-time-favorites", "shelfari-favorites", "re-read", "reread",
                   "dnf", "abandoned", "unfinished", "on-hold", "maybe",
                   "kindle", "ebook", "ebooks", "audiobook", "audiobooks", "audible",
                   "paperback", "hardcover", "book-club", "series", "novels", "books"}

def get_books_url(genre:str) -> str:
    '''
    actual paths are something like "https://mcauleylab.ucsd.edu/public_datasets/gdrive/goodreads/byGenre/goodreads_books_poetry.json.gz"
    Params:
        genre: genre to generate a path for
    returns the book file path
    '''
    if genre not in GENRES:
        raise ValueError(f"Unknown genre {genre}. Choose from: {', '.join(GENRES)}")
    
    return f"{BASE}/byGenre/goodreads_books_{genre}.json.gz"


def download_books(url:str, dest:str) -> None:
    '''
    params:
        url: url returned by get_books_url function
        dest: location where files are saved locally
    '''
    response = requests.get(url, stream=True) # streaming and chunking the data so that we can see progress
    response.raise_for_status()

    total = int(response.headers.get("Content-Length", 0)) # so that tqdm knows that 100% is

    with open(dest, "wb") as f:
        with tqdm(total=total, unit="B", unit_scale=True) as bar: #tqdm bar
            for chunk in response.iter_content(chunk_size=1024 * 1024): # for chunk
                f.write(chunk) # the actual writing
                bar.update(len(chunk)) # update the bar


def clean_shelves(shelves) -> list:
    '''
    params:
        shelves: a popular_shelves value, list of {"count": ..., "name": ...}
    returns the same list with stopword shelves removed
    '''
    if shelves is None:
        return []
    return [s for s in shelves
            if str(s.get("name", "")).strip().lower() not in SHELF_STOPWORDS]


def json_to_parquet(src: str, dest: str) -> None:
    '''
    params:
        src: path to the downloaded .json.gz file (one JSON object per line)
        dest: path to write the .parquet file to
    '''
    records = []
    with gzip.open(src, "rt", encoding="utf-8") as f:
        for line in tqdm(f, desc="reading", unit=" books"):
            if line.strip():
                rec = json.loads(line)
                rec["popular_shelves"] = clean_shelves(rec.get("popular_shelves"))
                records.append(rec)
    df = pd.DataFrame(records)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    df.to_parquet(dest, index=False, compression="zstd")
    print(f"{len(df):,} rows, {len(df.columns)} columns")


def main():
    # enter a genre
    print(f"Genres: {', '.join(GENRES)}")
    genre = input("Enter a genre: ").strip().lower()

    # get the url and destination
    url = get_books_url(genre)
    dest = os.path.join("data", f"goodreads_books_{genre}.json.gz")

    print(f"Downloading {genre}")
    download_books(url, dest)
    print(f"Saved to {dest}")

    parquet_dest = os.path.join("data", "initial", f"goodreads_books_{genre}.parquet")
    print(f"Converting to parquet")
    json_to_parquet(dest, parquet_dest)
    print(f"Saved to {parquet_dest}")

if __name__ == "__main__":
    main()
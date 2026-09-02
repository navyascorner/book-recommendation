# splitting the users into train/val/test sets
# to go into val/test set, a user should have given at least 20 4/5 ratings

# importing libraries
import argparse
from pathlib import Path
import numpy as np
import pandas as pd


def build(df, min_pos=20, n_val=10_000, n_test=10_000, seed=0):
    '''
        df — interactions, needs user_id and rating
        min_pos — minimum 4/5-star ratings to be eligible for val or test
        n_val, n_test — how many users in each cohort
        seed — makes the random draw reproducible
    '''

    rng = np.random.default_rng(seed)

    n_total = df.groupby("user_id").size().rename("n_total")
    n_pos = (df[df.rating >= 4].groupby("user_id").size()
             .reindex(n_total.index, fill_value=0).rename("n_pos"))
    users = pd.concat([n_total, n_pos], axis=1)

    eligible = users.index[users.n_pos >= min_pos].to_numpy()
    need = n_val + n_test
    if eligible.size < need:
        raise ValueError(f"{eligible.size:,} eligible < {need:,} needed")

    # Stratify on total activity: light and heavy readers fail differently,
    # and a uniform draw would be mostly median users.
    q = pd.qcut(users.loc[eligible].n_total, 4, labels=False, duplicates="drop")
    per = need // q.nunique()
    picked = np.concatenate([
        rng.choice(pool, size=min(per, pool.size), replace=False)
        for k in sorted(q.unique())
        if (pool := eligible[(q == k).to_numpy()]).size
    ])
    rng.shuffle(picked)

    users["cohort"] = "train"
    users.loc[picked[:n_val], "cohort"] = "val"
    users.loc[picked[n_val:need], "cohort"] = "test"
    return users.reset_index()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interactions", required=True)
    ap.add_argument("--out-dir", default="data/splits")
    ap.add_argument("--min-pos", type=int, default=20)
    ap.add_argument("--n-val", type=int, default=10_000)
    ap.add_argument("--n-test", type=int, default=10_000)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
 
    df = pd.read_parquet(a.interactions)
    users = build(df[["user_id", "rating"]], a.min_pos,
                  a.n_val, a.n_test, a.seed)
 
    assert users.user_id.is_unique
    assert users.groupby("cohort").size().drop("train").eq(
        [a.n_test, a.n_val]).all()
    assert (users.loc[users.cohort != "train", "n_pos"] >= a.min_pos).all()
 
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
 
    df = df.merge(users[["user_id", "cohort"]], on="user_id", how="left")
    assert df.cohort.notna().all(), "user lost in merge"
 
    for name, g in df.groupby("cohort"):
        path = out / f"{name}_split.parquet"
        g.drop(columns="cohort").to_parquet(path, index=False,
                                            compression="zstd")
        print(f"  {name:<6} {len(g):>12,} rows  "
              f"{g.user_id.nunique():>8,} users -> {path}")
 
    print(f"\neligible (>={a.min_pos} positives): "
          f"{(users.n_pos >= a.min_pos).sum():,}")
 
 
if __name__ == "__main__":
    main()
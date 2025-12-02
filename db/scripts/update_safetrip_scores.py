import os
from dotenv import load_dotenv
from supabase import create_client


# Load environment variables
load_dotenv(dotenv_path="/Users/sanjeevkamath/Documents/Projects/SafeTrip IQ/SafeTrip-IQ/.env")

url = os.getenv("SUPABASE_URL")
key = os.getenv("ANON_KEY")
supabase = create_client(url, key)


def compute_scores(bert_score, clustering_score):
    """
    Apply your formulas to compute clustering, bert, and safetrip.
    """
    has_bert = bert_score is not None
    has_cluster = clustering_score is not None

    clustering_val = None
    bert_val = None
    safetrip = None

    # Compute clustering metric
    if has_cluster:
        clustering_val = 20 - (4 * clustering_score)

    # Compute bert metric
    if has_bert:
        bert_val = 20 - (5 * bert_score)

    # Compute safetrip metric
    if has_bert and has_cluster:
        safetrip = (clustering_val + bert_val) / 4
    elif has_bert:      # only BERT available
        safetrip = bert_val / 2
    elif has_cluster:   # only clustering available
        safetrip = clustering_val / 2

    return clustering_val, bert_val, safetrip


def update_scores_table():
    # Get all rows from scores table
    res = supabase.table("scores").select("*").execute()
    rows = res.data

    updated_rows = []

    for row in rows:
        iso3 = row["iso3"]
        bert_score = row.get("bert_score")
        clustering_score = row.get("clustering_score")

        # Compute new values using your formula
        clustering_val, bert_val, safetrip = compute_scores(bert_score, clustering_score)

        updated_rows.append({
            "iso3": iso3,
            "safe_trip_score": safetrip
        })

    # Upsert back into Supabase
    upsert_res = supabase.table("scores").upsert(updated_rows).execute()
    print("Updated scores:", upsert_res)


if __name__ == "__main__":
    update_scores_table()

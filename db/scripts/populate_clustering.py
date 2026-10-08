import pandas as pd
import os
from pathlib import Path
if __package__:
    from .supabase_writer import get_writer_client
else:
    from supabase_writer import get_writer_client

supabase = get_writer_client()

root = Path(__file__).resolve().parents[2]
input_path = Path(os.environ.get("SAFETRIP_CLUSTERING_CSV", "pipeline/clustering/output/clustering_output.csv"))
if not input_path.is_absolute():
    input_path = root / input_path
df = pd.read_csv(input_path)

for _, row in df.iterrows():
    supabase.table("clustering").upsert({
        "iso3": row["iso3"],
        "clustering_score": int(row["cluster"]),
        "ppi": float(row["ppi_score"]),
        "gpi": float(row["gpi_score"]),
        "gti": float(row["gti_score"]),
        "pvi": float(row["pvi_score"])
    }).execute()

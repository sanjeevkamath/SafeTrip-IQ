import pandas as pd
from supabase import create_client
from dotenv import load_dotenv
import os

# Explicitly load .env to avoid path issues
load_dotenv(dotenv_path="/Users/sanjeevkamath/Documents/Projects/SafeTrip IQ/SafeTrip-IQ/.env")

url = os.getenv("SUPABASE_URL")
key = os.getenv("ANON_KEY")

print("Loaded URL:", url)
print("Loaded KEY:", key[:6] + "..." if key else None)

supabase = create_client(url, key)

df = pd.read_csv("pipeline/clustering/output/clustering_output.csv")

for _, row in df.iterrows():
    supabase.table("clustering").upsert({
        "iso3": row["iso3"],
        "clustering_score": int(row["cluster"]),
        "ppi": float(row["ppi_score"]),
        "gpi": float(row["gpi_score"]),
        "gti": float(row["gti_score"]),
        "pvi": float(row["pvi_score"])
    }).execute()

experience_level = 'cracked'


if experience_level != 'cracked':
    print("You need to lock in")
else:
    print("Congratulations, you're all set!")
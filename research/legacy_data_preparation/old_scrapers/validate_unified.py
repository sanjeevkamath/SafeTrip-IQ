from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
UNIFIED = ROOT / "unified_data" / "unified_travel_data.json"

def main():
    df = pd.read_json(UNIFIED)

    print(f"[INFO] rows: {len(df)}")
    for col in ["advisory_level","gpi_score","gti_score","events","events_year","numbeo_crime_index","ppi_score"]:
        got = int(df[col].notna().sum())
        pct = (got/len(df)*100) if len(df) else 0
        print(f"  coverage {col:20s}: {got:4d} / {len(df):4d} ({pct:4.1f}%)")

    # flag obsolete or special codes by name (you can add more here)
    obsolete = df[df["country_name"].isin(["Netherlands Antilles"])]
    if not obsolete.empty:
        print("\n[WARN] obsolete rows detected:")
        print(obsolete[["iso2","country_name"]].to_string(index=False))

    # show rows where events are old relative to max for that row set
    max_year = int(df["events_year"].dropna().max() or 0)
    stale = df[(df["events_year"].notna()) & (df["events_year"] < max_year)]
    if not stale.empty:
        print(f"\n[INFO] events not from latest year ({max_year}): {len(stale)} rows (sample)")
        print(stale[["country_name","events_year","events"]].head(10).to_string(index=False))

if __name__ == "__main__":
    main()

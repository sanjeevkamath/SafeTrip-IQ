if __package__:
    from .supabase_writer import get_writer_client
else:
    from supabase_writer import get_writer_client



def main():
    import argparse
    parser = argparse.ArgumentParser(description="Historical, non-idempotent cluster remapping. Never use for routine refreshes.")
    parser.add_argument("--write", action="store_true", required=True)
    parser.parse_args()
    supabase = get_writer_client()
    print("[INFO] Fetching all clustering records...")
    # Fetch all rows
    response = supabase.table("clustering").select("*").execute()
    data = response.data
    
    if not data:
        print("[INFO] No records found in 'clustering' table.")
        return

    print(f"[INFO] Found {len(data)} records. Starting remapping...")

    # Mapping: Old -> New
    # Cluster 1: Safest -> 0
    # Cluster 0: Moderately Safe -> 1
    # Cluster 3: Caution advised -> 2
    # Cluster 2: High Risk -> 3
    # Cluster 4: Extreme danger -> 4
    
    mapping = {
        1: 0,
        0: 1,
        3: 2,
        2: 3,
        4: 4
    }
    
    updated_records = []
    
    for row in data:
        old_score = row.get("clustering_score")
        
        if old_score in mapping:
            new_score = mapping[old_score]
            
            # Only update if the score actually changes (though 4->4 is same, we might want to skip)
            # But for simplicity and ensuring consistency, we can just update all.
            # Optimization: Skip if old == new? 
            # 4->4 is same. 
            # If we run this script TWICE, 0 (was 1) -> 1. 
            # This is DANGEROUS if run multiple times.
            # I will add a safety check or just warn the user. 
            # Since I cannot easily know if it was already run without a flag, I will proceed with the mapping.
            # Ideally, we'd have a migration version, but this is a one-off script.
            
            row["clustering_score"] = new_score
            updated_records.append(row)
        else:
            print(f"[WARN] Score {old_score} for {row.get('iso3')} not in mapping. Skipping.")

    if updated_records:
        print(f"[INFO] Updating {len(updated_records)} records...")
        # Upsert in batches to be safe, though 200 rows is small enough for one go usually.
        # Supabase python client handles list upserts.
        
        try:
            data = supabase.table("clustering").upsert(updated_records).execute()
            print("[INFO] Successfully updated clustering scores.")
        except Exception as e:
            print(f"[ERROR] Failed to upsert: {e}")
    else:
        print("[INFO] No records to update.")

if __name__ == "__main__":
    main()

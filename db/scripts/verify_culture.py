import os
import json
from supabase import create_client
from dotenv import load_dotenv

load_dotenv(dotenv_path="/Users/sanjeevkamath/Documents/Projects/SafeTrip IQ/SafeTrip-IQ/.env")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("ANON_KEY")

def main():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    print("Fetching culture data for Afghanistan (AFG)...")
    response = supabase.table("culture").select("*").eq("iso3", "AFG").execute()
    
    if not response.data:
        print("No data found.")
        return

    row = response.data[0]
    
    print("\n--- Data from DB ---")
    for key, value in row.items():
        print(f"{key}: {value} (Type: {type(value).__name__})")

    print("\n--- Frontend Usage Simulation ---")
    # Simulate what frontend needs to do
    try:
        cities = json.loads(row['cities'])
        print(f"Cities (parsed): {cities} (Type: {type(cities).__name__})")
        print("✅ JSON parsing successful. Frontend can iterate over this array.")
    except Exception as e:
        print(f"❌ JSON parsing failed: {e}")

if __name__ == "__main__":
    main()

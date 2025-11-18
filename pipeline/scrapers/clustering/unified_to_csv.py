# Convert the Unified data json files into csv files for easier processing
from pathlib import Path
import pandas as pd

def main():
    # Correctly locate files relative to the project root.
    # Assuming this script is run from the project root.
    project_root = Path(__file__).resolve().parents[2]
    input_path = project_root / "unified_data/unified_travel_data.json"
    output_path = project_root / "clustering/data/unified_cleaned.csv"

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load JSON into a pandas DataFrame
    df = pd.read_json(input_path)

    # Fields to keep
    fields_to_keep = [
        "iso2",
        "gpi_score",
        "ppi_score",
        "numbeo_safety_index",
        "gti_score",
        "numbeo_crime_index",
    ]
    
    # Select the desired columns and drop rows where ALL of these columns are missing
    df_cleaned = df[fields_to_keep].dropna(how='all', subset=fields_to_keep[1:])

    # Write to CSV, excluding the pandas index
    df_cleaned.to_csv(output_path, index=False, encoding="utf-8")

    print(f"✅ CSV successfully written to: {output_path}")

if __name__ == "__main__":
    main()

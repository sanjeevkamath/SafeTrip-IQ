''' Politial Violence Events Excel to JSON Converter'''
import pandas as pd
from pathlib import Path
import sys
import json


def convert_excel_to_json(input_excel: Path, output_json: Path) -> None:
    """Reads an Excel file with columns [country, year, events],
    cleans it, and writes a JSON file."""

    if not input_excel.exists():
        raise FileNotFoundError(f"Input Excel not found: {input_excel}")

    output_json.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_excel(input_excel)

    df.columns = [col.strip().lower() for col in df.columns]

    expected_cols = {"country", "year", "events"}
    if not expected_cols.issubset(set(df.columns)):
        raise ValueError(
            f"Input file must contain columns: {expected_cols}, but has {set(df.columns)}"
        )

    df = df[["country", "year", "events"]].dropna()

    df["country"] = df["country"].astype(str).str.strip()

    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["events"] = pd.to_numeric(df["events"], errors="coerce").astype("Int64")

    df = df.dropna(subset=["year", "events"])

    with output_json.open("w", encoding="utf-8") as f:
        json.dump(df.to_dict(orient="records"), f, ensure_ascii=False, indent=2)

    print(f"Wrote cleaned JSON to: {output_json}")


def main(argv):
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent

    default_input = project_root / "raw_datasets" / "number_of_political_violence_events_by_country-year_as-of-26Sep2025.xlsx"
    default_output = project_root / "cleaned_data" / "events.json"

    if len(argv) >= 3:
        input_path = Path(argv[1])
        output_path = Path(argv[2])
    elif len(argv) == 2:
        input_path = Path(argv[1])
        output_path = default_output
    else:
        input_path = default_input
        output_path = default_output

    try:
        convert_excel_to_json(input_path, output_path)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv)
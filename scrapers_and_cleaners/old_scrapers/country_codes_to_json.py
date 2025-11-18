import csv
import json
import sys
from pathlib import Path

#!/usr/bin/env python3
"""
Script: country_codes_to_json.py
Reads raw_datasets/country_codes.csv and writes cleaned_data/country_codes.json
"""


def convert_csv_to_json(input_csv: Path, output_json: Path) -> None:
    if not input_csv.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_csv}")

    output_json.parent.mkdir(parents=True, exist_ok=True)

    # Map certain headers to desired metadata keys
    def map_header(header: str) -> str:
        if header is None:
            return header
        h = header.strip()
        hl = h.lower()
        # map 'code' -> 'country code'
        if hl == "code" or "code" in hl:
            return "Country code"
        # map description/name -> 'Country name' (capital C)
        if "desc" in hl or hl == "name" or "name" in hl:
            return "Country name"
        return h

    rows = []
    with input_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        for raw in reader:
            item = {}
            for key in fieldnames:
                out_key = map_header(key)
                val = raw.get(key)
                if val is None:
                    item[out_key] = None
                    continue
                v = val.strip()
                # convert pure integers to int (preserve other formats as strings)
                if v.isdigit():
                    item[out_key] = int(v)
                else:
                    item[out_key] = v
            rows.append(item)

    with output_json.open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

def main(argv):
    # Determine project root relative to this script:
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent

    default_input = project_root / "raw_datasets" / "country_codes.csv"
    default_output = project_root / "cleaned_data" / "country_codes.json"

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
        convert_csv_to_json(input_path, output_path)
        print(f"Wrote JSON to: {output_path}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main(sys.argv)
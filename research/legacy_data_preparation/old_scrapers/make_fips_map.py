# make_fips_map.py
from pathlib import Path
import json, re, pandas as pd
from utils_norm import read_json_auto, snake_cols, norm_string

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RAW  = ROOT / "cleaned_data"
WORK = ROOT / "unified_data"
WORK.mkdir(parents=True, exist_ok=True)
OUT_PATH = WORK / "fips_to_name.json"

def extract_from_text(text: str):
    if not isinstance(text, str): return None
    t = norm_string(text)
    m = re.search(r"(?:in|to)\s+([A-Z][A-Za-zÀ-ÖØ-öø-ÿ'&\-\s\.]+?)(?:\s+due|\s+because|\.|,|;|:|\s+are|\s+do|\s+for)", t)
    return m.group(1).strip(" .,\n") if m else None

def main():
    adv = read_json_auto(RAW / "travel_advisory.json")
    adv = snake_cols(adv)
    if "country_id" not in adv.columns:
        raise SystemExit("travel_advisory.json needs 'country_id'")

    mapping = {}
    if OUT_PATH.exists():
        mapping = json.loads(OUT_PATH.read_text(encoding="utf-8"))

    text_col = "country_advisory_text" if "country_advisory_text" in adv.columns else None
    if text_col:
        for _, row in adv.iterrows():
            code = str(row["country_id"]).strip()
            if code in mapping: continue
            guess = extract_from_text(row[text_col])
            if guess: mapping[code] = guess

    # high-value corrections
    mapping.update({
        "MA": "Madagascar",   # not Morocco in FIPS
        "KS": "South Korea",
        "RM": "Marshall Islands",
        "AY": "Antarctica",
        # add more as you spot them (CE->Sri Lanka, BU->Bulgaria, EK->Equatorial Guinea, …)
        "CE": "Sri Lanka",
        "BU": "Bulgaria",
        "EK": "Equatorial Guinea",
    })

    OUT_PATH.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] wrote {OUT_PATH} with {len(mapping)} entries. Review & tweak if needed.")

if __name__ == "__main__":
    main()

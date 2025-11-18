# -*- coding: utf-8 -*-
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd

from utils_norm import (
    read_json_auto, snake_cols, canon_country, coerce_numeric, norm_string
)

# at the top of each script
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                          # <- repo root (SafeTrip-IQ/)
RAW  = ROOT / "cleaned_data"                # <- INPUTS live here
WORK = ROOT / "unified_data"                # <- keep fips map here
OUT  = ROOT / "unified_data"                # <- OUTPUT unified JSON here
OUT.mkdir(parents=True, exist_ok=True)
WORK.mkdir(parents=True, exist_ok=True)

def load_dim_countries():
    codes = read_json_auto(RAW / "country_codes.json")
    codes = snake_cols(codes)
    # Expect something like ["Country code","Country name"] originally
    # Create standardized columns
    # Try to find iso2 and name
    if "country_code" in codes.columns:
        iso2 = codes["country_code"]
    elif "country code" in codes.columns:
        iso2 = codes["country code"]
    elif "countrycode" in codes.columns:
        iso2 = codes["countrycode"]
    elif "country_code" not in codes.columns and "country name" in codes.columns:
        # fallback: assume first column is code
        iso2 = codes.iloc[:, 0]
    else:
        iso2 = codes.get("country code", codes.get("country_code", codes.iloc[:,0]))

    if "country_name" in codes.columns:
        name = codes["country_name"]
    elif "country name" in codes.columns:
        name = codes["country name"]
    else:
        # fallback: second column
        name = codes.iloc[:, 1]

    dim = pd.DataFrame({"iso2": iso2.astype(str).str.strip(),
                        "country_name": name.astype(str).map(norm_string)})
    dim["country_name_norm"] = canon_country(dim["country_name"])
    dim = dim.drop_duplicates("country_name_norm")
    return dim

def load_fips_map() -> dict:
    f = WORK / "fips_to_name.json"
    if not f.exists():
        print("[WARN] fips_to_name.json not found—run make_fips_map.py first for best results.")
        return {}
    return json.loads(f.read_text(encoding="utf-8"))

def norm_with_country(df: pd.DataFrame, name_col_guess=("country_name","country","name")) -> pd.DataFrame:
    from utils_norm import snake_cols, norm_string, canon_country
    df = snake_cols(df)
    # ensure a country_name column exists
    if "country_name" not in df.columns:
        for c in name_col_guess:
            if c in df.columns:
                df["country_name"] = df[c]
                break
    if "country_name" not in df.columns:
        # still nothing; create empty so downstream doesn’t crash
        df["country_name"] = None
    # normalize + canonicalize
    df["country_name"] = df["country_name"].apply(norm_string)
    df["country_name_norm"] = canon_country(df["country_name"])
    return df


def main():
    # Load dim and FIPS map
    dim = load_dim_countries()
    fips_map = load_fips_map()

    # --- Load sources
    # Advisories (FIPS-coded)
    adv = read_json_auto(RAW / "travel_advisory.json")
    adv = snake_cols(adv)
    # Backfill country_name from FIPS
    if "country_id" in adv.columns:
        adv["country_id"] = adv["country_id"].astype(str).str.strip()
        adv["country_name"] = adv.get("country_name")
        adv["country_name"] = adv["country_name"].where(adv["country_name"].notna(),
                                                        adv["country_id"].map(fips_map))
    adv = norm_with_country(adv)

    # GPI / GTI
    gpi = norm_with_country(read_json_auto(RAW / "gpi.json"))
    if "score" in gpi.columns and "gpi_score" not in gpi.columns:
        gpi = gpi.rename(columns={"score":"gpi_score"})
    gti = norm_with_country(read_json_auto(RAW / "gti.json"))
    if "score" in gti.columns and "gti_score" not in gti.columns:
        gti = gti.rename(columns={"score":"gti_score"})

    # Events
    events = norm_with_country(read_json_auto(RAW / "events.json"), name_col_guess=("country","country_name","name"))
    events = coerce_numeric(events, ["year","events"])
    if "year" in events.columns:
        events = (events.sort_values("year", ascending=False)
                        .drop_duplicates("country_name_norm")
                        .rename(columns={"year":"events_year"}))

    # Optional datasets (merge if present)
    def load_optional(fname):
        p = RAW / fname
        if p.exists():
            df = norm_with_country(read_json_auto(p))
            return df
        return None

    numbeo = load_optional("numbeo_clean.json")
    ppi    = load_optional("ppi.json")

    # --- Merge pipeline
    # start from dim; left-join facts so we keep “known” countries
    out = dim.copy()

    # advisories: choose reasonable column names
    level_col = None
    for c in ["country_advisory","advisory_level","advisory"]:
        if c in adv.columns: level_col = c; break
    text_col = None
    for c in ["country_advisory_text","advisory_text","advisory_details"]:
        if c in adv.columns: text_col = c; break

    cols = ["country_name_norm"]
    if level_col: cols.append(level_col)
    if text_col:  cols.append(text_col)
    out = out.merge(adv[cols], on="country_name_norm", how="left")

    # gpi/gti
    if "gpi_score" in gpi.columns:
        out = out.merge(gpi[["country_name_norm","gpi_score"]], on="country_name_norm", how="left")
    if "gti_score" in gti.columns:
        out = out.merge(gti[["country_name_norm","gti_score"]], on="country_name_norm", how="left")

    # events
    to_keep = ["country_name_norm"]
    for c in ["events","events_year"]:
        if c in events.columns: to_keep.append(c)
    out = out.merge(events[to_keep], on="country_name_norm", how="left")

    # numbeo (prefix)
    if numbeo is not None:
        num_cols = [c for c in numbeo.columns if c not in ("country_name_norm","country_name")]
        numbeo_pref = numbeo[["country_name_norm"] + num_cols]
        numbeo_pref = numbeo_pref.add_prefix("numbeo_")
        numbeo_pref = numbeo_pref.rename(columns={"numbeo_country_name_norm":"country_name_norm"})
        out = out.merge(numbeo_pref, on="country_name_norm", how="left")

    # ppi (prefix)
    if ppi is not None:
        ppi_cols = [c for c in ppi.columns if c not in ("country_name_norm","country_name")]
        ppi_pref = ppi[["country_name_norm"] + ppi_cols]
        ppi_pref = ppi_pref.add_prefix("ppi_")
        ppi_pref = ppi_pref.rename(columns={"ppi_country_name_norm":"country_name_norm"})
        out = out.merge(ppi_pref, on="country_name_norm", how="left")

    # final tidy columns
    out = coerce_numeric(out, ["gpi_score","gti_score","events","events_year"])
    out = out.rename(columns={
        level_col: "advisory_level" if level_col else "advisory_level",
        text_col:  "advisory_text"  if text_col  else "advisory_text",
    })

    # nice display name first
    out = out[[
        "iso2", "country_name", "country_name_norm",
        "advisory_level", "advisory_text",
        "gpi_score", "gti_score", "events", "events_year",
        *[c for c in out.columns if c.startswith("numbeo_")],
        *[c for c in out.columns if c.startswith("ppi_")],
    ]]

    # BERT input
    def mk_bert(row):
        parts = [f"Country: {row['country_name']}."]
        if pd.notna(row.get("advisory_level")):
            parts.append(f"Travel Advisory: {row['advisory_level']}.")
        if pd.notna(row.get("gpi_score")):
            parts.append(f"The Global Peace Index score is {float(row['gpi_score']):.3f}.")
        if pd.notna(row.get("gti_score")):
            parts.append(f"The Global Terrorism Index score is {float(row['gti_score']):.3f}.")
        if pd.notna(row.get("events")) and pd.notna(row.get("events_year")):
            parts.append(f"In {int(row['events_year'])}, there were {int(row['events'])} political violence events.")
        if pd.notna(row.get("advisory_text")):
            parts.append(f"Advisory Details: {row['advisory_text']}")
        return " ".join(parts)

    out["bert_input_text"] = out.apply(mk_bert, axis=1)

    # write
    out = out.where(pd.notna(out), None)
    (OUT / "unified_travel_data.json").write_text(
        json.dumps(out.to_dict(orient="records"), ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"[DONE] Wrote {OUT/'unified_travel_data.json'} (rows={len(out)})")

if __name__ == "__main__":
    main()

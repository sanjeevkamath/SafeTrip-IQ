import unicodedata, re, pandas as pd

ALIASES = {
    "türkiye":"Turkey", "turkiye":"Turkey", "t\ufffdrkiye":"Turkey",
    "czech republic":"Czechia",
    "cote d' ivoire":"Cote d'Ivoire", "côte d'ivoire":"Cote d'Ivoire",
    "kyrgyz republic":"Kyrgyzstan",
    "east timor":"Timor-Leste",
    "bahamas":"The Bahamas",
    "russian federation":"Russia",
    "lao pdr":"Laos",
    "united states of america":"United States",
}

def norm_string(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    # Convert non-strings to string safely
    s = str(x)
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("’","'").replace("`","'").replace("–","-").replace("—","-")
    s = re.sub(r"\s+", " ", s.strip())
    return s

def canon_country(series: pd.Series) -> pd.Series:
    # Normalize each element safely; allow None
    s = series.apply(norm_string)
    # lower() only on non-null strings
    lower = s.where(s.isna(), s.str.lower())
    mapped = lower.map(ALIASES).fillna(s)   # map known aliases; keep original otherwise
    return mapped

def snake_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = (df.columns.astype(str).str.strip()
                  .str.replace(r"\s+","_",regex=True)
                  .str.replace(r"[^\w_]","",regex=True)
                  .str.lower())
    return df

def read_json_auto(path):
    import pandas as pd
    try:
        return pd.read_json(path)
    except ValueError:
        return pd.read_json(path, lines=True)

def coerce_numeric(df: pd.DataFrame, cols):
    df = df.copy()
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

"""Preserved advisory parsing/cleaning; no fetching or configuration on import."""
import csv
import html
import re
import xml.etree.ElementTree as ET
from typing import Dict, Optional, List
from .country_names import COUNTRY_NAMES

CLEANING_VERSION = "advisory-no-country-labels-v4"


def _name_pattern(names):
    # Longest first prevents a shorter alias from leaving part of a full name.
    variants = {name.replace("’", "'") for name in names if name}
    return re.compile(r"(?<!\w)(?:" + "|".join(
        re.escape(name).replace(r"\ ", r"\s+")
        for name in sorted(variants, key=len, reverse=True)) + r")(?!\w)", re.IGNORECASE)


COUNTRY_NAME_PATTERN = _name_pattern(COUNTRY_NAMES)
LEVEL_PATTERN = re.compile(
    r"\b(?:advisory\s+)?level\s*[-:]?\s*(?:[1-4]|IV|III|II|I|one|two|three|four)\b",
    re.IGNORECASE,
)
RECOMMENDATION_PATTERN = re.compile(
    r"\b(?:do\s+not\s+travel|reconsider\s+travel|"
    r"(?:should\s+not|not\s+to)\s+travel|"
    r"avoid\s+(?:all|non[\s-]?essential)\s+travel|travel\s+is\s+not\s+recommended|"
    r"exercise\s+(?:increased\s+caution|normal\s+precautions?))\b"
    r"(?:\s+(?:to|in)\b)?", re.IGNORECASE,
)

FEED_URL = "https://travel.state.gov/_res/rss/TAsTWs.xml"

# ---------- US COUNTRY CODE (FIPS-10/Travel.State) TO ISO3 ---------- #
# Source: Travel.State.gov feed countryCode values mapped to ISO 3166-1 alpha-3
US_CODE_TO_ISO3 = {
    "A1": "BES",  # Saba (Caribbean Netherlands)
    "A2": "GUF",  # French Guiana
    "AA": "ABW",
    "AC": "ATG",
    "AF": "AFG",
    "AG": "DZA",
    "AJ": "AZE",
    "AL": "ALB",
    "AM": "ARM",
    "AN": "AND",
    "AO": "AGO",
    "AR": "ARG",
    "AS": "AUS",
    "AU": "AUT",
    "AV": "AIA",
    "AY": "ATA",
    "BA": "BHR",
    "BB": "BRB",
    "BC": "BWA",
    "BD": "BMU",
    "BE": "BEL",
    "BF": "BHS",
    "BG": "BGD",
    "BH": "BLZ",
    "BK": "BIH",
    "BL": "BOL",
    "BM": "MMR",
    "BN": "BEN",
    "BO": "BLR",
    "BP": "SLB",
    "BR": "BRA",
    "BT": "BTN",
    "BU": "BGR",
    "BX": "BRN",
    "BY": "BDI",
    "CA": "CAN",
    "CB": "KHM",
    "CD": "TCD",
    "CE": "LKA",
    "CF": "COG",
    "CG": "COD",
    "CH": "CHN",
    "CI": "CHL",
    "CM": "CMR",
    "CN": "COM",
    "CO": "COL",
    "CS": "CRI",
    "CT": "CAF",
    "CU": "CUB",
    "CV": "CPV",
    "CY": "CYP",
    "DJ": "DJI",
    "DO": "DMA",
    "DR": "DOM",
    "EC": "ECU",
    "EG": "EGY",
    "EI": "IRL",
    "EK": "GNQ",
    "EN": "EST",
    "ER": "ERI",
    "ES": "SLV",
    "ET": "ETH",
    "FI": "FIN",
    "FJ": "FJI",
    "FP": "PYF",
    "FR": "FRA",
    "GA": "GMB",
    "GB": "GAB",
    "GG": "GEO",
    "GH": "GHA",
    "GJ": "GRD",
    "GW": "GNB",
    "GL": "GRL",
    "GM": "DEU",
    "GR": "GRC",
    "GT": "GTM",
    "GV": "GIN",
    "GY": "GUY",
    "HA": "HTI",
    "HO": "HND",
    "HR": "HRV",
    "HU": "HUN",
    "IC": "ISL",
    "ID": "IDN",
    "IN": "IND",
    "IR": "IRN",
    "IT": "ITA",
    "IV": "CIV",
    "IZ": "IRQ",
    "JA": "JPN",
    "JM": "JAM",
    "JO": "JOR",
    "KE": "KEN",
    "KG": "KGZ",
    "KN": "PRK",
    "KR": "KIR",
    "KS": "KOR",
    "KU": "KWT",
    "KV": "XKX",
    "KZ": "KAZ",
    "LA": "LAO",
    "LE": "LBN",
    "LG": "LVA",
    "LH": "LTU",
    "LI": "LBR",
    "LO": "SVK",
    "LS": "LIE",
    "LT": "LSO",
    "LU": "LUX",
    "LY": "LBY",
    "MA": "MDG",
    "MD": "MDA",
    "MG": "MNG",
    "MH": "MSR",
    "MI": "MWI",
    "MP": "MUS",
    "MJ": "MNE",
    "MK": "MKD",
    "ML": "MLI",
    "MO": "MAR",
    "MR": "MRT",
    "MT": "MLT",
    "MU": "OMN",
    "MV": "MDV",
    "MX": "MEX",
    "MY": "MYS",
    "MZ": "MOZ",
    "NC": "NCL",
    "NG": "NER",
    "NH": "VUT",
    "NI": "NGA",
    "NN": "SXM",
    "NO": "NOR",
    "NP": "NPL",
    "NR": "NRU",
    "NS": "SUR",
    "NU": "NIC",
    "NZ": "NZL",
    "OD": "SSD",
    "PA": "PRY",
    "PE": "PER",
    "PK": "PAK",
    "PL": "POL",
    "PM": "PAN",
    "PO": "PRT",
    "PP": "PNG",
    "PS": "PLW",
    "QA": "QAT",
    "RI": "SRB",
    "RM": "MHL",
    "RO": "ROU",
    "RP": "PHL",
    "RS": "RUS",
    "RW": "RWA",
    "SA": "SAU",
    "SC": "KNA",
    "SE": "SYC",
    "SF": "ZAF",
    "SG": "SEN",
    "SI": "SVN",
    "SL": "SLE",
    "SN": "SGP",
    "SO": "SOM",
    "SP": "ESP",
    "SR": "CHE",
    "ST": "LCA",
    "SU": "SDN",
    "SW": "SWE",
    "SY": "SYR",
    "TD": "TTO",
    "TH": "THA",
    "TI": "TJK",
    "TK": "TCA",
    "TN": "TON",
    "TT": "TLS",
    "TV": "TUV",
    "TO": "TGO",
    "TP": "STP",
    "TS": "TUN",
    "TU": "TUR",
    "TX": "TKM",
    "TZ": "TZA",
    "UC": "CUW",
    "UG": "UGA",
    "UK": "GBR",
    "UP": "UKR",
    "UV": "BFA",
    "UY": "URY",
    "UZ": "UZB",
    "VC": "VCT",
    "VE": "VEN",
    "VI": "VGB",
    "VM": "VNM",
    "WA": "NAM",
    "WS": "WSM",
    "WZ": "SWZ",
    "TW": "TWN",
    "YM": "YEM",
    "ZA": "ZMB",
    "ZI": "ZWE",
    "None": "USA",
}


# ---------- ISO3 LOOKUP FROM CSV ---------- #



# -------------------------------------------------------------------
# ISO3 LOOKUP VIA CSV
# -------------------------------------------------------------------

def normalize_country_name(name: str) -> str:
    """
    Normalize a country name for matching:
      - lowercase
      - collapse weird apostrophes
      - strip spaces
    """
    return (
        name.replace("’", "'")
            .replace("\u00a0", " ")  # non-breaking space
            .strip()
            .lower()
    )


def load_iso3_mapping(csv_path: str) -> Dict[str, str]:
    """
    Build mapping: normalized country name -> ISO3 code.
    """
    mapping = {}
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("English short name lower case") or "").strip()
            iso3 = (row.get("Alpha-3 code") or "").strip().upper()

            if not name or not iso3:
                continue

            key = normalize_country_name(name)
            mapping[key] = iso3

    return mapping


# Additional fallback spellings not in the CSV
ALIAS_NAME_TO_CANONICAL = {
    "cote d'ivoire": "côte d'ivoire",
    "cote d’ivoire": "côte d'ivoire",
    "myanmar (burma)": "myanmar",
    "burma": "myanmar",
    "syrian arab republic": "syria",
    "russian federation": "russia",
    "cabo verde": "cape verde",
}


def lookup_iso3(country_name: Optional[str], iso_map: Dict[str, str]) -> Optional[str]:
    """Map country_name → ISO3 using CSV and aliases."""
    if not country_name:
        return None

    key = normalize_country_name(country_name)

    # Direct match
    if key in iso_map:
        return iso_map[key]

    # Alias fallback
    if key in ALIAS_NAME_TO_CANONICAL:
        canon = normalize_country_name(ALIAS_NAME_TO_CANONICAL[key])
        if canon in iso_map:
            return iso_map[canon]

    print(f"[WARN] No ISO3 found for country: '{country_name}'")
    return None


# -------------------------------------------------------------------
# RSS FETCH + PARSE
# -------------------------------------------------------------------

TITLE_COUNTRY_RE = re.compile(r"^(?P<country>.+?)\s+[–-]\s+Level\s*\d")


def fetch_feed_bytes() -> bytes:
    import requests
    from time import sleep
    for attempt in range(3):
        response = None
        try:
            response = requests.get(FEED_URL, timeout=(5, 20))
            if response.status_code in {429, 500, 502, 503, 504} and attempt < 2:
                response.close()
                sleep(2 ** attempt)
                continue
            response.raise_for_status()
            return response.content
        except requests.exceptions.SSLError:
            raise  # Certificate/configuration errors need correction, not retries.
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            if attempt == 2:
                raise
            sleep(2 ** attempt)
        finally:
            if response is not None:
                response.close()
    raise RuntimeError("Advisory fetch attempts exhausted.")


def fetch_feed_xml() -> str:
    return fetch_feed_bytes().decode("utf-8-sig")


def clean_html_to_text(raw_html: Optional[str], country_name: Optional[str] = None) -> str:
    if not raw_html:
        return ""
    # strip tags
    text = re.sub(r"<[^>]+>", " ", html.unescape(raw_html))
    text = text.replace("’", "'")
    # collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # --- Boilerplate Removal ---
    # Remove "Country Summary:" prefix
    text = re.sub(r"^Country Summary:\s*", "", text, flags=re.IGNORECASE)

    # Remove "Read the entire Travel Advisory."
    text = re.sub(r"Read the entire Travel Advisory\.?", "", text, flags=re.IGNORECASE)

    # Remove "If you decide to travel to..." and everything after it (usually generic advice)
    # But be careful, sometimes it's "If you decide to travel to [Region]..." which might be specific.
    # The generic one is usually "If you decide to travel to [Country]:" followed by "Enroll in STEP..."
    # Let's target the specific generic phrases instead to be safe.

    boilerplate_patterns = [
        r"Enroll in the Smart Traveler Enrollment Program \(STEP\) to receive messages and Alerts.*",
        r"Review the Country Security Report for.*",
        r"Prepare a plan for emergency situations.*",
        r"Review the Traveler's Checklist.*",
        r"Visit the CDC page for the latest Travel Health Information.*",
        r"We highly recommend that you buy insurance before you travel.*",
        r"Check with your travel insurance provider about evacuation assistance.*",
        r"Visit our website for Travel to High-Risk Areas.*",
    ]

    for pattern in boilerplate_patterns:
        # Remove only the matched sentence, not all later risk information.
        pattern = pattern.removesuffix(".*") + r"[^.!?]*(?:[.!?]|$)"
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)

    # Some archived body text lost whitespace around HTML emphasis tags.
    text = re.sub(r"\b(level\s*[1-4])(?=[a-z])", r"\1 ", text, flags=re.IGNORECASE)
    text = LEVEL_PATTERN.sub(" ", text)
    text = RECOMMENDATION_PATTERN.sub(" ", text)
    if country_name:
        text = _name_pattern([country_name]).sub(" ", text)
    text = COUNTRY_NAME_PATTERN.sub(" ", text)

    # Clean up any double spaces created
    text = re.sub(r"\s+", " ", text).lstrip(" .,:;–—-").rstrip()
    if not re.search(r"\w", text):
        return ""

    return text.lower()


def parse_feed(xml_text: str) -> List[dict]:
    """
    Return list of:
      {
        country_name,
        country_code,
        pub_date_raw,
        description_raw_html,
        description_text
      }
    """
    root = ET.fromstring(xml_text)
    channel = root.find("channel")
    if channel is None:
        raise RuntimeError("RSS feed missing <channel>")

    records = []

    for item in channel.findall("item"):
        title = (item.findtext("title") or "").strip()
        pub_date_raw = (item.findtext("pubDate") or "").strip()

        # Extract country_name from title
        m = TITLE_COUNTRY_RE.match(title)
        country_name = m.group("country").strip() if m else None

        # Get Country-Tag state dept code
        country_code = None
        for cat in item.findall("category"):
            if cat.get("domain") == "Country-Tag":
                country_code = (cat.text or "").strip()

        # Description
        desc_el = item.find("description")
        raw_html = desc_el.text if desc_el is not None else ""
        description_text = clean_html_to_text(raw_html, country_name)

        records.append(
            {
                "country_name": country_name,
                "country_code": country_code,        # keep original 2-letter tag
                "pub_date_raw": pub_date_raw,
                "description_raw_html": raw_html,
                "description_text": description_text,
            }
        )

    return records




def map_records(xml_text, iso_map=None):
    """Resolve country identity and retain the newest dated advisory per ISO3.

    Fail on unmapped records instead of silently publishing an incomplete feed.
    An optional CSV can supply the historical country-name fallback.
    """
    from .countries import resolve_iso3
    from email.utils import parsedate_to_datetime
    from datetime import datetime, timezone
    def source_date(value):
        try:
            date = parsedate_to_datetime(value)
            if date.tzinfo is None:
                raise ValueError("Date lacks timezone.")
            return date
        except (ValueError, TypeError):
            # Official RSS also uses calendar dates without a time or timezone.
            # Compare these at UTC midnight, preserving the original source string.
            return datetime.strptime(value, "%a, %d %b %Y").replace(tzinfo=timezone.utc)
    unique = {}
    for record in parse_feed(xml_text):
        iso3 = resolve_iso3(record["country_name"], record["country_code"], iso_map)
        record["iso3"] = iso3
        if iso3 in unique:
            previous = unique[iso3]
            if previous["description_raw_html"] != record["description_raw_html"]:
                try:
                    old_date = source_date(previous["pub_date_raw"])
                    new_date = source_date(record["pub_date_raw"])
                except (ValueError, TypeError) as error:
                    raise ValueError("Conflicting duplicate advisories require valid dated source records.") from error
                if old_date == new_date:
                    raise ValueError("Conflicting duplicate advisories have identical publication dates.")
                if new_date < old_date:
                    continue
        unique[iso3] = record
    if not unique:
        raise ValueError("No advisories found; refusing an empty refresh.")
    return list(unique.values())

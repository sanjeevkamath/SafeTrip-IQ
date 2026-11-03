"""Resolve advisory country identity with legacy tags and a verified name cross-check."""
import unicodedata
from .country_codes import NAME_TO_ISO3, ISO2_TO_ISO3

ALIASES = {
    "kosovo": "XKX", "burma": "MMR", "myanmar (burma)": "MMR", "laos": "LAO",
    "russia": "RUS", "iran": "IRN", "syria": "SYR", "bolivia": "BOL", "venezuela": "VEN",
    "south korea": "KOR", "north korea": "PRK", "cote d'ivoire": "CIV", "micronesia": "FSM",
    "federated states of micronesia": "FSM", "french west indies": "GLP", "macau": "MAC",
    "brunei": "BRN", "turkey": "TUR", "the bahamas": "BHS", "the gambia": "GMB",
    "congo, democratic republic of the": "COD", "democratic republic of the congo": "COD",
    "congo, republic of the": "COG", "republic of the congo": "COG", "west bank and gaza": "PSE",
    "kingdom of denmark": "DNK", "czech republic": "CZE", "czechia": "CZE",
    "sint maarten": "SXM", "british virgin islands": "VGB", "cabo verde": "CPV",
    "french saint martin": "MAF", "saint kitts and nevis": "KNA",
    "west bank": "PSE", "gaza": "PSE", "saba": "BES", "bonaire": "BES",
}
MANUAL_NAMES = {"czechia", "federated states of micronesia", "macau", "kingdom of denmark", "french west indies", "west bank", "gaza", "saba", "bonaire"}
VERIFIED_TAG_ALIASES = {"KH": "KHM"}  # Current feed also retains the legacy CB tag for Cambodia.


def normalized_name(name):
    return "".join(ch for ch in unicodedata.normalize("NFKD", (name or "").replace("’", "'"))
                   if not unicodedata.combining(ch)).strip().lower()


def resolve_iso3(country_name, country_code, iso_map=None, *, allow_regions=False):
    from .advisories import US_CODE_TO_ISO3, normalize_country_name
    key = normalized_name(country_name)
    if key in {"west bank", "gaza", "saba", "bonaire"} and not allow_regions:
        raise ValueError("Territory advisories require an explicit region aggregation policy before country publication.")
    named = ALIASES.get(key) or NAME_TO_ISO3.get(key)
    if not named and iso_map:
        named = iso_map.get(normalize_country_name(country_name or ""))
    if key in MANUAL_NAMES:
        return ALIASES[key]
    tagged = US_CODE_TO_ISO3.get(country_code) or VERIFIED_TAG_ALIASES.get(country_code)
    if tagged and named and tagged != named:
        if ISO2_TO_ISO3.get(country_code) == named:
            return named  # A mixed-format feed is unambiguous only with the name cross-check.
        raise ValueError("Advisory country tag conflicts with its named country; review mapping before publication.")
    if tagged or named:
        return tagged or named
    raise ValueError("An advisory could not be mapped to ISO3; review aliases or supply --iso-csv.")

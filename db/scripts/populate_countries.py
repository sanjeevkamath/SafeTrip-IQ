import pycountry
import pycountry_convert as pc
if __package__:
    from .supabase_writer import get_writer_client
else:
    from supabase_writer import get_writer_client


# -------------------------------------------------
# Load environment variables
# -------------------------------------------------
supabase = get_writer_client()


# -------------------------------------------------
# Continent mapping (ISO3 -> Continent)
# -------------------------------------------------
continent_map = {
    "AF": "Africa",
    "AS": "Asia",
    "EU": "Europe",
    "NA": "North America",
    "SA": "South America",
    "OC": "Oceania",
    "AN": "Antarctica"
}

def country_to_continent(alpha2):
    country_continent_code = pc.country_alpha2_to_continent_code(alpha2)
    country_continent_name = pc.convert_continent_code_to_continent_name(country_continent_code)
    return country_continent_name



# -------------------------------------------------
# Function to insert a single country
# -------------------------------------------------
def insert_country(iso3, iso2):
    try:
        # Get country object
        country = pycountry.countries.get(alpha_3=iso3)

        if not country:
            print(f"❌ No match found for ISO3: {iso3}")
            return

        if not iso2:
            print(f"❌ No ISO2 code found for ISO3: {iso3}")
            return

        # Extract fields
        name = country.name
        alpha2 = iso2
        #continent = continent_map.get(country.region, None)


        # Insert row
        data = {
            "iso2": alpha2,
            "iso3": iso3,
            "name": name,
            "continent": None,
            "flag_url": None
        }

        response = supabase.table("countries").upsert(data).execute()
        print(f"✅ Inserted {iso3} - {name}")

    except Exception as e:
        print(f"❌ Error inserting {iso3}: {e}")


# -------------------------------------------------
# List of ISO3 codes you want to insert
# (Replace with your full list or load from CSV)
# -------------------------------------------------
iso_list = [
    (c.alpha_3, c.alpha_2)
    for c in pycountry.countries
    if getattr(c, "alpha_3", None) and getattr(c, "alpha_2", None)
]



# -------------------------------------------------
# Run insertion
# -------------------------------------------------
for iso3, iso2 in iso_list:
    insert_country(iso3, iso2)

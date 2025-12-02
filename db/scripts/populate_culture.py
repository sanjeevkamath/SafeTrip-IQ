import os
import json
import time
from supabase import create_client
from litellm import completion
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path="/Users/sanjeevkamath/Documents/Projects/SafeTrip IQ/SafeTrip-IQ/.env")

# Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("ANON_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and ANON_KEY must be set in .env")

if not OPENAI_API_KEY:
    # Fallback or error if not set. test.py had it hardcoded or set in env.
    # Assuming it's in env based on test.py usage, but let's be safe.
    # I will assume it is set in the environment or I should set it if missing, 
    # but for a production script it's better to rely on env vars.
    # I'll add a check.
    print("Warning: OPENAI_API_KEY not found in environment variables.")

def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def get_culture_data(country_name):
    """
    Fetches culture data for a specific country using the LLM.
    """
    print(f"Fetching culture data for: {country_name}")
    try:
        response = completion(
            model="openai/gpt-oss-120b", 
            api_base="https://api.ai.it.ufl.edu/v1",
            api_key=OPENAI_API_KEY,
            messages=[
                {
                    "role": "system", 
                    "content": "You are a globally aware travel-safety assistant. Given a specific country, respond ONLY with a valid JSON object containing the following keys: language, greeting, currency, overview, cities, etiquette, religion, dos, donts, popular_foods, cultural_safety_notes. Do not include any markdown formatting. Rules: - greeting: Provide 1 to 2 common greetings. - overview: Provide a concise 2-sentence country overview. - cities: Provide 1–3 major cities that are most visited. - etiquette: Provide 1–2 common etiquette practices for travelers. - religion: Provide 1–2 widely practiced religions. - dos: Provide 2-3 recommended behaviors for travelers. - donts: Provide 2-3 behaviors to avoid.  - popular_foods: Provide 1-2 well-known local foods (names only). - cultural_safety_notes: Provide 1–2 cultural or safety notes useful for travelers. Ensure all field values are short, clear, and suitable for use in a public travel-safety application."
                },
                { 
                    "role": "user", 
                    "content": f"Give me the following data about {country_name}: language, greeting, currency, 2 sentence overview, cities, etiquette, religion, dos, donts, popular foods, cultural_safety_notes"
                }
            ]
        )
        content = response.choices[0].message.content
        # Clean up content if it has markdown code blocks
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        
        data = json.loads(content)
        return data
    except Exception as e:
        print(f"Error fetching/parsing data for {country_name}: {e}")
        return None

def main():
    supabase = get_supabase()
    
    # 1. Fetch all countries
    print("Fetching countries from DB...")
    response = supabase.table("countries").select("iso3, name").execute()
    countries = response.data
    
    if not countries:
        print("No countries found in the database.")
        return

    print(f"Found {len(countries)} countries.")

    # 2. Iterate and populate
    for i, country in enumerate(countries):
        iso3 = country['iso3']
        name = country['name']
        
        # Check if culture data already exists to avoid re-running (optional, but good for restartability)
        # For now, we will overwrite/upsert as per instructions.
        
        print(f"[{i+1}/{len(countries)}] Processing {name} ({iso3})...")
        
        culture_data = get_culture_data(name)
        
        if culture_data:
            # Prepare row for Supabase
            # Note: The table schema has TEXT for list fields, so we json.dumps them.
            # language, greeting, currency, overview are strings.
            # cities, etiquette, religion, dos, donts, food, cultural_safety_notes are lists in JSON, so we dump them.
            
            row = {
                "iso3": iso3,
                "language": culture_data.get("language"),
                "greeting": culture_data.get("greeting"),
                "currency": culture_data.get("currency"),
                "overview": culture_data.get("overview"),
                "cities": json.dumps(culture_data.get("cities", [])),
                "etiquette": json.dumps(culture_data.get("etiquette", [])),
                "religion": json.dumps(culture_data.get("religion", [])),
                "dos": json.dumps(culture_data.get("dos", [])),
                "donts": json.dumps(culture_data.get("donts", [])),
                "food": json.dumps(culture_data.get("popular_foods", [])), # Mapped to 'food' column
                "cultural_safety_notes": json.dumps(culture_data.get("cultural_safety_notes", []))
            }
            
            try:
                supabase.table("culture").upsert(row).execute()
                print(f"Successfully updated culture for {name}.")
            except Exception as e:
                print(f"Error upserting to DB for {name}: {e}")
        
        # Sleep briefly to avoid rate limits if necessary
        time.sleep(1)

if __name__ == "__main__":
    main()

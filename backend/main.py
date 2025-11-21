from fastapi import FastAPI, HTTPException
from supabase_client import supabase

app = FastAPI()

@app.get("/country/{iso3}")
def get_country(iso3: str):
    country = supabase.table("countries").select("*").eq("iso3", iso3).single().execute()
    if not country.data:
        raise HTTPException(404, "Country not found!")

    #score = supabase.table("scores").select("*").eq("iso3", iso3).single().execute()

    #cultures = supabase.table("culture").select("*").eq("iso3", iso3).single().execute()

    #clusterings = supabase.table("clustering").select("*").eq("iso3", iso3).single().execute()

    # Format response
    response = {
        "iso3": iso3,
        "name": country.data["name"],
        "continent": country.data["continent"],
        "flag": country.data["flag_url"]
        #"scores": {
            #"safe_trip_score": score.data["safe_trip_score"] if score.data else None,
            #"bert_score": score.data["bert_score"] if score.data else None,
            #"clustering_score": score.data["clustering_score"] if score.data else None
        #}
            #"culture": cultures.data if cultures.data else None,
            #"clustering_details": clusterings.data if clusterings.data else None
    }
    return response

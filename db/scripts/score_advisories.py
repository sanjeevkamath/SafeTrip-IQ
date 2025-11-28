import os
import torch
import numpy as np
from supabase import create_client
from transformers import BertTokenizerFast, BertForSequenceClassification
from dotenv import load_dotenv

load_dotenv(dotenv_path="/Users/sanjeevkamath/Documents/Projects/SafeTrip IQ/SafeTrip-IQ/.env")

# Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("ANON_KEY")
MODEL_PATH = "results/checkpoint-189"  # Using the latest checkpoint
BATCH_SIZE = 16

def get_supabase():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set.")
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def load_model(model_path):
    print(f"[INFO] Loading model from {model_path}...")
    tokenizer = BertTokenizerFast.from_pretrained("bert-base-uncased") # Tokenizer usually from base or saved with model
    # If the tokenizer was saved with the model, load it from there:
    if os.path.exists(os.path.join(model_path, "tokenizer_config.json")):
        tokenizer = BertTokenizerFast.from_pretrained(model_path)
    
    model = BertForSequenceClassification.from_pretrained(model_path)
    return tokenizer, model

def fetch_advisories(supabase):
    print("[INFO] Fetching travel advisories...")
    # Fetch all advisories. In a real scenario, might want to filter by those not yet scored.
    # For now, we fetch all and upsert.
    response = supabase.table("travel_advisories").select("iso3, description_text").execute()
    return response.data

def score_texts(texts, tokenizer, model, device):
    inputs = tokenizer(texts, truncation=True, padding=True, max_length=256, return_tensors="pt").to(device)
    with torch.no_grad():
        outputs = model(**inputs)
    
    logits = outputs.logits
    # Assuming the model outputs logits for classes. 
    # We need to know how to map logits to a "score".
    # If it's a regression model (num_labels=1), the logit is the score.
    # If it's classification (e.g. 0=Safe, 1=Unsafe), we might want the probability of "Unsafe" or a class index.
    # Based on sentiment.py, it seems to be classification.
    # Let's assume we want the class index as the score for now, or map it.
    # The user schema says 'bert_score integer'.
    
    predictions = torch.argmax(logits, dim=-1).cpu().numpy()
    return predictions

def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[INFO] Using device: {device}")

    supabase = get_supabase()
    tokenizer, model = load_model(MODEL_PATH)
    model.to(device)
    model.eval()

    advisories = fetch_advisories(supabase)
    print(f"[INFO] Found {len(advisories)} advisories.")

    # Fetch valid ISO3s from countries table to avoid FK violation
    print("[INFO] Fetching valid ISO3 codes from countries table...")
    countries_resp = supabase.table("countries").select("iso3").execute()
    valid_iso3s = {item["iso3"] for item in countries_resp.data}
    
    # Filter advisories
    advisories = [a for a in advisories if a["iso3"] in valid_iso3s]
    print(f"[INFO] {len(advisories)} advisories have valid ISO3 codes in 'countries' table.")

    if not advisories:
        print("[INFO] No valid advisories to process.")
        return

    # Process in batches
    for i in range(0, len(advisories), BATCH_SIZE):
        batch = advisories[i : i + BATCH_SIZE]
        texts = [item["description_text"] for item in batch if item["description_text"]]
        iso3s = [item["iso3"] for item in batch if item["description_text"]]
        
        if not texts:
            continue

        scores = score_texts(texts, tokenizer, model, device)

        # Prepare upsert data
        rows_to_upsert = []
        for iso3, text, score in zip(iso3s, texts, scores):
            rows_to_upsert.append({
                "iso3": iso3,
                "cleaned_text": text,
                "bert_score": int(score) # Ensure python int for JSON serialization
            })

        # Upsert to bert_scores
        if rows_to_upsert:
            supabase.table("bert_scores").upsert(rows_to_upsert).execute()
            print(f"[INFO] Upserted batch {i // BATCH_SIZE + 1}")

if __name__ == "__main__":
    main()

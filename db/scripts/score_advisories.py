import os
from pathlib import Path
import torch
from transformers import BertTokenizerFast, BertForSequenceClassification
if __package__:
    from .supabase_writer import get_writer_client
else:
    from supabase_writer import get_writer_client

# Configuration
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = PROJECT_ROOT / "results/checkpoint-189"
BATCH_SIZE = 16

def get_supabase():
    return get_writer_client()

def load_model(model_path):
    model_path = Path(model_path)
    if not model_path.is_absolute():
        model_path = PROJECT_ROOT / model_path
    print(f"[INFO] Loading model from {model_path}...")
    # The baseline includes the tokenizer. Do not silently download a different
    # one or load pickle-based training state when reproducing inference.
    tokenizer = BertTokenizerFast.from_pretrained(model_path, local_files_only=True)
    model = BertForSequenceClassification.from_pretrained(
        model_path, local_files_only=True, use_safetensors=True
    )
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
    # Training maps original labels 1,2,3,4 to class IDs 0,1,2,3.
    # Preserve the class ID here; this is not a probability or a 0-10 score.
    
    predictions = torch.argmax(logits, dim=-1).cpu().numpy()
    return predictions

def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[INFO] Using device: {device}")

    supabase = get_supabase()
    tokenizer, model = load_model(os.environ.get("SAFETRIP_MODEL_PATH", str(MODEL_PATH)))
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

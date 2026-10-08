"""Local-only model loading and CPU-compatible inference, without persistence."""
from pathlib import Path
from safetrip.config import resolve_path

def load_model(model_path):
    from transformers import BertTokenizerFast, BertForSequenceClassification
    model_path = Path(model_path)
    if not model_path.is_absolute():
        model_path = resolve_path(model_path)
    print(f"[INFO] Loading model from {model_path}...")
    # The baseline includes the tokenizer. Do not silently download a different
    # one or load pickle-based training state when reproducing inference.
    tokenizer = BertTokenizerFast.from_pretrained(model_path, local_files_only=True)
    model = BertForSequenceClassification.from_pretrained(
        model_path, local_files_only=True, use_safetensors=True
    )
    return tokenizer, model

def score_texts(texts, tokenizer, model, device):
    import torch
    inputs = tokenizer(texts, truncation=True, padding=True, max_length=256, return_tensors="pt").to(device)
    with torch.no_grad():
        outputs = model(**inputs)

    logits = outputs.logits
    # Training maps original labels 1,2,3,4 to class IDs 0,1,2,3.
    # Preserve the class ID here; this is not a probability or a 0-10 score.

    predictions = torch.argmax(logits, dim=-1).cpu().numpy()
    return predictions

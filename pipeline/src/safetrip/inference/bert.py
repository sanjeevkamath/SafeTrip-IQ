"""Local-only model loading and CPU-compatible inference, without persistence."""
from pathlib import Path
import os
from safetrip.config import resolve_path

INFERENCE_VERSION = "bert-document-inputs-v2"

def load_model(model_path):
    from transformers import BertTokenizerFast, BertForSequenceClassification
    model_path = Path(model_path)
    if not model_path.is_absolute():
        model_path = resolve_path(model_path)
    if os.environ.get("SAFETRIP_MODEL_MANIFEST"):
        from safetrip.inference.integrity import verify_model
        verify_model(model_path, resolve_path(os.environ["SAFETRIP_MODEL_MANIFEST"]))
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
    from safetrip.inference.document_inputs import encode_documents, pool_document_logits
    policy = getattr(model.config, "safetrip_input_policy", "head")
    length = getattr(model.config, "safetrip_max_length", 256)
    overlap = getattr(model.config, "safetrip_chunk_overlap", 128)
    if length not in {256, 512} or policy not in {"head", "head_tail", "chunks"}:
        raise ValueError("Unsupported model document-input configuration.")
    inputs, documents = encode_documents(tokenizer, texts, policy=policy, max_length=length, overlap=overlap)
    inputs = inputs.to(device)
    with torch.no_grad():
        # Bound inference memory even when many long advisories are batched together.
        windows = [model(**{name: value[start:start + 4] for name, value in inputs.items()}).logits
                   for start in range(0, len(documents), 4)]
    logits = pool_document_logits(torch.cat(windows), documents, len(texts))
    # Training maps original labels 1,2,3,4 to class IDs 0,1,2,3.
    # Preserve the class ID here; this is not a probability or a 0-10 score.

    predictions = torch.argmax(logits, dim=-1).cpu().numpy()
    return predictions

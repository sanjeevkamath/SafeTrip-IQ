"""Shared document encoding for research and inference; optional ML imports are lazy."""


def token_windows(ids, *, policy, max_length, special_tokens=2, overlap=128):
    capacity = max_length - special_tokens
    if capacity <= 0:
        raise ValueError("Token limit must allow content and special tokens.")
    if policy == "head":
        return [ids[:capacity]]
    if policy == "head_tail":
        if len(ids) <= capacity:
            return [ids]
        first = (capacity + 1) // 2
        return [ids[:first] + ids[-(capacity - first):]]
    if policy != "chunks" or not 0 <= overlap < capacity:
        raise ValueError("Invalid document input policy or overlap.")
    result = []
    for start in range(0, max(len(ids), 1), capacity - overlap):
        result.append(ids[start:start + capacity])
        if start + capacity >= len(ids):
            break
    return result


def encode_documents(tokenizer, texts, *, policy="head", max_length=256, overlap=128, fixed_padding=False):
    features, documents = [], []
    for number, text in enumerate(texts):
        ids = tokenizer.encode(text, add_special_tokens=False, truncation=False)
        for window in token_windows(ids, policy=policy, max_length=max_length,
                                    special_tokens=tokenizer.num_special_tokens_to_add(pair=False), overlap=overlap):
            features.append(tokenizer.prepare_for_model(window, add_special_tokens=True,
                                                        return_attention_mask=True, truncation=False))
            documents.append(number)
    return tokenizer.pad(features, padding="max_length" if fixed_padding else True,
                         max_length=max_length if fixed_padding else None, return_tensors="pt"), documents


def pool_document_logits(logits, documents, count):
    import torch
    indices = torch.tensor(documents, device=logits.device)
    sums = logits.new_zeros((count, logits.shape[-1])).index_add(0, indices, logits)
    counts = torch.bincount(indices, minlength=count).to(logits.dtype).unsqueeze(1)
    if bool((counts == 0).any()):
        raise ValueError("Every advisory requires at least one window.")
    return sums / counts

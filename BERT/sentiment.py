from sklearn.metrics import classification_report, confusion_matrix
from datasets import load_dataset, DatasetDict
from transformers import (
    BertTokenizerFast, BertForSequenceClassification,
    TrainingArguments, Trainer, DataCollatorWithPadding
)
import numpy as np
from sklearn.metrics import accuracy_score, f1_score
import torch
from collections import Counter

MODEL = "bert-base-uncased"
TEST_SIZE = 0.1
SEED = 42

# 1) Load CSVs
raw = load_dataset(
    "csv",
    data_files={"train": "BERT/train.csv", "test": "BERT/test.csv"}
)

def merge_labels(example):
    if example["label"] == 4:
        example["label"] = 3
    return example

raw["train"] = raw["train"].map(merge_labels)
raw["test"]  = raw["test"].map(merge_labels)

# 2) Normalize column names (strip whitespace)
def strip_colnames(ds):
    rename = {c: c.strip() for c in ds.column_names}
    # only rename if any name changes
    if any(k != v for k, v in rename.items()):
        ds = ds.rename_columns(rename)
    return ds

raw["train"] = strip_colnames(raw["train"])
raw["test"]  = strip_colnames(raw["test"])

# 3) Identify columns
cols = raw["train"].column_names
if "label" not in cols:
    raise ValueError(f"Expected a 'label' column, found: {cols}")
text_col = "text" if "text" in cols else None
if text_col is None:
    # Try a best-effort guess: pick the non-label column
    candidates = [c for c in cols if c != "label"]
    if len(candidates) == 1:
        text_col = candidates[0]
    else:
        raise ValueError(f"Couldn't find text column. Columns: {cols}")

# 4) Ensure label is numeric and contiguous 0..K-1
train_labels = raw["train"]["label"]
if isinstance(train_labels[0], str):
    # map strings -> ints
    label_names = sorted(set(train_labels))
    name2id = {n: i for i, n in enumerate(label_names)}
    def map_labels(ex): ex["label"] = name2id[ex["label"]]; return ex
    raw["train"] = raw["train"].map(map_labels)
    raw["test"]  = raw["test"].map(map_labels)
else:
    # shift labels to 0..K-1 if they are {1,2,3,...}
    unique = sorted(set(train_labels))
    if unique != list(range(len(unique))):
        remap = {v: i for i, v in enumerate(unique)}
        def remap_labels(ex): ex["label"] = remap[int(ex["label"])]; return ex
        raw["train"] = raw["train"].map(remap_labels)
        raw["test"]  = raw["test"].map(remap_labels)

num_labels = len(set(raw["train"]["label"]))

# 5) Try stratified split, else fallback
counts = Counter(raw["train"]["label"])
min_class = min(counts.values())
can_stratify = min_class >= 2  # with 10% val, each class needs >=2 to put >=1 in val

if can_stratify:
    split = raw["train"].train_test_split(test_size=0.1, seed=42)

else:
    print(f"[WARN] Cannot stratify (class counts: {dict(counts)}). Using random split.")
    split = raw["train"].train_test_split(test_size=TEST_SIZE, seed=SEED)

dataset = DatasetDict({
    "train": split["train"],
    "validation": split["test"],
    "test": raw["test"],
})

# 6) Tokenization (dynamic padding via data collator)
tokenizer = BertTokenizerFast.from_pretrained(MODEL)

def tokenize(batch):
    return tokenizer(batch[text_col], truncation=True, max_length=256)

tokenized = {k: ds.map(tokenize, batched=True) for k, ds in dataset.items()}
for k in tokenized:
    keep = ["input_ids", "attention_mask", "label"]
    tokenized[k] = tokenized[k].remove_columns([c for c in tokenized[k].column_names if c not in keep])
    tokenized[k] = tokenized[k].with_format("torch")

# 7) Model, collator, metrics
model = BertForSequenceClassification.from_pretrained(MODEL, num_labels=num_labels)
collator = DataCollatorWithPadding(tokenizer=tokenizer)

def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=1)
    avg = "binary" if num_labels == 2 else "weighted"
    return {
        "accuracy": accuracy_score(labels, preds),
        "f1": f1_score(labels, preds, average=avg),
    }

use_fp16 = torch.cuda.is_available()
args = TrainingArguments(
    output_dir="./results",
    evaluation_strategy="epoch",
    save_strategy="epoch",
    load_best_model_at_end=True,
    metric_for_best_model="f1",
    greater_is_better=True,
    per_device_train_batch_size=16,
    per_device_eval_batch_size=32,
    learning_rate=2e-5,
    num_train_epochs=3,
    weight_decay=0.01,
    seed=SEED,
    fp16=use_fp16,
    report_to=None,
)

trainer = Trainer(
    model=model,
    args=args,
    train_dataset=tokenized["train"],
    eval_dataset=tokenized["validation"],
    tokenizer=tokenizer,
    data_collator=collator,
    compute_metrics=compute_metrics,
)

trainer.train()

print(trainer.evaluate(eval_dataset=tokenized["test"]))


preds = trainer.predict(tokenized["test"])
logits, labels = preds.predictions, preds.label_ids
y_pred = np.argmax(logits, axis=-1)



print(classification_report(labels, y_pred))
print(confusion_matrix(labels, y_pred))

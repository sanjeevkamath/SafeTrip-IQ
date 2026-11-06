"""Train a versioned BERT candidate on prepared grouped data; no deployment or test evaluation."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import time

ROOT = Path(__file__).resolve().parents[2]
BASE_REVISION = "86b5e0934494bd15c9632b12f734a8a67f723594"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / ".local/research/bert/dataset-v2")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--base-model", type=Path, default=Path.home() / ".cache/huggingface/hub/models--bert-base-uncased/snapshots" / BASE_REVISION)
    parser.add_argument("--device", choices=("auto", "cpu", "mps", "cuda"), default="auto")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--accumulation", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-length", type=int, choices=(256, 512), default=256)
    parser.add_argument("--input-policy", choices=("head", "head_tail", "chunks"), default="head")
    parser.add_argument("--class-weighting", choices=("none", "balanced"), default="none")
    args = parser.parse_args()
    if min(args.epochs, args.batch_size, args.accumulation) < 1 or args.learning_rate <= 0:
        parser.error("Training settings must be positive.")
    # Optional ML imports happen only after parsing, preserving offline --help.
    import torch
    from torch.utils.data import DataLoader
    from transformers import BertTokenizerFast, BertForSequenceClassification, get_linear_schedule_with_warmup
    from safetrip.ingestion.advisories import CLEANING_VERSION
    from research.scripts.evaluate_bert_validation import metrics
    from safetrip.inference.document_inputs import encode_documents, pool_document_logits

    manifest_path = args.dataset / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest["cleaning_version"] != CLEANING_VERSION:
        raise ValueError("Dataset preprocessing version differs from runtime.")
    for name, expected in manifest["cleaner_source_hashes"].items():
        if hashlib.sha256((ROOT / "pipeline/src/safetrip/ingestion" / name).read_bytes()).hexdigest() != expected:
            raise ValueError("Cleaner changed after preparing the dataset.")
    splits = {}
    for split in ("train", "validation"):
        path = args.dataset / (split + ".jsonl")
        if hashlib.sha256(path.read_bytes()).hexdigest() != manifest["artifacts"][path.name]:
            raise ValueError("Dataset differs from its pinned hash.")
        splits[split] = [json.loads(line) for line in path.read_text().splitlines()]
    if {r["group_id"] for r in splits["train"]} & {r["group_id"] for r in splits["validation"]}:
        raise ValueError("Training and validation share a similarity group.")
    if not (args.base_model / "model.safetensors").is_file():
        raise FileNotFoundError("Pinned pretrained safetensors are not cached; obtain the base model separately.")
    device = args.device
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    if device == "mps" and not torch.backends.mps.is_available():
        raise ValueError("MPS unavailable in this process; run outside the sandbox or use CPU.")
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.set_num_threads(2)
    if device == "cuda":
        torch.cuda.manual_seed_all(args.seed)
    output = args.output or ROOT / ".local/research/bert" / datetime.now(timezone.utc).strftime("candidate-%Y%m%dT%H%M%S%fZ")
    output.mkdir(parents=True, exist_ok=False)
    report = {
        "status": "running", "base_model": "bert-base-uncased", "base_revision": args.base_model.name,
        "base_weights_sha256": hashlib.sha256((args.base_model / "model.safetensors").read_bytes()).hexdigest(),
        "dataset_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "cleaning_version": CLEANING_VERSION, "label_mapping": manifest["label_mapping"],
        "device": device, "seed": args.seed, "epochs": args.epochs,
        "batch_size": args.batch_size, "gradient_accumulation": args.accumulation,
        "effective_batch_size": args.batch_size * args.accumulation,
        "learning_rate": args.learning_rate, "max_length": args.max_length, "weight_decay": 0.01,
        "input_policy": args.input_policy, "chunk_overlap": 128, "class_weighting": args.class_weighting,
        "selection_metric": "validation_macro_f1", "test_set_used": False,
        "torch_version": torch.__version__, "history": [],
        "reproducibility_note": "Seeds and inputs pinned; accelerator results need not be bit-for-bit deterministic.",
    }
    def save_report():
        temporary = output / "training-report.tmp"
        temporary.write_text(json.dumps(report, indent=2) + "\n")
        temporary.replace(output / "training-report.json")
    save_report()
    print(f"Training candidate on {device}; outputs: {output}", flush=True)
    tokenizer = BertTokenizerFast.from_pretrained(args.base_model, local_files_only=True)
    names = {i: "LEVEL_" + str(i + 1) for i in range(4)}
    model = BertForSequenceClassification.from_pretrained(
        args.base_model, local_files_only=True, use_safetensors=True, num_labels=4,
        id2label=names, label2id={v: k for k, v in names.items()})
    model.to(device)
    model.config.safetrip_input_policy = args.input_policy
    model.config.safetrip_max_length = args.max_length
    model.config.safetrip_chunk_overlap = 128
    model.config.safetrip_cleaning_version = CLEANING_VERSION
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    report["memory_policy"] = "fixed token padding, gradient checkpointing, per-update MPS cache release"
    class_counts = [sum(row["label"] == label for row in splits["train"]) for label in range(4)]
    weights = [len(splits["train"]) / (4 * count) for count in class_counts] if args.class_weighting == "balanced" else [1.0] * 4
    class_weights = torch.tensor(weights, device=device)
    report.update(training_class_counts=class_counts, class_weights=weights)
    def collate(rows):
        batch, documents = encode_documents(tokenizer, [row["text"] for row in rows],
                                             policy=args.input_policy, max_length=args.max_length, fixed_padding=True)
        return batch, documents, torch.tensor([row["label"] for row in rows])
    loader = DataLoader(splits["train"], batch_size=args.batch_size, shuffle=True, collate_fn=collate,
                        generator=torch.Generator().manual_seed(args.seed))
    validation = DataLoader(splits["validation"], batch_size=1 if args.input_policy == "chunks" else 4, collate_fn=collate)
    no_decay = ("bias", "LayerNorm.weight")
    parameters = [{"params": [p for n, p in model.named_parameters() if not any(term in n for term in no_decay)], "weight_decay": 0.01},
                  {"params": [p for n, p in model.named_parameters() if any(term in n for term in no_decay)], "weight_decay": 0.0}]
    optimizer = torch.optim.AdamW(parameters, lr=args.learning_rate, foreach=False)
    steps_per_epoch = (len(loader) + args.accumulation - 1) // args.accumulation
    total_steps = steps_per_epoch * args.epochs
    scheduler = get_linear_schedule_with_warmup(optimizer, num_warmup_steps=int(total_steps * 0.1), num_training_steps=total_steps)
    report.update(optimizer="AdamW", warmup_steps=int(total_steps * 0.1), optimizer_steps=total_steps)
    best = -1.0
    started = time.monotonic()
    try:
        for epoch in range(args.epochs):
            model.train()
            optimizer.zero_grad(set_to_none=True)
            loss_total = 0.0
            for step, (batch, documents, labels) in enumerate(loader):
                batch = {name: tensor.to(device) for name, tensor in batch.items()}
                logits = pool_document_logits(model(**batch).logits, documents, len(labels))
                # Per-document weighting survives batch-size-one gradient accumulation.
                loss = torch.nn.functional.cross_entropy(logits, labels.to(device), weight=class_weights,
                                                        reduction="none").mean()
                loss_total += loss.item()
                divisor = min(args.accumulation, len(loader) - (step // args.accumulation) * args.accumulation)
                (loss / divisor).backward()
                del loss, logits, batch
                if (step + 1) % args.accumulation == 0 or step + 1 == len(loader):
                    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    optimizer.step()
                    scheduler.step()
                    optimizer.zero_grad(set_to_none=True)
                    if device == "mps":
                        torch.mps.empty_cache()
                    if (step + 1) % 40 == 0 or step + 1 == len(loader):
                        print(f"Epoch {epoch + 1}/{args.epochs}: {step + 1}/{len(loader)} batches", flush=True)
            model.eval()
            actual, predictions = [], []
            with torch.no_grad():
                for batch, documents, labels in validation:
                    actual.extend(labels.tolist())
                    logits = model(**{name: tensor.to(device) for name, tensor in batch.items()}).logits
                    logits = pool_document_logits(logits, documents, len(labels))
                    predictions.extend(logits.argmax(-1).cpu().tolist())
            result = metrics(actual, predictions)
            report["history"].append({"epoch": epoch + 1, "mean_training_loss": loss_total / len(loader), "validation": result,
                                      "validation_predictions": predictions})
            if result["macro_f1"] > best:
                best = result["macro_f1"]
                report["best_epoch"] = epoch + 1
                report["best_validation_macro_f1"] = best
                model.config._name_or_path = "bert-base-uncased"
                model.save_pretrained(output / "model", safe_serialization=True)
                tokenizer.name_or_path = "bert-base-uncased"
                tokenizer.init_kwargs["name_or_path"] = "bert-base-uncased"
                tokenizer.save_pretrained(output / "model")
            save_report()
            print(f"Epoch {epoch + 1}: validation accuracy={result['accuracy']:.4f}, macro-F1={result['macro_f1']:.4f}", flush=True)
        report.update(status="succeeded", seconds=round(time.monotonic() - started, 3))
    except BaseException as error:
        report.update(status="interrupted" if isinstance(error, KeyboardInterrupt) else "failed", error_type=type(error).__name__)
        raise
    finally:
        save_report()
    print(f"Candidate complete; best epoch {report['best_epoch']}. No test evaluation or deployment performed.", flush=True)


if __name__ == "__main__":
    main()

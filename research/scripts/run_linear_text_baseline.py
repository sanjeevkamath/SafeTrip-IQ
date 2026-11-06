"""Validation-only full-text TF-IDF/logistic baseline for diagnosing BERT experiments."""
import hashlib
import json
from pathlib import Path

from research.scripts.evaluate_bert_validation import metrics

ROOT = Path(__file__).resolve().parents[2]


def main():
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from threadpoolctl import threadpool_limits
    dataset = ROOT / ".local/research/bert/dataset-v3c"
    output = ROOT / ".local/research/bert/investigation-v3c/linear-validation.json"
    if output.exists():
        raise FileExistsError("Linear experiment already exists.")
    manifest = json.loads((dataset / "manifest.json").read_text())
    splits = {}
    for split in ("train", "validation"):
        path = dataset / (split + ".jsonl")
        if hashlib.sha256(path.read_bytes()).hexdigest() != manifest["artifacts"][path.name]:
            raise ValueError("Dataset hash changed.")
        splits[split] = [json.loads(line) for line in path.read_text().splitlines()]
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True, max_features=20000)
    train = vectorizer.fit_transform([r["text"] for r in splits["train"]])
    validation = vectorizer.transform([r["text"] for r in splits["validation"]])
    reports = []
    features = vectorizer.get_feature_names_out()
    with threadpool_limits(limits=2):
        for c in (0.1, 1.0, 10.0):
            classifier = LogisticRegression(C=c, class_weight="balanced", max_iter=2000, random_state=42)
            classifier.fit(train, [r["label"] for r in splits["train"]])
            predictions = [int(v) for v in classifier.predict(validation)]
            reports.append({"C": c, "metrics": metrics([r["label"] for r in splits["validation"]], predictions),
                            "validation_predictions": predictions,
                            "highest_positive_features": {str(label + 1): [str(features[i]) for i in classifier.coef_[label].argsort()[-12:][::-1]]
                                                          for label in range(4)}})
    report = {"model_family": "full-text TF-IDF + class-balanced logistic regression", "experiments": reports,
              "dataset_manifest_sha256": hashlib.sha256((dataset / "manifest.json").read_bytes()).hexdigest(),
              "test_used": False, "selected_C": max(reports, key=lambda r: r["metrics"]["macro_f1"])["C"]}
    with output.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    for experiment in reports:
        print(json.dumps({"C": experiment["C"], "metrics": experiment["metrics"]}))


if __name__ == "__main__":
    main()

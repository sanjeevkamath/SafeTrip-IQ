"""Reconstructed legacy scoring rule, matched against 212 stored scores.

This preserves observed behavior; it is not a calibrated measure of travel risk.
The original SQL that calculated safe_trip_score has not been recovered.
"""


def legacy_safety_score(bert_score, clustering_score):
    components = []
    for name, value, maximum, factor in (
        ("bert_score", bert_score, 3, 2.5),
        ("clustering_score", clustering_score, 4, 2.0),
    ):
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
            raise ValueError(f"{name} must be an integer from 0 to {maximum}, or None")
        components.append(10.0 - factor * value)
    return sum(components) / len(components) if components else None

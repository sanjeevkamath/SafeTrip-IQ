# Advisory preprocessing (current: v4)

`advisory-no-country-labels-v4` removes country names and direct advisory classification cues before BERT inference. It applies to RSS ingestion and to JSON scoring inputs, including cloud benchmarks. Original XML, raw descriptions, country names, and ISO3 identifiers remain available for auditing and database linking.

The cleaner strips HTML, decodes entities, normalizes apostrophes/whitespace, removes specific boilerplate sentences, removes explicit levels 1–4 (including Roman numerals and spelled-out numbers), and removes “Exercise normal precautions,” “Exercise increased caution,” “Reconsider travel,” and “Do not travel.” It removes country names using a static catalogue derived from pycountry 24.6.1 plus common/advisory aliases, as well as the country name parsed from the feed title. It preserves the surrounding risk evidence and lowercases the result.

Country matching uses whole lexical boundaries and longest names first. It removes references to other countries too. This is not a general named-entity recognizer: cities, demonyms, and unknown aliases can remain. Ambiguous names such as Turkey or Georgia are removed whenever they match; context-sensitive entity handling is a future improvement. Removing names does not prove that all geographical clues have been eliminated.

Boilerplate removal is now bounded by sentence-ending punctuation instead of discarding all subsequent text. Punctuation abbreviations can affect these regex sentence boundaries; new feed formats need regression examples. If removing labels leaves no usable text, validation stops the run before inference/publication rather than generating a score from an empty input.

Both cleaned-text hashes and cleaning-version metadata participate in prediction reuse. The new version forces recomputation of prior cached predictions, even if a particular row's text did not change. The first full refresh can therefore score the entire feed. Baseline datasets and captured predictions remain frozen as historical evidence; they are not rewritten to make regression tests pass.

## Checkpoint compatibility

On October 13, 2026, an offline scan of frozen baseline data found direct level/recommendation cues in 1,097 of 1,107 training rows and 498 of 502 test rows. These counts indicate a substantial label-leakage risk; they do not prove which features the saved model used or measure its accuracy. The located Wayback cleaner removes some boilerplate but does not remove these cues from body text.

Before enabling production publication with this preprocessing version, clean training and evaluation inputs using the same versioned rules, review rows that become empty, evaluate the saved checkpoint on that data, and retrain/evaluate a candidate without direct labels or country names. Review country/time overlap between splits to limit leakage, and keep the frozen baseline untouched. Promote only a separately versioned model with documented evaluation. Retraining investigations are recorded in [bert-investigation-v3.md](bert-investigation-v3.md). No candidate has been approved for production.

All 209 historical advisory rows retained nonempty text in an offline check against their raw descriptions. Their cleaned texts changed. This is a historical-input check, not verification of today's live feed. Previous AWS benchmark timings and aggregate counts describe the earlier image/cleaner; rebuild and pin a new image for further AWS runs, and do not reuse saved completed benchmark reports as evidence for this version.

V4 additionally removes singular “normal precaution” and the aliases Republic of Korea, ROK, DPRK, and DRC. The v3 investigation preserves its original cleaned inputs for a fair comparison; those checkpoints are not v4 production candidates.

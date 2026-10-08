-- Deterministic development fixtures, not current travel guidance.
-- Scores reproduce the frozen CAN/JPN/USA baseline. Descriptions are synthetic.
\set ON_ERROR_STOP on
BEGIN;
INSERT INTO countries (iso3, name, iso2, continent) VALUES
    ('CAN', 'Canada', 'CA', 'North America'),
    ('JPN', 'Japan', 'JP', 'Asia'),
    ('USA', 'United States', 'US', 'North America')
ON CONFLICT (iso3) DO UPDATE SET name=excluded.name, iso2=excluded.iso2, continent=excluded.continent;
INSERT INTO culture (iso3, overview) VALUES
    ('CAN', 'Synthetic development content, not travel guidance.'),
    ('JPN', 'Synthetic development content, not travel guidance.')
ON CONFLICT (iso3) DO UPDATE SET overview=excluded.overview;
INSERT INTO scores (iso3, safe_trip_score, bert_score, clustering_score) VALUES
    ('CAN', 10, 0, 0), ('JPN', 10, 0, 0), ('USA', 6, NULL, 2)
ON CONFLICT (iso3) DO UPDATE SET safe_trip_score=excluded.safe_trip_score,
    bert_score=excluded.bert_score, clustering_score=excluded.clustering_score;
INSERT INTO bert_scores (iso3, cleaned_text, bert_score) VALUES
    ('CAN', 'synthetic development fixture', 0), ('JPN', 'synthetic development fixture', 0)
ON CONFLICT (iso3) DO UPDATE SET cleaned_text=excluded.cleaned_text, bert_score=excluded.bert_score;
INSERT INTO clustering (iso3, clustering_score) VALUES ('CAN', 0), ('JPN', 0), ('USA', 2)
ON CONFLICT (iso3) DO UPDATE SET clustering_score=excluded.clustering_score;
INSERT INTO travel_advisories (iso3, country_name, description_text, last_fetched_at) VALUES
    ('CAN', 'Canada', 'Synthetic development advisory.', '2026-01-01T00:00:00Z'),
    ('JPN', 'Japan', 'Synthetic development advisory.', '2026-01-01T00:00:00Z')
ON CONFLICT (iso3) DO UPDATE SET country_name=excluded.country_name,
    description_text=excluded.description_text, last_fetched_at=excluded.last_fetched_at;
COMMIT;

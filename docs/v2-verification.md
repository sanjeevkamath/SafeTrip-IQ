# V2 verification — November 6, 2026

## Hosted refresh and publication

The [refresh-only run](https://github.com/sanjeevkamath/SafeTrip-IQ/actions/runs/42283982340) completed capture, scoped import and score preview; publication was deliberately skipped.

The [end-to-end manual run](https://github.com/sanjeevkamath/SafeTrip-IQ/actions/runs/42287664477) then completed both jobs, including **Independently read back outputs and verify preserved model inputs**. Its evidence recorded:

| Check | Result |
| --- | --- |
| Source documents | 444: 218 US and 226 UK |
| Existing versions reused | 444; zero new documents/versions for unchanged source content |
| New retrieval observations | 444 |
| Review-required records retained | 5: unresolved compounds or overlapping whole-country documents; unresolved coverage supplies no guessed national score |
| Published catalogue rows | 250 |
| Both components / US only / clustering only / neither | 165 / 47 / 3 / 35 |
| Numeric / blank overall values | 215 / 35 |
| Numeric changes in this repeated publication | 0 |
| Publication UUID | `61cb6b87-2e6e-44a7-bb73-8e7af0b9d220` |

The successful workflow ID `42287664477` is the weekly activation receipt. This is different from the database publication UUID. Repository activation settings were configured only after checking the successful import, publication and read-back through GitHub's API. The weekly cron itself takes effect after this branch is merged into main.

Evidence stays under ignored `.local/v2/operations/`, including downloaded workflow artifacts. Generated connection configuration is not in this document or the PR.

## Read-only production browser checks

Headless Chromium checked the actual live Vercel website and its real geometry/API responses, without synthetic production data or writes:

- Map API returned 250 countries, 215 numeric scores and 35 blanks.
- Canada displayed 10.0 and green; USA displayed 6.0 and its clustering-only explanation; Afghanistan displayed 2.25 internally and its explicit Level 4 warning. Map colors matched the website's scale.
- Palestine's polygon was gray, with no national score. Palestine and BES country pages retained Gaza/West Bank and Bonaire/Saba/Sint Eustatius warnings respectively.
- Canada search selected the correct country page and score. Official breakdowns did not label historical BERT as a production component.
- India's UK affected-area disclosure opened and contained retained official excerpts.
- Unknown ISO3 `ZZZ` returned 404.

These are snapshot/smoke checks, not a claim that every country's source text has been manually audited or that the index predicts individual safety. The low-resolution geometry does not represent every catalogue destination separately.

## Local verification

- 115 dependency-free Python tests and nine credential tests passed. The historical baseline still reproduces all 212 captured scores exactly after moving experiment tools.
- 52 real PostgreSQL integration tests passed, including owner restore dry-run rollback, committed restoration, newly inserted score-row removal, retained history/model inputs, stale-receipt rejection and changed-model-input rejection.
- 14 frontend rendering/query tests and seven real PostgreSQL frontend tests passed. Lint/typecheck/build passed, with three existing image lint warnings. Production dependency audit reported zero vulnerabilities; development-only moderate findings remain separate.
- Workflow syntax passed actionlint. The alert test verifies one issue on first failure, quiet unchanged failure and one recovery transition. Weekly activation tests reject refresh-only, skipped/failed publication, missing read-back, forks and non-main runs.
- Non-root container smoke checks and all five Chromium smoke tests passed, including an unpublished local dataset returning unhealthy freshness while remaining ready, and the separate advice/score freshness labels.

## Honest operational limits

No restore, downgrade or failure injection was performed against production. Recovery was rehearsed on isolated local PostgreSQL. The owner restore tool defaults to rollback and is not executable by the scheduled writer/publisher.

The actual new health query code was also run read-only against hosted PostgreSQL. It reported healthy data: 217 mapped US documents, 224 mapped UK documents and all 250 official score publications were fresh. Raw document counts differ because unresolved compounds are excluded from the display projection. No new permissions were needed.

After PR #23 was merged, production `/api/ready`, `/api/health`, `/api/refresh-status` and `/api/scoring-status` all returned HTTP 200. The deployed health route reported both sources fresh and all 250 official score publications fresh. The [first manually dispatched production monitor](https://github.com/sanjeevkamath/SafeTrip-IQ/actions/runs/42304087643) succeeded against the live endpoint. All PR #23 CI jobs, including container/Chromium checks, passed.

The weekly activation switch is enabled with verified manual run `42287664477`. The first scheduled weekly execution remains to be observed; the healthy monitor run does not prove a future cron delivery or failure-email delivery. Email delivery depends on the maintainer's GitHub notification settings. An independent external monitor has not been configured; a total GitHub outage or all scheduled workflows being disabled can affect both refresh and monitoring. See [operations](operations.md).

The production path uses official advisory values plus frozen clustering tiers; BERT remains experimental and AWS remains a separate benchmark/deployment lab. No retraining, extra hazard index, database migration to another provider, or frontend redesign is included.

## Interview walkthrough

Explain the data path first, then demonstrate a country with two components, one with one component and one without a national score. Show the separate US/UK regional warnings and source/retrieval dates. Explain why a missing warning is not a safe score.

Use the successful workflow and database receipt to explain the engineering tradeoffs: append-only source evidence, ISO3 identity with explicit regional scope, three scoped accounts, preview fingerprints, atomic score publication, separate import/publication transactions, independent read-back, and an owner-reviewed recovery path. Distinguish regression reproducibility from ML accuracy, and an AWS benchmark from an AWS production deployment.

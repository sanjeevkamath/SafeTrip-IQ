# V2 operations and recovery

The production website runs on Vercel; data stays on Supabase PostgreSQL. GitHub Actions fetches official US/UK advice and publishes `us-official-cluster-v1`. No AWS task or BERT retraining is scheduled.

## Cadence and activation

The refresh cron is **Monday at 10:17 UTC**: 05:17 Eastern Standard Time / 06:17 Eastern Daylight Time. A daily health check runs at 12:43 UTC. These are best-effort schedules, not exact execution-time guarantees. Times avoid the top of the hour, which GitHub documents as a busy period.

Scheduled writes require both repository variables:

- `SAFETRIP_WEEKLY_REFRESH_ENABLED=true`: explicit operator switch; set `false` to pause future scheduled imports and publication. Manual runs remain available.
- `SAFETRIP_VERIFIED_REFRESH_RUN=<run ID>`: a successful manual `refresh-advisories.yml` run on main in this repository. Both `refresh` and `publish`, including the independent read-back step, must have succeeded. A refresh-only run does not qualify.

The workflow also requires successful CI for the exact current main commit before accessing database credentials. No PR, fork or arbitrary branch can run the production path. Workflow concurrency prevents overlapping instances; database advisory locks and input fingerprint checks protect transactions against other cooperating writers and stale plans.

Automatic publication was chosen for weekly runs. The `score-publication` environment must allow main without a mandatory reviewer for unattended execution. If reviewers are enabled later, scheduled publication waits for approval rather than bypassing protection. The two environment write secrets remain separate; [setup instructions](advisory-refresh-actions.md) cover their roles.

To validate before activation, run on main:

```sh
gh workflow run refresh-advisories.yml --ref main -f publish_scores=true
gh run list --workflow refresh-advisories.yml --limit 3
```

After checking the successful publication artifact/read-back, record its numeric run ID and enable:

```sh
gh variable set SAFETRIP_VERIFIED_REFRESH_RUN --body RUN_ID_FROM_SUCCESSFUL_END_TO_END_RUN
gh variable set SAFETRIP_WEEKLY_REFRESH_ENABLED --body true
```

The activation verifier independently inspects this receipt using GitHub's API; it does not trust a variable pointing to a skipped publication. Variables are operational settings, not secrets. The cron only becomes available when this workflow version is merged into main. Pause with `gh variable set SAFETRIP_WEEKLY_REFRESH_ENABLED --body false`; an already-running workflow must be inspected separately.

## Freshness and public health

`GET /api/health` returns 200 only when:

- Both US and UK have mapped source documents and the **oldest current retrieval observation** for each source is at most 216 hours (nine days) old.
- Every catalogue destination has the official formula, publication run reference and timestamp, and the oldest publication is at most nine days old. Null scores count as published outputs; missing components must not be imputed safe.
- Database/schema access and the required scoring fields are available. Unavailable, incomplete, stale or implausibly future data produces 503.

The endpoint exposes aggregate counts/dates, not raw advisories, credentials or private run records. It uses the existing restricted website reader and needs no new grants. Nine days allows the seven-day refresh interval plus two days for delay/recovery. A government document can remain valid without being edited: freshness measures **our retrieval/publication**, not its original publication date or the vintage of frozen clustering features.

`GET /api/ready` preserves the former app/database connectivity check and is used by Docker's healthcheck. Stale/unpublished fixture data does not make an otherwise working container unready. `/api/health` deliberately answers the stronger data-freshness question for monitoring.

The homepage now shows separate US/UK check and score-publication dates. Its old 48-hour legacy-BERT threshold remains only for local/historical adapter paths. `/api/scoring-status` remains the publication readiness endpoint; it is not a liveness/freshness check by itself.

## Alerts and notification delivery

The refresh workflow opens one `[Operations] Advisory refresh failed` issue on a failed stage. It does not create another issue for every unchanged failure; inspect workflow runs for subsequent attempts. Resolve that incident manually after checking which stages committed.

The separate daily monitor calls public `/api/health` without database secrets. On unhealthy data, it opens one freshness issue. When health recovers, it comments once and closes that issue. If issue creation fails, the workflow also fails visibly. Full workflow cancellation or a GitHub outage can prevent a failure-reporting job from running; later freshness checks provide another signal.

Enable GitHub **Settings → Notifications → Actions → Email**, selecting failed workflows if desired, and watch this repository's Issues so operations issues reach you. Creating an issue does not prove email delivery: verify your notification preferences and email address. No SMTP secret or personal access token is required; only the alert jobs receive `issues: write` through the short-lived workflow token.

GitHub documents delayed/dropped scheduled events and automatic disabling of scheduled workflows in public repositories after 60 days without repository activity. A daily job on the same provider cannot detect a total GitHub outage or all schedules being disabled. For independent detection, configure an external HTTP monitor against `https://safetripiq.vercel.app/api/health` and verify its alert delivery. No external monitoring account has been created by this implementation.

## Failure investigation

1. Inspect the run's last successful step, artifact and `pipeline_runs` receipt. A capture file or empty result JSON does not prove a committed import/publication.
2. Preflight failures leave current source data untouched. Missing previously stored documents require deliberate withdrawal handling; do not waive the guard merely to get a green run. Unresolved compounds remain explicit and cannot supply guessed national scores.
3. After committed import, a scoring failure leaves newer cards with the prior score publication. Fix the cause and generate a fresh preview. Old previews are invalidated by input or publication changes.
4. After an ambiguous commit response, inspect the attempt run ID in the ledger before retrying. A job can fail after scores committed. Read-back failures do not automatically roll back a successful commit.
5. Save the evidence under ignored `.local/`, never in a public issue if it contains connection data. Artifacts last 14 days; database history is durable until separately retained/pruned. No automated pruning is introduced here.

## Reviewed score restoration

Prefer a forward correction and fresh official publication for bad source/mapping logic. Reverting application code alone does not undo database values. Advisory history is append-only and is not reverted by restoring scores.

For an incorrect **latest** official score publication:

1. Pause future weekly runs, inspect active runs, and wait for an active writer to finish. Keep its successful receipt and input snapshot. If a credential is implicated, disable its login and rotate it separately.
2. Review `db/security/restore_official_scores.sql` using the owner connection, outside GitHub Actions. Replace `REPLACE_WITH_INCIDENT_RUN_UUID` with the specific successful publication UUID. This is not the GitHub numeric workflow-run ID.
3. Run the complete file with its final **ROLLBACK** unchanged. Inspect the counts. It uses the shared locks, requires every current output to match that publication/history, checks unchanged model inputs, and refuses a superseded or already-restored receipt.
4. After reviewing that rehearsal, deliberately replace only the final `ROLLBACK;` with `COMMIT;` and run the full transaction again. It restores prior numeric/methodology fields, removes only score rows first created by that publication, preserves model/advisory/history records, and writes a separate restoration event in the run ledger.
5. Verify map/search/country values and provenance. Health may correctly become stale/incomplete if restoring an old/legacy snapshot. Fix the underlying cause, generate a new preview, and complete a new verified publication before resuming automation.

This owner-only tool grants no additional privileges and creates no stored database function. Dry-run rollback, committed restore, history/model preservation and refusal of stale/model-modified receipts are exercised against isolated local PostgreSQL. It has not been executed against production. Schema backups and isolated restore rehearsals remain separate from this targeted score recovery; never downgrade the hosted schema to roll back a publication.

## References

- [GitHub scheduled workflow caveats](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
- [GitHub Actions notifications](https://docs.github.com/en/subscriptions-and-notifications/how-tos/managing-github-actions-notifications)
- [Public-repository schedule disabling](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows)

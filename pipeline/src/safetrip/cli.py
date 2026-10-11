"""Explicit data commands; --write opts into publication.

publish-scores, runs, and status read PostgreSQL even without --write; other previews use local files.
"""
import argparse
import json
import os
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, description in (
        ("ingest", "Parse an RSS file or fetch the advisory feed."),
        ("score", "Score a local advisory JSON file using the saved checkpoint."),
        ("refresh", "Ingest and score advisories; with final publication the feed is a complete snapshot and missing advisories are cleared."),
        ("seed-countries", "Prepare the ISO country catalog."),
        ("import-clusters", "Prepare raw cluster IDs (does not rank risk tiers)."),
        ("publish-scores", "Read current Postgres components and preview final scores; --write commits them."),
        ("runs", "Read the 20 most recent Postgres run summaries into a JSON file."),
        ("status", "Report the last completed refresh and running attempts older than one hour."),
    ):
        command = commands.add_parser(name, help=description, description=description)
        command.add_argument("--output", required=True, help="New JSON artifact path; existing files are never overwritten.")
        command.add_argument("--write", action="store_true", help="Also publish to the configured database using backend credentials.")
        if name in {"ingest", "refresh", "score", "import-clusters"}:
            command.add_argument("--input", required=name == "score", help="Input XML (ingest/refresh), JSON (score), or CSV (import-clusters). For refresh final publication, supply the complete advisory feed.")
        if name in {"ingest", "refresh"}:
            command.add_argument("--iso-csv", help="Optional historical country-name lookup CSV.")
        if name in {"score", "refresh"}:
            command.add_argument("--model-path", help="Local checkpoint; defaults to SAFETRIP_MODEL_PATH or results/checkpoint-189.")
            command.add_argument("--publish-scores", action="store_true", help="With --write and Postgres, also recalculate final scores in the same transaction.")
    args = parser.parse_args(argv)
    final_scores = getattr(args, "publish_scores", False)
    if final_scores and not args.write:
        parser.error("--publish-scores requires --write; use publish-scores to preview stored components.")
    if args.command in {"runs", "status"} and args.write:
        parser.error("runs and status are read-only; omit --write.")
    from safetrip.config import load_environment, resolve_path
    from safetrip import jobs
    publisher = None
    run_metadata = {}
    try:
        load_environment()
        if resolve_path(args.output).exists():
            raise FileExistsError("Output already exists.")
        # Final-score previews need read access to the internal component tables.
        if args.write or args.command in {"publish-scores", "runs", "status"}:
            from safetrip.persistence.publication import get_publisher
            publisher = get_publisher(require_postgres=final_scores or args.command in {"publish-scores", "runs", "status"})
        from safetrip.persistence.postgres import PostgresPublisher
        tracked = isinstance(publisher, PostgresPublisher)
        if args.write and tracked:
            publisher.start_run(args.command)
        if args.command in {"runs", "status"}:
            jobs.save_json(args.output, publisher.recent_runs() if args.command == "runs" else publisher.refresh_status())
            print("Report saved. Database rows unchanged.")
            return 0
        if args.command == "publish-scores":
            artifact = publisher.publish_scores(args.output, write=args.write)
            print("Score preview saved. " + ("Final scores committed." if args.write else "Database rows unchanged."))
            print("Component coverage: " + json.dumps(artifact["coverage"], sort_keys=True))
            return 0
        if args.command in {"ingest", "refresh"}:
            run_metadata.update(source_kind="local_xml" if args.input else "state_department_feed",
                                cleaning_version="legacy-advisory-v1")
            def retain_raw(content):
                from hashlib import sha256
                raw_path = resolve_path(args.output + ".source.xml")
                raw_path.parent.mkdir(parents=True, exist_ok=True)
                with raw_path.open("xb") as stream:
                    stream.write(content)
                run_metadata["raw_sha256"] = sha256(content).hexdigest()
                if tracked:
                    publisher.retain_raw(content)
            rows = jobs.ingest(args.input, args.iso_csv or os.environ.get("SAFETRIP_ISO_CSV"), retain_raw=retain_raw)
            if args.command == "refresh":
                model_path = args.model_path or os.environ.get("SAFETRIP_MODEL_PATH", "results/checkpoint-189")
                reused = []
                if tracked:
                    scores, reused = jobs.incremental_score(rows, model_path, publisher, run_metadata)
                else:
                    scores = jobs.score(rows, model_path, metadata=run_metadata)
                artifact = {"advisories": rows, "bert_scores": scores}
                if tracked:
                    artifact["reused_bert_scores"] = reused
                    print(f"Advisories: {len(rows)}; inferred: {len(scores)}; reused: {len(reused)}.")
            else:
                artifact = rows
        elif args.command == "score":
            # External JSON may not have passed through our cleaner.
            run_metadata.update(source_kind="local_json", cleaning_version=None)
            rows = json.loads(resolve_path(args.input).read_text())
            scores = jobs.score(rows, args.model_path or os.environ.get("SAFETRIP_MODEL_PATH", "results/checkpoint-189"), metadata=run_metadata)
            artifact = scores
        elif args.command == "seed-countries":
            artifact = jobs.country_rows()
        else:
            artifact = jobs.cluster_rows(args.input or os.environ.get("SAFETRIP_CLUSTERING_CSV", "data/baseline/clustering/clusters.csv"))
        jobs.save_json(args.output, artifact)
        if publisher is not None:
            if tracked:
                publisher.publish(args.command, artifact, publish_scores=final_scores, metadata=run_metadata)
            else:
                publisher.publish(args.command, artifact)
        print("Artifact saved." + (" Intermediate data and final scores committed together." if final_scores else
              " Intermediate data published; final scores are unchanged." if args.write else " No database access performed."))
        return 0
    except Exception as error:
        if publisher is not None and hasattr(publisher, "fail_run"):
            publisher.fail_run(error)
        # SDK exceptions may include request URLs/credentials. Never echo them.
        from safetrip.persistence.postgres import ScorePublicationError
        message = str(error) if isinstance(error, ScorePublicationError) else f"Check input files and configuration ({type(error).__name__})."
        print(f"Command failed: {message} An output artifact does not confirm successful publication.", file=sys.stderr)
        if args.write and os.environ.get("SAFETRIP_DB_BACKEND", "supabase") == "supabase":
            print("Supabase publication may be partial.", file=sys.stderr)
        return 1
    finally:
        if publisher is not None:
            if getattr(publisher, "last_run_id", None) is not None:
                print(f"Run ID: {publisher.last_run_id}")
            publisher.close()


if __name__ == "__main__":
    raise SystemExit(main())

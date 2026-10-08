"""Explicit data commands. Local artifacts by default; --write opts into publication."""
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
        ("refresh", "Ingest and score advisories; output both intermediate datasets."),
        ("seed-countries", "Prepare the ISO country catalog."),
        ("import-clusters", "Prepare raw cluster IDs (does not rank risk tiers)."),
    ):
        command = commands.add_parser(name, help=description, description=description)
        command.add_argument("--output", required=True, help="New JSON artifact path; existing files are never overwritten.")
        command.add_argument("--write", action="store_true", help="Also publish to the configured database using backend credentials.")
        if name in {"ingest", "refresh", "score", "import-clusters"}:
            command.add_argument("--input", required=name == "score", help="Input XML (ingest/refresh), JSON (score), or CSV (import-clusters).")
        if name in {"ingest", "refresh"}:
            command.add_argument("--iso-csv", help="Optional historical country-name lookup CSV.")
        if name in {"score", "refresh"}:
            command.add_argument("--model-path", help="Local checkpoint; defaults to SAFETRIP_MODEL_PATH or results/checkpoint-189.")
    args = parser.parse_args(argv)
    from safetrip.config import load_environment, resolve_path
    from safetrip import jobs
    try:
        load_environment()
        if resolve_path(args.output).exists():
            raise FileExistsError("Output already exists.")
        # Resolve writer configuration before expensive work, but only when requested.
        client = None
        if args.write:
            from safetrip.persistence.supabase import get_writer_client
            client = get_writer_client()
        if args.command in {"ingest", "refresh"}:
            rows = jobs.ingest(args.input, args.iso_csv or os.environ.get("SAFETRIP_ISO_CSV"))
            if args.command == "refresh":
                scores = jobs.score(rows, args.model_path or os.environ.get("SAFETRIP_MODEL_PATH", "results/checkpoint-189"))
                artifact = {"advisories": rows, "bert_scores": scores}
            else:
                artifact = rows
        elif args.command == "score":
            rows = json.loads(resolve_path(args.input).read_text())
            scores = jobs.score(rows, args.model_path or os.environ.get("SAFETRIP_MODEL_PATH", "results/checkpoint-189"))
            artifact = scores
        elif args.command == "seed-countries":
            artifact = jobs.country_rows()
        else:
            artifact = jobs.cluster_rows(args.input or os.environ.get("SAFETRIP_CLUSTERING_CSV", "data/baseline/clustering/clusters.csv"))
        jobs.save_json(args.output, artifact)
        if client is not None:
            from safetrip.persistence import repository
            if args.command in {"ingest", "refresh"}:
                repository.write_advisories(client, rows)
            if args.command in {"score", "refresh"}:
                repository.write_bert_scores(client, scores)
            if args.command in {"seed-countries", "import-clusters"}:
                repository.write_rows(client, "countries" if args.command == "seed-countries" else "clustering", artifact)
        print("Artifact saved." + (" Intermediate data published; final scores are unchanged." if args.write else " No database access performed."))
        return 0
    except Exception as error:
        # SDK exceptions may include request URLs/credentials. Never echo them.
        print(f"Command failed ({type(error).__name__}). Check input files and configuration. Publication may be partial if --write was used.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

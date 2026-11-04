"""Explicit capture/preview/private-ingest commands; no score publication."""
import json
import sys


def run(args):
    from safetrip.config import resolve_path
    from safetrip.ingestion.multisource import AdvisoryValidationError, capture_bundle, normalize_bundle, preview
    publisher = None
    try:
        output = resolve_path(args.output)
        if output.exists():
            raise FileExistsError('Output exists.')
        if args.command == 'capture-advisories':
            bundle = capture_bundle(output, args.iso3)
            print(f"Capture complete: {len(bundle['captures'])} responses. No database access.")
            return 0
        bundle = json.loads(resolve_path(args.input).read_text())
        output.parent.mkdir(parents=True, exist_ok=True)
        # Reserve the path before any write, preventing a concurrent output collision.
        with output.open('x') as stream:
            if args.write:
                from safetrip.config import load_environment
                from safetrip.persistence.publication import get_publisher
                from safetrip.persistence.advisories import ingest_capture
                load_environment()
                publisher = get_publisher(require_postgres=True)
                report = ingest_capture(publisher, bundle)
            else:
                report = {**preview(normalize_bundle(bundle), requested=bundle.get('iso3')), 'database_written': False}
            json.dump(report, stream, indent=2)
            stream.write('\n')
        print('Private advisory ingestion committed; public scores unchanged.' if args.write else
              'Advisory preview saved. No database access performed.')
        return 0
    except Exception as error:
        if publisher is not None:
            publisher.fail_run(error)
        from safetrip.persistence.postgres import ScorePublicationError
        detail = str(error) if isinstance(error, (ScorePublicationError, AdvisoryValidationError)) else type(error).__name__
        print(f'Advisory command failed ({detail}). Capture/output files alone do not prove committed ingestion.', file=sys.stderr)
        return 1
    finally:
        if publisher is not None:
            if publisher.last_run_id:
                print('Run ID:', publisher.last_run_id)
            publisher.close()

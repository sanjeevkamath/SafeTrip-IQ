"""Compatibility command. Run with uv; publication now requires --write."""
from safetrip.inference.bert import load_model, score_texts


def main():
    import sys
    from safetrip.cli import main as run
    return run(["score", *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())

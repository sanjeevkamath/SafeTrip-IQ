"""Compatibility command. Run with uv; publication now requires --write."""


def main():
    import sys
    from safetrip.cli import main as run
    return run(["import-clusters", *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())

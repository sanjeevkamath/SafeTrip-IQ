"""Make a deterministic archive of only the checksum-pinned baseline model files."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile

from safetrip.inference.integrity import verify_model


def package(model, manifest, output):
    model, manifest, output = Path(model), Path(manifest), Path(output)
    verify_model(model, manifest)
    files = json.loads(manifest.read_text())["model_files"]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream, tarfile.open(fileobj=stream, mode="w|") as archive:
        for name in sorted(files):
            source = model / name
            info = tarfile.TarInfo(name)
            info.size = files[name]["bytes"]
            info.mode = 0o444
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            with source.open("rb") as data:
                archive.addfile(info, data)
    with output.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"archive": str(output), "bytes": output.stat().st_size, "sha256": digest}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="results/checkpoint-189")
    parser.add_argument("--manifest", default="docs/baseline/artifacts.json")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(package(args.model, args.manifest, args.output), sort_keys=True))


if __name__ == "__main__":
    main()

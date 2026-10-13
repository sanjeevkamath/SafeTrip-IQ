"""Small offline Docker benchmark; no database connection or publication."""
import argparse
from datetime import datetime, timezone
import json
import hashlib
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent


def inside(advisories=None):
    import os
    import resource
    started = time.perf_counter()
    from safetrip.inference.bert import load_model, score_texts
    if advisories:
        from safetrip.jobs import validate_advisories
        source_bytes = Path(advisories).read_bytes()
        rows = validate_advisories(json.loads(source_bytes))
        texts = [row['description_text'] for row in rows]
    else:
        fixture = json.loads(Path('/app/fixtures/bert_predictions.json').read_text())['rows']
        texts = [row['text'] for row in fixture]
    load_started = time.perf_counter()
    tokenizer, model = load_model(os.environ['SAFETRIP_MODEL_PATH'])
    model.to('cpu').eval()
    load_seconds = time.perf_counter() - load_started
    predictions = []
    timings = []
    # Match the production worker's batches of 16. Full data runs once;
    # the tiny fixture also measures a second same-process warm inference.
    for _ in range(1 if advisories else 2):
        predictions = []
        for start in range(0, len(texts), 16):
            before = time.perf_counter()
            predictions.extend(int(value) for value in score_texts(texts[start:start+16], tokenizer, model, 'cpu'))
            timings.append(time.perf_counter() - before)
        if not advisories and predictions != [row['expected_class_id'] for row in fixture]:
            raise RuntimeError('Fixture predictions changed.')
    if len(predictions) != len(texts) or any(value not in range(4) for value in predictions):
        raise RuntimeError('Incomplete or invalid predictions.')
    peak_path = Path('/sys/fs/cgroup/memory.peak')
    manifest = json.loads(Path('/app/model-manifest.json').read_text())
    report = {
        'input_rows':len(texts), 'batch_size':16,
        'prediction_counts':{str(value):predictions.count(value) for value in range(4)},
        'fixture_predictions_match':None if advisories else True,
        'load_import_and_integrity_seconds':round(load_seconds, 4),
        'inference_total_seconds':round(sum(timings), 4),
        'batch_seconds':[round(value, 4) for value in timings],
        'first_inference_seconds':round(timings[0], 4),
        'warm_inference_seconds':None if advisories else round(timings[1], 4),
        'python_work_seconds':round(time.perf_counter() - started, 4),
        'process_peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        'cgroup_peak_bytes':int(peak_path.read_text()) if peak_path.exists() else None,
        'model_artifact_bytes':sum(row['bytes'] for row in manifest['model_files'].values()),
    }
    if advisories:
        lengths = sorted(len(text) for text in texts)
        report.update(input_sha256=hashlib.sha256(source_bytes).hexdigest(),
                      text_characters={'min':lengths[0], 'median':lengths[len(lengths)//2], 'max':lengths[-1]},
                      token_limit=256, mode='full_advisories')
    else:
        report['mode'] = 'synthetic_fixture'
    print('BENCHMARK_JSON=' + json.dumps(report))


def command(args):
    result = subprocess.run(args, text=True, capture_output=True, timeout=900)
    if result.returncode:
        raise RuntimeError(f'Benchmark command failed ({result.returncode}): {result.stderr}')
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inside', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--image', default='safetrip-iq-local-worker:latest')
    parser.add_argument('--output', help='New local JSON report path.')
    parser.add_argument('--advisories', help='Saved advisory JSON to benchmark once in batches of 16.')
    args = parser.parse_args()
    if args.inside:
        inside(args.advisories)
        return
    if not args.output:
        parser.error('--output is required')
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise ValueError('Choose an unused output filename.')
    extra_mounts, extra_args = [], []
    if args.advisories:
        source = Path(args.advisories).resolve(strict=True)
        # Parse before container startup; detailed validation also runs inside.
        if not isinstance(json.loads(source.read_bytes()), list):
            raise ValueError('Expected an advisory JSON list.')
        extra_mounts = ['--mount',f'type=bind,src={source},dst=/advisories.json,readonly']
        extra_args = ['--advisories','/advisories.json']
    image = json.loads(command(['docker','image','inspect',args.image]))[0]
    # Run the exact inspected image even if its tag later changes.
    image_id = image['Id']
    info = json.loads(command(['docker','info','--format','{{json .}}']))
    name = 'safetrip-benchmark-' + str(time.time_ns())
    common = ['docker','run','--rm','--name',name,'--platform','linux/amd64',
              '--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
              '--cpus','2','--memory','2g','--memory-swap','2g',
              '--tmpfs','/tmp:rw,size=268435456','--entrypoint','python']
    try:
        before = time.perf_counter()
        command(common + [image_id,'-c','print("ready")'])
        startup = time.perf_counter() - before
        before = time.perf_counter()
        result = command(common + extra_mounts + [
            '--mount',f'type=bind,src={ROOT / "results/checkpoint-189"},dst=/models/checkpoint-189,readonly',
            '--mount',f'type=bind,src={Path(__file__).resolve()},dst=/benchmark.py,readonly',
            '--env','HF_HOME=/tmp/huggingface',image_id,'/benchmark.py','--inside'] + extra_args)
        total = time.perf_counter() - before
        measured = json.loads(next(line.split('=',1)[1] for line in result.splitlines() if line.startswith('BENCHMARK_JSON=')))
    finally:
        # Also remove the container if a timeout interrupted docker run.
        subprocess.run(['docker','rm','-f',name], capture_output=True, timeout=30)
    report = {
        'measured_at_utc':datetime.now(timezone.utc).isoformat(),
        'image_id':image_id, 'docker_reported_image_bytes':image['Size'],
        'image_architecture':image['Architecture'], 'host_architecture':platform.machine(),
        'docker_architecture':info['Architecture'], 'docker_vm_cpus':info['NCPU'],
        'docker_vm_memory_bytes':info['MemTotal'], 'container_cpu_limit':2,
        'container_memory_limit_bytes':2147483648,
        'cached_image_start_and_exit_seconds':round(startup, 4),
        'inference_container_wall_seconds':round(total, 4), **measured,
        'limitations':['Historical full advisory batch; not current live guidance.' if args.advisories else 'Two short synthetic texts, not a representative full feed.',
                      'Image already local; no registry pull or model download measured.',
                      'amd64 on Apple Silicon uses emulation; remeasure on target AWS CPU.',
                      'RSS and cgroup peak measure different scopes; neither is a cloud sizing guarantee.',
                      'No ingestion, database writes, network, or training in this benchmark.'],
    }
    with output.open('x') as stream:
        json.dump(report,stream,indent=2)
        stream.write('\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()

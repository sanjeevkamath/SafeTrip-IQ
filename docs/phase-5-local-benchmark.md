# Stage 5 checkpoint 1: small local worker benchmark

Measured October 11, 2026 (America/New_York), using the existing Linux amd64 worker image on an Apple Silicon Mac. This is an initial local reference, not an AWS sizing result.

## What ran

The reusable `scripts/benchmark_worker.py` inspects the local image and pins its image ID for the run. It starts a minimal Python container, then a separate container that loads the verified BERT checkpoint and predicts the two synthetic regression texts twice. The second inference uses the already-loaded model.

Both containers use two CPUs, 2 GiB memory, disabled swap, no network, and a read-only root filesystem with a temporary `/tmp`. The inference container mounts the model and benchmark script read-only. It uses no database URL or publication command. Containers are removed after the measurement.

The regression classes matched `[0, 1]`. These are existing behavioral fixtures, not evidence of model accuracy.

## First successful measurement

| Measurement | Result |
| --- | ---: |
| Docker-reported image size | 293.3 MB |
| Separate model artifacts | 438.9 MB |
| Minimal container start, Python print, and exit | 0.60 s |
| Model/library loading and integrity checks | 20.18 s |
| First inference, two short texts | 0.45 s |
| Second inference, same loaded model | 0.10 s |
| Entire inference container run, including both predictions | 22.56 s |
| Python process peak resident memory | 753.1 MB |
| Container cgroup memory peak | 753.7 MB |

MB means decimal megabytes; the imposed 2 GiB limit is approximately 2,147 MB. Docker image size is the engine's reported value, not a measured registry transfer size or a guarantee of disk usage. Model artifacts are mounted separately and are not included in that image-size figure.

Most of this tiny run was spent loading the model and libraries, not making predictions. Loading the model once and processing a batch amortizes that cost. The memory result shows this fixture completed within the chosen limit; a full feed with longer texts and larger batches still needs measurement.

The image was already local, so no registry pull or model download was timed. The start/exit value includes Docker client and container lifecycle overhead; it is not pure kernel startup latency. Linux amd64 runs under emulation on this Mac. The process and cgroup peaks measure different scopes and are sampled/reported by different mechanisms. Host caching and contention can affect subsequent runs.

## Repeat it

With Docker running and the existing image/checkpoint available:

```sh
uv run --frozen python scripts/benchmark_worker.py \
  --output .local/benchmarks/worker-fixture-02.json
```

Use a new output filename for every run. The first report is `.local/benchmarks/worker-fixture-01.json`, including image identity, machine architecture, limits, and detailed timing. Reports remain ignored by Git. If the worker code changes, rebuild its image first with `docker compose build worker`.

## Next checkpoint

The full local advisory benchmark is now complete (below). Next, prepare AWS account access and credit/budget settings, then measure on the intended native AWS CPU architecture, including image/model downloads, before finalizing resources or estimating costs. This checkpoint creates no cloud resources and does not retrain the model.

## Full advisory batch method

The same benchmark accepts `--advisories` for a saved advisory JSON file. It validates the input and runs every description exactly once in batches of 16, matching the runtime worker. The 209 captured descriptions range from 93 to 8,943 characters, with a median of 954. Tokenization retains the existing 256-token limit; this is not a test of reading every character in a long advisory.

```sh
uv run --frozen python scripts/benchmark_worker.py \
  --advisories .local/baselines/20261008T032611470774Z/travel_advisories.json \
  --output .local/benchmarks/worker-full-02.json
```

The report contains the input hash, input count, per-batch timings, prediction class counts, and process/container memory peaks. It does not include advisory text or publish predictions. Unlike the small fixture, this data has no asserted ground-truth outputs: successful inference establishes operational completion, not model accuracy. The run computes all predictions, representing a refresh with no reusable BERT outputs; normal incremental refreshes may infer fewer rows.

The script allows at most 15 minutes per Docker command and cleans up its named container on timeout. CPU use around 200% means both allocated CPUs are busy. The memory limit is a cap, not memory preallocated to the model.

### Full-batch result

The first complete batch finished successfully under the same two-CPU, 2 GiB limit:

| Measurement | Result |
| --- | ---: |
| Advisories / batches | 209 / 14 |
| Model/library loading and integrity checks | 13.55 s |
| Inference across all batches | 193.59 s |
| Entire inference container run | 208.77 s (3 min 29 s) |
| Process peak resident memory | 1,019.7 MB |
| Container cgroup memory peak | 948.2 MB |

The source hash matches the reviewed captured advisory export. All 209 outputs were valid class IDs (83 class 0, 80 class 1, 26 class 2, 20 class 3). No accuracy claim or equality with historical published classes is inferred from this distribution. The complete report is `.local/benchmarks/worker-full-01.json`.

Process RSS and cgroup accounting report different scopes, especially under emulation; do not add their values or treat the smaller figure as exact peak host memory. Both measurements suggest roughly 1 GB for this workload, which completed within the imposed 2 GiB cap. This supports testing the same resource limits on native cloud hardware, not finalizing production sizing yet. The smaller loading time than the first synthetic run also illustrates cache and runtime variation between individual measurements.

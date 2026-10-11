"""Internal run records; successful publication and audit rows commit together."""
from datetime import datetime
import hashlib
import json
import sys
from uuid import UUID, uuid4


def encode(value):
    def convert(item):
        if isinstance(item, (datetime, UUID)):
            return str(item)
        raise TypeError("Unsupported audit value")
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False, default=convert)


class RunHistory:
    def __init__(self, engine):
        self.engine = engine
        self.active = None
        self.last = None

    def start(self, command):
        from sqlalchemy import text
        if self.active is not None:
            raise ValueError("A run is already active.")
        run_id = uuid4()
        with self.engine.begin() as conn:
            conn.execute(text("""INSERT INTO public.pipeline_runs (run_id, command, status)
                VALUES (:id, :command, 'running')"""), {"id":run_id, "command":command})
        self.active = self.last = run_id
        return run_id

    def record_input(self, artifact, metadata=None):
        from sqlalchemy import text
        payload = encode(artifact)
        digest = hashlib.sha256(payload.encode()).hexdigest()
        # A separate short transaction preserves attempted inputs on failure.
        with self.engine.begin() as conn:
            conn.execute(text("""UPDATE public.pipeline_runs
                SET input_payload=CAST(:payload AS jsonb), input_sha256=:digest,
                    metadata=CAST(:metadata AS jsonb)
                WHERE run_id=:id AND status='running'"""),
                {"payload":payload, "digest":digest, "metadata":encode(metadata or {}), "id":self.active})

    def succeeded(self, conn, coverage=None, published_rows=0):
        from sqlalchemy import text
        conn.execute(text("""UPDATE public.pipeline_runs SET status='succeeded',
            finished_at=clock_timestamp(), coverage=CAST(:coverage AS jsonb), published_rows=:count
            WHERE run_id=:id AND status='running'"""),
            {"id":self.active, "coverage":encode(coverage), "count":published_rows})

    def committed(self):
        self.active = None

    def failed(self, error):
        from sqlalchemy import text
        if self.active is None:
            return
        try:
            with self.engine.begin() as conn:
                # Never overwrite succeeded after an ambiguous commit response.
                conn.execute(text("""UPDATE public.pipeline_runs SET status='failed',
                    finished_at=clock_timestamp(), error_type=:error
                    WHERE run_id=:id AND status='running'"""),
                    {"id":self.active, "error":type(error).__name__})
        except Exception:
            # Network loss or process termination can leave a running record.
            print("Could not record failure status; the run may still show running.", file=sys.stderr)
        finally:
            self.active = None

    def recent(self):
        from sqlalchemy import text
        with self.engine.connect() as conn:
            return [dict(row) for row in conn.execute(text("""SELECT run_id::text, command, status,
                started_at::text, finished_at::text, metadata, input_sha256, coverage, published_rows, error_type
                FROM public.pipeline_runs ORDER BY started_at DESC, run_id DESC LIMIT 20""")).mappings()]

    def save_scores(self, conn, artifact):
        from sqlalchemy import text
        inputs = artifact["inputs"]
        for row in artifact["scores"]:
            conn.execute(text("""INSERT INTO public.score_history
                (run_id, iso3, safe_trip_score, bert_score, clustering_score, scoring_version, inputs)
                VALUES (:run_id, :iso3, :safe_trip_score, :bert_score, :clustering_score,
                        :version, CAST(:inputs AS jsonb))"""),
                {**row, "run_id":self.active, "version":artifact["scoring_version"],
                 "inputs":encode(inputs[row["iso3"]])})

"""Direct PostgreSQL batch writes with one transaction per publication.

Imports stay lazy so CLI help and lightweight tests need no database libraries.
"""
from datetime import datetime, timezone
from contextlib import contextmanager

TABLE_COLUMNS = {
    "culture": {"iso3", "cities", "cultural_safety_notes", "currency", "donts", "dos", "etiquette", "food", "greeting", "language", "overview", "religion"},
    "countries": {"iso3", "iso2", "name", "continent", "flag_url"},
    "clustering": {"iso3", "clustering_score", "ppi", "gpi", "gti", "pvi", "score_kind", "last_run_id"},
    "scores": {"iso3", "safe_trip_score", "bert_score", "clustering_score", "last_run_id", "published_at"},
    "bert_scores": {"iso3", "cleaned_text", "bert_score", "last_run_id"},
    "travel_advisories": {"iso3", "country_name", "country_code", "pub_date_raw",
                          "description_raw_html", "description_text", "last_fetched_at", "last_run_id"},
}

# Refresh owns a session lock from before fetching until publication finishes.
# Other cooperating writers also acquire this key during their transactions.
REFRESH_LOCK = 73481002
PUBLICATION_LOCK = 73481001


class ScorePublicationError(ValueError):
    """A controlled, credential-free message safe to show in the CLI."""


class PostgresPublisher:
    def __init__(self, url):
        from sqlalchemy import create_engine
        from sqlalchemy.engine import make_url
        from sqlalchemy.pool import NullPool
        parsed = make_url(url)
        if parsed.drivername != "postgresql+psycopg" or parsed.username != "safetrip_writer":
            raise ValueError("A PostgreSQL writer account and psycopg URL are required.")
        # A one-shot batch job needs one connection, not a long-lived pool.
        self.engine = create_engine(parsed, poolclass=NullPool, hide_parameters=True,
                                    connect_args={"connect_timeout": 5, "options": "-c statement_timeout=30000"})
        from safetrip.persistence.history import RunHistory
        self.history = RunHistory(self.engine)
        self._refresh_connection = None

    @property
    def last_run_id(self):
        return self.history.last

    def start_run(self, command):
        from sqlalchemy import text
        run_id = self.history.start(command)
        if command == "refresh":
            try:
                self._refresh_connection = self.engine.connect()
                acquired = self._refresh_connection.execute(
                    text("SELECT pg_try_advisory_lock(:key)"), {"key":REFRESH_LOCK}).scalar_one()
                self._refresh_connection.commit()
                if not acquired:
                    raise ScorePublicationError("Another refresh or publication is in progress; retry after it completes.")
            except BaseException as error:
                self.fail_run(error)
                raise
        return run_id

    def _release_refresh(self):
        if self._refresh_connection is not None:
            # NullPool closes the physical session, releasing its advisory lock.
            self._refresh_connection.close()
            self._refresh_connection = None

    @contextmanager
    def _transaction(self):
        if self._refresh_connection is None:
            with self.engine.begin() as conn:
                yield conn
        else:
            with self._refresh_connection.begin():
                yield self._refresh_connection

    def fail_run(self, error):
        try:
            self.history.failed(error)
        finally:
            self._release_refresh()

    def recent_runs(self):
        return self.history.recent()

    def refresh_status(self):
        from sqlalchemy import text
        with self.engine.connect() as conn:
            latest = conn.execute(text("""SELECT published_at::text, source_kind,
                published_at < now() - interval '48 hours' AS overdue
                FROM public.refresh_status WHERE singleton""")).mappings().one_or_none()
            overdue = conn.execute(text("""SELECT run_id::text, command, started_at::text
                FROM public.pipeline_runs WHERE status='running'
                AND started_at < now() - interval '1 hour' ORDER BY started_at""")).mappings().all()
        return {"last_publication":dict(latest) if latest else None,
                "overdue_running_attempts":[dict(row) for row in overdue],
                "refresh_threshold_hours":48, "running_threshold_hours":1}

    def retain_raw(self, content):
        from hashlib import sha256
        from sqlalchemy import text
        digest = sha256(content).hexdigest()
        with self.engine.begin() as conn:
            conn.execute(text("""INSERT INTO public.raw_feeds (run_id,sha256,content)
                VALUES (:id,:digest,:content)"""),
                {"id":self.history.active, "digest":digest, "content":content})
        return digest

    def cached_predictions(self):
        from sqlalchemy import text
        with self.engine.connect() as conn:
            return {row["iso3"]:dict(row) for row in conn.execute(text("""
                SELECT b.iso3,b.cleaned_text,b.bert_score,b.last_run_id::text,
                       r.metadata,r.status
                FROM public.bert_scores b LEFT JOIN public.pipeline_runs r ON r.run_id=b.last_run_id
            """)).mappings()}

    @staticmethod
    def _upsert(conn, table, rows):
        from sqlalchemy import text
        allowed = TABLE_COLUMNS[table]
        for row in rows:
            if "iso3" not in row or not set(row) <= allowed:
                raise ValueError("Unexpected publication columns.")
            columns = sorted(row)
            assignments = ", ".join(f"{key}=EXCLUDED.{key}" for key in columns if key != "iso3")
            conflict = f"DO UPDATE SET {assignments}" if assignments else "DO NOTHING"
            statement = text(f"INSERT INTO public.{table} ({', '.join(columns)}) "
                             f"VALUES ({', '.join(':' + key for key in columns)}) "
                             f"ON CONFLICT (iso3) {conflict}")
            conn.execute(statement, row)

    @staticmethod
    def _lock(conn):
        from sqlalchemy import text
        if not conn.execute(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": REFRESH_LOCK}).scalar_one():
            raise ScorePublicationError("Another refresh is in progress; retry after it completes.")
        if not conn.execute(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": PUBLICATION_LOCK}).scalar_one():
            raise ScorePublicationError("Another publication is in progress; retry after it completes.")

    @staticmethod
    def _calculate_scores(conn):
        from sqlalchemy import text
        from safetrip.scoring.legacy import legacy_safety_score
        if conn.execute(text("""SELECT EXISTS (
            SELECT 1 FROM public.scores s LEFT JOIN public.countries c ON c.iso3=s.iso3
            WHERE c.iso3 IS NULL)""")).scalar_one():
            raise ScorePublicationError("Published scores contain unknown countries; resolve them first.")
        components = conn.execute(text("""
            SELECT c.iso3, b.bert_score, k.clustering_score, k.score_kind,
                   to_jsonb(b) AS bert_input, to_jsonb(k) AS cluster_input,
                   to_jsonb(a) AS advisory_input, br.metadata AS bert_run_metadata,
                   kr.metadata AS cluster_run_metadata
            FROM public.countries c
            LEFT JOIN public.bert_scores b ON b.iso3=c.iso3
            LEFT JOIN public.clustering k ON k.iso3=c.iso3
            LEFT JOIN public.travel_advisories a ON a.iso3=c.iso3
            LEFT JOIN public.pipeline_runs br ON br.run_id=b.last_run_id
            LEFT JOIN public.pipeline_runs kr ON kr.run_id=k.last_run_id
            ORDER BY c.iso3
        """)).mappings().all()
        if not components:
            raise ScorePublicationError("Cannot publish an empty country catalog.")
        rows = []
        inputs = {}
        coverage = {"both": 0, "bert_only": 0, "clustering_only": 0, "neither": 0}
        for row in components:
            bert, cluster = row["bert_score"], row["clustering_score"]
            if cluster is not None and row["score_kind"] != "risk_tier":
                raise ScorePublicationError("Clustering values must be verified risk tiers before score publication.")
            try:
                value = legacy_safety_score(bert, cluster)
            except ValueError:
                raise ScorePublicationError("Stored score components are outside the supported class/tier ranges.") from None
            kind = ("both" if bert is not None and cluster is not None else
                    "bert_only" if bert is not None else
                    "clustering_only" if cluster is not None else "neither")
            coverage[kind] += 1
            rows.append({"iso3": row["iso3"], "bert_score": bert,
                         "clustering_score": cluster, "safe_trip_score": value})
            inputs[row["iso3"]] = {key:row[key] for key in (
                "bert_input", "cluster_input", "advisory_input", "bert_run_metadata", "cluster_run_metadata")}
        return {"scoring_version": "legacy-v1", "coverage": coverage, "scores": rows, "inputs": inputs}

    def _write_final_scores(self, conn, artifact):
        self.history.save_scores(conn, artifact)
        now = datetime.now(timezone.utc)
        self._upsert(conn, "scores", [{**row, "last_run_id":self.history.active, "published_at":now}
                                      for row in artifact["scores"]])

    def publish_scores(self, output_path, write=False):
        """Read current components and save a preview; optionally commit scores."""
        from safetrip.jobs import save_json
        if write and self.history.active is None:
            self.start_run("publish-scores")
        try:
            with self.engine.begin() as conn:
                self._lock(conn)
                artifact = self._calculate_scores(conn)
                if write:
                    self.history.record_input({"scores":artifact["scores"], "inputs":artifact["inputs"]},
                                              {"scoring_version":artifact["scoring_version"]})
                    artifact["run_id"] = str(self.history.active)
                save_json(output_path, artifact)
                if write:
                    self._write_final_scores(conn, artifact)
                    self.history.succeeded(conn, artifact["coverage"], len(artifact["scores"]))
            if write:
                self.history.committed()
        except BaseException as error:
            if write:
                self.fail_run(error)
            raise
        return artifact

    def publish(self, command, artifact, *, publish_scores=False, metadata=None):
        if command not in {"ingest", "score", "refresh", "seed-countries", "import-clusters"}:
            raise ValueError("Unsupported publication command.")
        if publish_scores and command not in {"score", "refresh"}:
            raise ValueError("Final scores can accompany only scoring or refresh.")
        if self.history.active is None:
            self.start_run(command)
        try:
            metadata = dict(metadata or {})
            if publish_scores:
                metadata["scoring_version"] = "legacy-v1"
            self.history.record_input(artifact, metadata)
            self._publish_transaction(command, artifact, publish_scores)
            self.history.committed()
        except BaseException as error:
            self.fail_run(error)
            raise
        finally:
            self._release_refresh()

    def import_baseline(self, tables, metadata):
        """Import a validated release only into an empty application database."""
        from sqlalchemy import text
        self.start_run("import-baseline")
        try:
            self.history.record_input(tables, {**metadata, "scoring_version":"legacy-v1"})
            with self.engine.begin() as conn:
                self._lock(conn)
                if any(conn.execute(text(f"SELECT EXISTS (SELECT 1 FROM public.{table})")).scalar_one()
                       for table in (*TABLE_COLUMNS, 'refresh_status')):
                    raise ScorePublicationError("Baseline import requires empty application tables; existing data was preserved.")
                for table in ('countries', 'culture', 'bert_scores', 'clustering', 'travel_advisories'):
                    rows = tables[table]
                    if table in {'bert_scores', 'clustering', 'travel_advisories'}:
                        rows = [{**row, 'last_run_id':self.history.active} for row in rows]
                    if table == 'clustering':
                        rows = [{**row, 'score_kind':'risk_tier'} for row in rows]
                    self._upsert(conn, table, rows)
                scores = self._calculate_scores(conn)
                expected = {row['iso3']:row for row in tables['scores']}
                for row in scores['scores']:
                    if row['iso3'] in expected and row != expected[row['iso3']]:
                        raise ScorePublicationError("Imported scores differ from the captured baseline.")
                self._write_final_scores(conn, scores)
                self.history.succeeded(conn, scores['coverage'], len(scores['scores']))
            self.history.committed()
            return scores['coverage']
        except BaseException as error:
            self.fail_run(error)
            raise

    def _publish_transaction(self, command, artifact, publish_scores):
        from sqlalchemy import text
        with self._transaction() as conn:
            self._lock(conn)
            if command == "refresh":
                from safetrip.jobs import validate_advisories
                validate_advisories(artifact["advisories"])
                incoming = {row["iso3"] for row in artifact["advisories"]}
                predictions = artifact["bert_scores"] + artifact.get("reused_bert_scores", [])
                predicted_ids = [row["iso3"] for row in predictions]
                if len(predicted_ids) != len(set(predicted_ids)) or set(predicted_ids) != incoming:
                    raise ScorePublicationError("Every incoming advisory must have exactly one new or reused prediction.")
                countries = set(conn.execute(text("SELECT iso3 FROM public.countries")).scalars())
                if not incoming <= countries:
                    raise ScorePublicationError("Advisory feed contains an unknown country; resolve the mapping first.")
                # Reject an outdated cache decision instead of silently publishing
                # a different component after another writer changed it.
                for reused in artifact.get("reused_bert_scores", []):
                    current = conn.execute(text("""SELECT iso3,cleaned_text,bert_score,last_run_id::text
                        FROM public.bert_scores WHERE iso3=:iso3 FOR UPDATE"""),
                        {"iso3":reused["iso3"]}).mappings().one_or_none()
                    if current is None or dict(current) != reused:
                        raise ScorePublicationError("A reused prediction changed during refresh; run refresh again.")
                if publish_scores:
                    import json
                    # A successful final refresh treats its feed as the complete
                    # advisory snapshot. Clearing and recalculation are atomic.
                    missing = sorted(countries - incoming)
                    cleared = {}
                    for table in ("travel_advisories", "bert_scores"):
                        cleared[table] = conn.execute(text(
                            f"DELETE FROM public.{table} WHERE NOT (iso3::text = ANY(:present))"),
                            {"present":sorted(incoming)}).rowcount
                    conn.execute(text("""UPDATE public.pipeline_runs SET metadata = metadata || CAST(:policy AS jsonb)
                        WHERE run_id=:id"""), {"id":self.history.active, "policy":json.dumps({
                            "missing_advisory_policy":"blank-v1", "missing_advisory_iso3":missing,
                            "missing_advisory_count":len(missing), "cleared_rows":cleared})})
            if command in {"ingest", "refresh"}:
                rows = artifact["advisories"] if command == "refresh" else artifact
                now = datetime.now(timezone.utc)
                self._upsert(conn, "travel_advisories", [{**row, "last_fetched_at": now, "last_run_id":self.history.active} for row in rows])
            if command in {"score", "refresh"}:
                rows = artifact["bert_scores"] if command == "refresh" else artifact
                countries = set(conn.execute(text("SELECT iso3 FROM public.countries")).scalars())
                if any(row["iso3"] not in countries for row in rows):
                    raise ValueError("Scored input contains an unknown country.")
                self._upsert(conn, "bert_scores", [{**row, "last_run_id":self.history.active} for row in rows])
            if command in {"seed-countries", "import-clusters"}:
                rows = ([{**row, "score_kind": "raw_cluster_id", "last_run_id":self.history.active} for row in artifact]
                        if command == "import-clusters" else artifact)
                self._upsert(conn, "countries" if command == "seed-countries" else "clustering", rows)
            if publish_scores:
                scores = self._calculate_scores(conn)
                self._write_final_scores(conn, scores)
                if command == "refresh":
                    conn.execute(text("""INSERT INTO public.refresh_status (singleton,published_at,source_kind)
                        SELECT true,clock_timestamp(),CASE WHEN metadata->>'source_kind' IN
                            ('state_department_feed','local_xml') THEN metadata->>'source_kind' ELSE 'unknown' END
                        FROM public.pipeline_runs WHERE run_id=:id
                        ON CONFLICT (singleton) DO UPDATE SET published_at=excluded.published_at,
                            source_kind=excluded.source_kind"""), {"id":self.history.active})
                self.history.succeeded(conn, scores["coverage"], len(scores["scores"]))
            else:
                self.history.succeeded(conn)

    def close(self):
        self._release_refresh()
        self.engine.dispose()

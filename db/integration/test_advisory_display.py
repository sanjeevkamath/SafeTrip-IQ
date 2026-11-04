"""Verify the actual database boundary used by the website advisory endpoint."""
import hashlib
import unittest
import uuid

import psycopg
from test_local_database import connect


class AdvisoryDisplayTests(unittest.TestCase):
    def test_latest_successful_observation_and_private_projection(self):
        with connect('admin') as conn:
            try:
                doc = uuid.uuid4()
                conn.execute("INSERT INTO advisory.documents(document_id,source,source_key) VALUES (%s,'us_state',%s)",
                             (doc, str(doc)))
                versions = []
                for day, status, level in [(1, 'succeeded', 1), (3, 'succeeded', 3),
                                            (4, 'failed', 4), (2, 'succeeded', 2)]:
                    run, version = uuid.uuid4(), uuid.uuid4()
                    payload = str(version).encode()
                    conn.execute("""INSERT INTO public.pipeline_runs(run_id,command,status,finished_at)
                        VALUES (%s,'display-test',%s,now())""", (run,status))
                    conn.execute("""INSERT INTO advisory.versions(version_id,document_id,source,
                        parser_version,content_sha256,raw_payload,source_url,us_level)
                        VALUES (%s,%s,'us_state','display-test',%s,%s,'https://travel.state.gov/example',%s)""",
                        (version,doc,hashlib.sha256(payload).hexdigest(),payload,level))
                    conn.execute("INSERT INTO advisory.coverage VALUES (%s,%s,'CAN','parts','Test region')",
                                 (uuid.uuid4(),version))
                    conn.execute("""INSERT INTO advisory.observations VALUES
                        (%s,%s,%s,%s::timestamptz)""", (run,doc,version,f'2026-01-0{day}T00:00:00Z'))
                    versions.append(version)
                conn.execute('SET LOCAL ROLE safetrip_reader')
                cursor=conn.execute("SELECT * FROM public.advisory_summaries WHERE document_id=%s",(doc,))
                columns=[c.name for c in cursor.description]
                rows=cursor.fetchall()
                self.assertEqual(len(rows),1)
                row=dict(zip(columns,rows[0]))
                self.assertEqual(row['version_id'],versions[1])
                self.assertEqual(row['us_level'],3)
                self.assertEqual(row['coverage_scope'],'parts')
                self.assertEqual(row['region_label'],'Test region')
                self.assertTrue({'raw_payload','metadata','input_payload','body'}.isdisjoint(columns))
                for statement in ['SELECT * FROM advisory.versions',
                                  'SELECT * FROM public.pipeline_runs',
                                  'DELETE FROM public.advisory_summaries WHERE false',
                                  'UPDATE public.advisory_summaries SET us_level=1 WHERE false']:
                    with self.subTest(statement=statement):
                        with self.assertRaises((psycopg.errors.InsufficientPrivilege,
                                                psycopg.errors.ObjectNotInPrerequisiteState)), conn.transaction():
                            conn.execute(statement)
            finally:
                conn.rollback()

    def test_view_granted_only_to_website_reader(self):
        with connect('admin') as conn:
            for role, expected in [('safetrip_reader',True),('safetrip_writer',False)]:
                actual=conn.execute("SELECT has_table_privilege(%s,'public.advisory_summaries','SELECT')",(role,)).fetchone()[0]
                self.assertEqual(actual,expected)
                for privilege in ['INSERT','UPDATE','DELETE','TRUNCATE']:
                    self.assertFalse(conn.execute("SELECT has_table_privilege(%s,'public.advisory_summaries',%s)",
                                                  (role,privilege)).fetchone()[0])
            self.assertFalse(conn.execute("""SELECT EXISTS (
                SELECT FROM pg_class c, LATERAL aclexplode(c.relacl) a
                WHERE c.oid='public.advisory_summaries'::regclass AND a.grantee=0
            )""").fetchone()[0])

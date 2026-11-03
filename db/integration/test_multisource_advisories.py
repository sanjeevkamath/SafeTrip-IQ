"""Local-only schema contracts: source identity, provenance, privacy and references."""
import hashlib
import uuid
import unittest

import psycopg
from psycopg import sql
from test_local_database import connect

TABLES = ('documents', 'versions', 'coverage', 'observations', 'paragraphs', 'analyses', 'evidence')


class MultisourceAdvisoryTests(unittest.TestCase):
    def setUp(self):
        self.conn = connect('writer')
        self.run = uuid.uuid4()
        self.conn.execute("INSERT INTO pipeline_runs(run_id,command,status) VALUES (%s,'schema-test','running')", (self.run,))

    def tearDown(self):
        self.conn.rollback()
        self.conn.close()

    def document(self, source='us_state', key=None):
        doc = uuid.uuid4()
        self.conn.execute('INSERT INTO advisory.documents(document_id,source,source_key) VALUES (%s,%s,%s)',
                          (doc,source,key or str(doc)))
        return doc

    def version(self, doc, source='us_state', payload=b'Original source bytes', level=2, flags=None, parser='test-v1'):
        version = uuid.uuid4()
        self.conn.execute('''INSERT INTO advisory.versions
            (version_id,document_id,source,parser_version,content_sha256,raw_payload,source_url,us_level,uk_alert_status)
            VALUES (%s,%s,%s,%s,%s,%s,'https://example.invalid/advisory',%s,%s)''',
            (version,doc,source,parser,hashlib.sha256(payload).hexdigest(),payload,level,flags))
        return version

    def test_sources_match_country_without_sharing_document_keys(self):
        documents = []
        for source,key in [('us_state','us-canada'),('uk_fcdo','uk-content-uuid')]:
            doc = self.document(source,key)
            documents.append(doc)
            version = self.version(doc,source,level=2 if source=='us_state' else None,
                                   flags=None if source=='us_state' else ['avoid_all_travel_to_parts'])
            self.conn.execute('''INSERT INTO advisory.coverage(coverage_id,version_id,iso3,scope)
                VALUES (%s,%s,'CAN','whole_country')''',(uuid.uuid4(),version))
        rows=self.conn.execute('''SELECT d.source,v.us_level,v.uk_alert_status FROM advisory.documents d
            JOIN advisory.versions v USING(document_id) JOIN advisory.coverage c USING(version_id)
            WHERE c.iso3='CAN' AND d.document_id=ANY(%s) ORDER BY d.source''', (documents,)).fetchall()
        self.assertEqual(rows,[('uk_fcdo',None,['avoid_all_travel_to_parts']),('us_state',2,None)])

    def test_unknown_flags_invalid_levels_and_source_mismatches_are_rejected(self):
        us=self.document(); uk=self.document('uk_fcdo')
        for kwargs in [dict(doc=us,level=5),dict(doc=us,level=None),
                       dict(doc=uk,source='uk_fcdo',level=None,flags=['unknown']),
                       dict(doc=uk,source='uk_fcdo',level=2,flags=[]),
                       dict(doc=us,source='uk_fcdo',level=None,flags=[])]:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(psycopg.IntegrityError), self.conn.transaction():
                    self.version(**kwargs)

    def test_repeat_fetch_preserves_version_but_adds_freshness_observation(self):
        doc=self.document();version=self.version(doc)
        second=uuid.uuid4()
        self.conn.execute("INSERT INTO pipeline_runs(run_id,command,status) VALUES (%s,'schema-test','running')",(second,))
        for run in [self.run,second]:
            self.conn.execute('''INSERT INTO advisory.observations(run_id,document_id,version_id,fetched_at)
                VALUES (%s,%s,%s,now())''',(run,doc,version))
        self.assertEqual(self.conn.execute('SELECT count(*) FROM advisory.observations WHERE document_id=%s',(doc,)).fetchone()[0],2)
        with self.assertRaises(psycopg.errors.UniqueViolation), self.conn.transaction():self.version(doc)
        self.version(doc,payload=b'Changed advice')
        self.assertEqual(self.conn.execute('SELECT count(*) FROM advisory.versions WHERE document_id=%s',(doc,)).fetchone()[0],2)
        with self.assertRaises(psycopg.errors.CheckViolation), self.conn.transaction():
            self.conn.execute('''INSERT INTO advisory.versions(version_id,document_id,source,parser_version,
                content_sha256,raw_payload,source_url,us_level) VALUES (%s,%s,'us_state','bad',%s,%s,'https://example.invalid',2)''',
                (uuid.uuid4(),doc,'0'*64,b'not that checksum'))

    def test_grouped_coverage_requires_explicit_regions_and_known_countries(self):
        version=self.version(self.document())
        for iso,scope,region in [('ZZZ','whole_country',None),('CAN','parts',None),('CAN','whole_country','Northern area')]:
            with self.assertRaises(psycopg.IntegrityError), self.conn.transaction():
                self.conn.execute('INSERT INTO advisory.coverage VALUES (%s,%s,%s,%s,%s)',(uuid.uuid4(),version,iso,scope,region))
        for iso in ['CAN','USA']:
            self.conn.execute('INSERT INTO advisory.coverage VALUES (%s,%s,%s,%s,%s)',(uuid.uuid4(),version,iso,'parts','Named region'))
        self.conn.execute('INSERT INTO advisory.coverage VALUES (%s,%s,NULL,%s,%s)',(uuid.uuid4(),version,'unresolved','Mapping review needed'))
        self.assertEqual(self.conn.execute('SELECT count(*) FROM advisory.coverage WHERE version_id=%s',(version,)).fetchone()[0],3)

    def test_evidence_must_reference_a_real_paragraph_of_its_analysis_version(self):
        doc=self.document();v1=self.version(doc);v2=self.version(doc,payload=b'New source')
        self.conn.execute("INSERT INTO advisory.paragraphs VALUES (%s,'safety',0,'Safety',NULL,'Kidnapping occurs.')",(v1,))
        self.conn.execute("INSERT INTO advisory.paragraphs VALUES (%s,'safety',0,'Safety',NULL,'Theft occurs.')",(v2,))
        analysis=uuid.uuid4()
        self.conn.execute('''INSERT INTO advisory.analyses(analysis_id,version_id,run_id,analyzer_version,input_sha256)
            VALUES (%s,%s,%s,'rules-v1',%s)''',(analysis,v1,self.run,'a'*64))
        for version,index in [(v1,99),(v2,0)]:
            with self.assertRaises(psycopg.errors.ForeignKeyViolation), self.conn.transaction():
                self.conn.execute("INSERT INTO advisory.evidence VALUES (%s,%s,'safety',%s,'kidnapping','unreviewed')",(analysis,version,index))
        self.conn.execute("INSERT INTO advisory.evidence VALUES (%s,%s,'safety',0,'kidnapping','unreviewed')",(analysis,v1))
        self.assertEqual(self.conn.execute('''SELECT p.body FROM advisory.evidence e JOIN advisory.paragraphs p
            USING(version_id,section_slug,paragraph_index) WHERE e.analysis_id=%s''',(analysis,)).fetchone()[0],'Kidnapping occurs.')

    def test_private_append_only_permissions_and_rls(self):
        with connect('reader') as reader:
            for table in TABLES:
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    reader.execute(sql.SQL('SELECT * FROM advisory.{}').format(sql.Identifier(table)))
                reader.rollback()
        for table in TABLES:
            for command in ['UPDATE advisory.{} SET '+('source=source' if table=='documents' else 'version_id=version_id')+' WHERE false',
                            'DELETE FROM advisory.{} WHERE false','TRUNCATE advisory.{}']:
                with self.assertRaises(psycopg.errors.InsufficientPrivilege), self.conn.transaction():
                    self.conn.execute(sql.SQL(command).format(sql.Identifier(table)))
        with connect('admin') as admin:
            for table in TABLES:
                row=admin.execute('SELECT relrowsecurity,pg_get_userbyid(relowner) FROM pg_class WHERE oid=%s::regclass',('advisory.'+table,)).fetchone()
                self.assertEqual(row,(True,'safetrip_migrator'))
            for role in ['safetrip_reader','safetrip_writer']:
                self.assertFalse(admin.execute("SELECT has_database_privilege(%s,'safetrip','CREATE')",(role,)).fetchone()[0])

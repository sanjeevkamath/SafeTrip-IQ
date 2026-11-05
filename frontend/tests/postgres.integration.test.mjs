import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import vm from 'node:vm'
import ts from 'typescript'

const require = createRequire(import.meta.url)
const root = fileURLToPath(new URL('../src/lib/server/', import.meta.url))
const localUrl = 'postgresql://safetrip_reader:reader_local_only@127.0.0.1:55432/safetrip'

// Execute the actual server modules against local Postgres. Only Next's
// server-only import marker is stubbed; pg and SQL are real.
function queries(env = {}) {
    const cache = new Map()
    const environment = { SAFETRIP_DB_BACKEND: 'postgres', SAFETRIP_DATABASE_URL: localUrl, ...env }
    function load(filename) {
        if (cache.has(filename)) return cache.get(filename)
        const exports = {}
        cache.set(filename, exports)
        const compiled = ts.transpileModule(readFileSync(filename, 'utf8'), {
            compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
        }).outputText
        vm.runInNewContext(compiled, {
            exports, URL, process: { env: environment }, console: { error() {} },
            require(name) {
                if (name === 'server-only') return {}
                if (name.startsWith('.')) return load(path.resolve(path.dirname(filename), name + '.ts'))
                return require(name)
            },
        })
        return exports
    }
    return load(path.join(root, 'queries.ts'))
}

test('real reader query returns seeded map/search data', async () => {
    const db = queries()
    assert.deepEqual((await db.listCountryScores()).map(r => [r.iso3, r.safe_trip_score]),
        [['CAN', 10], ['JPN', 10], ['USA', 6]])
    assert.equal((await db.listCountryScores('aNa'))[0].iso3, 'CAN')
    assert.equal((await db.listCountryScores("' OR true --")).length, 0)
    assert.equal((await db.listCountryScores('%')).length, 0)
    assert.equal((await db.listCountryScores('_')).length, 0)
})

test('advisory query preserves source boundaries and rejects unsupported hosted reads', async () => {
    const db = queries()
    assert.equal(await db.getCountryAdvisories('ZZZ'), null)
    assert.equal(await db.getCountryAdvisories("CAN' OR true --"), null)
    const result = await db.getCountryAdvisories('CAN')
    assert.equal(result.country.iso3, 'CAN')
    for (const source of ['us_state', 'uk_fcdo']) {
        const summary = result.sources[source]
        assert.equal(summary.status, summary.documents.length ? 'available' : 'not_available')
        for (const document of summary.documents) {
            assert.equal(document.source, source)
            assert.equal(document.iso3, 'CAN')
            assert.ok(['parts', 'whole_country'].includes(document.coverage_scope))
            for (const field of ['raw_payload', 'metadata', 'input_payload', 'body']) {
                assert.equal(Object.hasOwn(document, field), false)
            }
        }
    }
    await assert.rejects(queries({SAFETRIP_DB_BACKEND:'supabase'}).getCountryAdvisories('CAN'),
        { message: 'Travel data is temporarily unavailable.' })
})

test('dedicated advisory reader works alongside the legacy backend', async () => {
    const db = queries({SAFETRIP_DB_BACKEND:'supabase',SAFETRIP_ADVISORY_DATABASE_URL:localUrl})
    const result = await db.getCountryAdvisories('CAN')
    assert.equal(result.country.iso3,'CAN')
    assert.ok(result.sources.uk_fcdo)
})

test('scoring readiness uses only the reader and reports unpublished official fields', async () => {
    const status=await queries().getScoringStatus()
    assert.equal(status.supported_formula,'us-official-cluster-v1')
    assert.equal(status.regional_policy,'exclude')
    assert.equal(status.schema_ready,true)
    assert.equal(status.published_rows,0)
})

test('country details preserve missing country and missing optional data', async () => {
    const db = queries()
    assert.equal(await db.getCountryDetails('ZZZ'), null)
    assert.equal(await db.getCountryDetails("CAN' OR true --"), null)
    const canada = await db.getCountryDetails('CAN')
    assert.equal(canada.country.name, 'Canada')
    assert.equal(canada.score.safe_trip_score, 10)
    assert.match(canada.culture.overview, /Synthetic/)
    const usa = await db.getCountryDetails('USA')
    assert.equal(usa.culture, null)
    assert.equal(usa.score.bert_score, null)
})

test('failed postgres configuration/connection does not fall back to Supabase', async () => {
    for (const env of [
        { SAFETRIP_DATABASE_URL: '' },
        { SAFETRIP_DATABASE_URL: localUrl.replace(':55432/', ':1/') },
        { SAFETRIP_DATABASE_URL: localUrl.replace('safetrip_reader:', 'safetrip_admin:') },
        { SAFETRIP_DB_BACKEND: 'typo' },
    ]) {
        await assert.rejects(queries(env).listCountryScores(), { message: 'Travel data is temporarily unavailable.' })
        await assert.rejects(queries(env).getRefreshStatus(), { message: 'Travel data is temporarily unavailable.' })
    }
})

test('development seeds have no verified refresh time; legacy backend reports unknown', async () => {
    assert.equal(await queries().getRefreshStatus(), null)
    assert.equal(await queries({ SAFETRIP_DB_BACKEND: 'supabase' }).getRefreshStatus(), null)
})

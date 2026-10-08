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
    }
})

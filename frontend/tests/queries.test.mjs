import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'

// Exercise the real query module with controlled database responses; no network.
const source = readFileSync(new URL('../src/lib/server/supabase-queries.ts', import.meta.url), 'utf8')
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText
function queries(responses) {
    const exports = {}
    const db = { from(table) {
        const response = responses[table]
        assert.ok(response, `Unexpected table ${table}`)
        const request = {
            select() { return this }, ilike() { return this }, limit() { return this },
            in() { return this }, eq() { return this }, returns() { return this },
            maybeSingle() { return Promise.resolve(response) },
            then(resolve, reject) { return Promise.resolve(response).then(resolve, reject) },
        }
        return request
    } }
    vm.runInNewContext(compiled, {
        exports, process: {env: {}}, console: {error() {}},
        require(name) {
            if (name === 'server-only') return {}
            if (name === '@supabase/supabase-js') return {createClient: () => db}
            throw new Error(`Unexpected import: ${name}`)
        },
    })
    return exports
}
const country = {iso3:'CAN', iso2:'CA', name:'Canada', continent:'North America', flag_url:null}
test('missing country is represented separately from failed database access', async () => {
    assert.equal(await queries({countries:{data:null,error:null}}).getCountryDetails('ZZZ'), null)
    await assert.rejects(queries({countries:{data:null,error:{code:'08006'}}}).getCountryDetails('CAN'), /temporarily unavailable/)
})
test('missing optional score/culture retains a real country', async () => {
    const result = await queries({countries:{data:country,error:null}, scores:{data:null,error:null}, culture:{data:null,error:null}}).getCountryDetails('CAN')
    assert.equal(result.country.name, 'Canada')
    assert.equal(result.score, null)
})
test('score and culture failures are not disguised as missing optional data', async () => {
    for (const table of ['scores','culture']) {
        const responses = {countries:{data:country,error:null}, scores:{data:null,error:null}, culture:{data:null,error:null}}
        responses[table].error = {code:'08006'}
        await assert.rejects(queries(responses).getCountryDetails('CAN'), /temporarily unavailable/)
    }
})
test('list keeps missing scores null but propagates failed score queries', async () => {
    const result = await queries({countries:{data:[country],error:null},scores:{data:[],error:null}}).listCountryScores()
    assert.equal(result[0].safe_trip_score, null)
    await assert.rejects(queries({countries:{data:[country],error:null},scores:{data:null,error:{code:'08006'}}}).listCountryScores(), /temporarily unavailable/)
})

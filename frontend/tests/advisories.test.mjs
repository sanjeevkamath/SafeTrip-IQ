import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import vm from 'node:vm'
import ts from 'typescript'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

const require = createRequire(import.meta.url)
function load(path, mocks = {}, env = {}) {
    const exports = {}
    const code = ts.transpileModule(readFileSync(new URL(path, import.meta.url), 'utf8'), {
        compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX },
    }).outputText
    vm.runInNewContext(code, { exports, URL, console: {error() {}}, process: {env}, require(name) {
        if (Object.hasOwn(mocks,name)) return mocks[name]
        return name === 'server-only' ? {} : require(name)
    } })
    return exports
}
const Component = load('../src/components/OfficialAdvisories.tsx').default
const ScoreBreakdown = load('../src/components/SafetyScoreDetails.tsx').default
const {advisoryPoolOptions} = load('../src/lib/server/advisory-reader.ts')
const document = {iso3:'PSE',document_id:'one',version_id:'v1',source:'us_state',
    source_url:'https://travel.state.gov/example',source_public_updated_at:'2026-11-01T12:00:00Z',
    fetched_at:'2026-11-04T12:00:00Z',us_level:4,uk_alert_status:null,
    coverage_scope:'parts',region_label:'Gaza'}
const data = (us, uk) => ({us_state:{documents:us},uk_fcdo:{documents:uk}})
const render = sources => renderToStaticMarkup(createElement(Component, {sources}))

test('regional US and multiple UK restrictions remain distinct with dates and links', () => {
    const html = render(data([document],[{...document,version_id:'v2',source:'uk_fcdo',
        source_url:'https://www.gov.uk/foreign-travel-advice/palestine',us_level:null,
        uk_alert_status:['avoid_all_travel_to_parts','avoid_all_but_essential_travel_to_parts']}]))
    for (const text of ['Regional advice: Gaza','Level 4: Do not travel','Against all travel to certain areas',
        'Against all but essential travel to certain areas','Retrieved:','UTC','https://www.gov.uk/']) {
        assert.ok(html.includes(text), text)
    }
})

test('empty flags, missing source, failure, and unavailable flags are distinct', () => {
    const uk = {...document,source:'uk_fcdo',source_url:'https://www.gov.uk/example',uk_alert_status:[]}
    const html = render(data([],[uk]))
    assert.match(html,/No imported advice is available/)
    assert.match(html,/No travel-restriction flags recorded/)
    assert.match(html,/Other risks and guidance may still apply/)
    assert.match(render(null),/temporarily unavailable/)
    assert.match(render(data([],[{...uk,uk_alert_status:null}])),/Warning status not provided/)
})

test('multiple documents survive rendering and unsafe source links are excluded', () => {
    const html = render(data([document,{...document,version_id:'v3',region_label:'The West Bank',
        source_url:'https://travel.state.gov.evil.example/path',us_level:3}],[]))
    assert.match(html,/Multiple source documents apply/)
    assert.match(html,/Level 4:/); assert.match(html,/Level 3:/)
    assert.ok(!html.includes('evil.example'))
})

test('hosted reader connection requires exact role, session pooler and verified CA', () => {
    const url = 'postgresql://safetrip_reader.example@aws-0-us-east-2.pooler.supabase.com:5432/postgres'
    const options = advisoryPoolOptions(url,'synthetic-ca')
    assert.equal(options.ssl.rejectUnauthorized,true)
    for (const invalid of [url.replace('safetrip_reader','safetrip_writer'),
        url.replace(':5432',':6543'),url+'?sslmode=require',url.replace('.pooler.supabase.com','.example.com')]) {
        assert.throws(() => advisoryPoolOptions(invalid,'synthetic-ca'))
    }
    assert.throws(() => advisoryPoolOptions(url))
    assert.equal(advisoryPoolOptions('postgresql://safetrip_reader@127.0.0.1:55432/test').ssl,undefined)
})

test('affected areas preserve official exceptions, escape text, and have an honest fallback', () => {
    const uk={...document,source:'uk_fcdo',source_url:'https://www.gov.uk/example',
        uk_alert_status:['avoid_all_but_essential_travel_to_parts'],warning_excerpts:[{
            version_id:'v1',extractor_version:'uk-warning-areas-v1',section_slug:'warnings-and-insurance',
            paragraph_index:2,warning_heading:'Areas where FCDO advises against all but essential travel',
            heading:'Border province',body:'Within 1km, except official border crossings. <script>unsafe()</script>',
        }]}
    const html=render(data([],[uk]))
    assert.match(html,/<details/)
    assert.match(html,/Affected areas/)
    assert.match(html,/Within 1km, except official border crossings/)
    assert.match(html,/&lt;script&gt;/)
    assert.ok(!html.includes('<script>unsafe()'))
    assert.match(render(data([],[{...uk,warning_excerpts:[]}])),/Affected areas could not be listed/)
    assert.match(render(data([],[{...uk,warning_excerpts:null}])),/Affected areas could not be listed/)
    assert.ok(!render(data([],[{...uk,uk_alert_status:[]}])).includes('<details'))
})

test('optional excerpt failure retains official warnings and filters excerpts by exact version', async () => {
    for (const fail of [false,true]) {
        const uk={...document,iso3:'CAN',source:'uk_fcdo',uk_alert_status:['avoid_all_travel_to_parts']}
        const db={async query(sql) {
            if (sql.includes('FROM public.countries')) return {rows:[{iso3:'CAN',name:'Canada'}]}
            if (sql.includes('FROM public.advisory_summaries')) return {rows:[uk]}
            if (sql.includes('FROM public.advisory_warning_excerpts')) {
                if(fail) throw new Error('Synthetic unavailable optional projection')
                return {rows:[{version_id:'v1',body:'Current official wording'}, {version_id:'old',body:'Old wording'}]}
            }
            throw new Error('Unexpected query')
        }}
        const api=load('../src/lib/server/postgres-queries.ts',{'./advisory-reader':{advisoryReader:()=>db}},
            {SAFETRIP_ADVISORY_DATABASE_URL:'synthetic-reader'})
        const result=await api.getCountryAdvisories('CAN')
        assert.equal(result.sources.uk_fcdo.documents.length,1)
        const excerpts=result.sources.uk_fcdo.documents[0].warning_excerpts
        if(fail) assert.equal(excerpts,null)
        else { assert.equal(excerpts.length,1);assert.equal(excerpts[0].body,'Current official wording') }
    }
})

test('official score breakdown never labels historical BERT as a production component', () => {
    const renderScore=props=>renderToStaticMarkup(createElement(ScoreBreakdown,{bertScore:3,clusteringScore:2,...props}))
    const html=renderScore({scoringVersion:'us-official-cluster-v1',officialUSLevel:2,
        officialUSComponent:7.5,clusteringComponent:6})
    assert.match(html,/Official US advisory/);assert.match(html,/7\.50/);assert.match(html,/6\.00/)
    assert.match(html,/Equal-weight average/);assert.ok(!html.includes('BERT Score'))
    const single=renderScore({scoringVersion:'us-official-cluster-v1',clusteringComponent:6})
    assert.match(single,/one available component/);assert.ok(!single.includes('Official US advisory'))
    const severe=renderScore({scoringVersion:'us-official-cluster-v1',officialUSLevel:4,officialUSComponent:2.5})
    assert.ok(severe.indexOf('Do not travel')<severe.indexOf('<details'))
    assert.match(renderScore({scoringVersion:'unavailable'}),/methodology is temporarily unavailable/)
    assert.match(renderScore({}),/BERT Score/)
})

test('legacy Supabase country read overlays current score methodology and fails honestly', async () => {
    const base={country:{iso3:'CAN',name:'Canada'},score:{iso3:'CAN',safe_trip_score:10,bert_score:0,clustering_score:0},culture:null}
    for (const fail of [false,true]) {
        const api=load('../src/lib/server/queries.ts',{
            './supabase-queries':{getCountryDetails:async()=>base},
            './postgres-queries':{getPublishedScore:async()=>{
                if(fail)throw new Error('Synthetic methodology failure')
                return {...base.score,scoring_version:'us-official-cluster-v1',official_us_level:1}
            }},
        },{SAFETRIP_DB_BACKEND:'supabase',SAFETRIP_ADVISORY_DATABASE_URL:'synthetic-reader'})
        const result=await api.getCountryDetails('CAN')
        assert.equal(result.score.scoring_version,fail?'unavailable':'us-official-cluster-v1')
    }
})

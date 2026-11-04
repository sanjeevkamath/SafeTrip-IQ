import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import vm from 'node:vm'
import ts from 'typescript'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

const require = createRequire(import.meta.url)
function load(path) {
    const exports = {}
    const code = ts.transpileModule(readFileSync(new URL(path, import.meta.url), 'utf8'), {
        compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX },
    }).outputText
    vm.runInNewContext(code, { exports, URL, process: {env: {}}, require(name) {
        return name === 'server-only' ? {} : require(name)
    } })
    return exports
}
const Component = load('../src/components/OfficialAdvisories.tsx').default
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

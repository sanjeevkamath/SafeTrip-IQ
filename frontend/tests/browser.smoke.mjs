import { before, after, test } from 'node:test'
import assert from 'node:assert/strict'
import { chromium } from 'playwright'

const base = process.env.SAFETRIP_BROWSER_URL ?? 'http://127.0.0.1:3001'
if (!['127.0.0.1', 'localhost'].includes(new URL(base).hostname)) throw new Error('Browser checks require a local fixture server.')
let browser
before(async () => { browser = await chromium.launch({ headless: true }) })
after(async () => { await browser?.close() })

async function withPage(run) {
    const context = await browser.newContext()
    try {
        await context.route('**/*', route => {
            const url = route.request().url()
            return new URL(url).origin === new URL(base).origin ? route.continue() : route.abort()
        })
        await run(await context.newPage())
    } finally { await context.close() }
}

async function selectCanadaFromSearch(page) {
    const search = page.getByRole('combobox', { name: 'Search a country' })
    await search.fill('Can')
    await page.getByRole('option', { name: /Canada/ }).waitFor()
    await search.press('ArrowDown')
    await search.press('Enter')
    return page.getByRole('region', { name: 'Country preview' })
}

test('keyboard search selects a real country and opens its guide', { timeout: 30000 }, async () => withPage(async page => {
    await page.goto(base)
    const preview = await selectCanadaFromSearch(page)
    await preview.getByRole('heading', { name: 'Canada', exact: true }).waitFor()
    await preview.getByText('10.0', { exact: true }).waitFor()
    await preview.getByRole('link', { name: 'View country guide' }).click()
    await page.waitForURL('**/country/CAN')
    await page.getByRole('heading', { name: 'Canada', exact: true }).waitFor()
    await page.getByText('10.0', { exact: true }).waitFor()
}))

test('globe drags, zooms in both directions, previews a country, and pins the preview', { timeout: 30000 }, async () => withPage(async page => {
    await page.goto(base)
    const globe = page.getByRole('group', { name: /^World globe/ })
    const canada = globe.locator('path[data-country="CAN"]')
    await canada.waitFor()
    const initialPath = await canada.getAttribute('d')
    const bounds = await globe.boundingBox()
    const x = bounds.x + bounds.width * 0.48
    const y = bounds.y + bounds.height * 0.42
    await page.mouse.move(x, y)
    await page.mouse.down()
    await page.mouse.move(x + 90, y + 40, { steps: 6 })
    await page.mouse.up()
    assert.notEqual(await canada.getAttribute('d'), initialPath)

    const transform = globe.locator('g[transform]').first()
    const zoom = () => transform.evaluate(element => Number(element.getAttribute('transform').match(/scale\(([^)]+)\)/)[1]))
    await page.mouse.wheel(0, 160)
    await page.waitForFunction(() => document.querySelector('svg[aria-label^="World globe"] g[transform]').getAttribute('transform').includes('scale(0.8)'))
    assert.equal(await page.getByRole('button', { name: 'Zoom out' }).isEnabled(), false)
    await page.mouse.wheel(0, -360)
    await page.waitForFunction(() => Number(document.querySelector('svg[aria-label^="World globe"] g[transform]')
        .getAttribute('transform').match(/scale\(([^)]+)\)/)[1]) > 1)
    const wheelZoom = await zoom()
    await page.getByRole('button', { name: 'Zoom in' }).click()
    assert.ok(await zoom() > wheelZoom)
    await page.getByRole('button', { name: 'Reset globe view' }).click()
    assert.equal(await zoom(), 1)
    assert.equal(await canada.getAttribute('d'), initialPath)
    const preview = await selectCanadaFromSearch(page)
    await preview.getByRole('heading', { name: 'Canada', exact: true }).waitFor()
    await preview.getByRole('button', { name: 'Clear selection' }).click()
    await page.getByRole('button', { name: 'Select Canada on the globe' }).hover()
    await preview.getByText('10.0', { exact: true }).waitFor()
    await preview.getByRole('button', { name: 'Keep this preview open' }).click()
    await preview.getByRole('link', { name: 'View country guide' }).waitFor()
    await page.getByRole('button', { name: 'Reset globe view' }).click()
    await page.getByRole('button', { name: 'Select Portugal on the globe' }).hover()
    await preview.getByRole('heading', { name: 'Portugal', exact: true }).waitFor()
    await page.getByRole('button', { name: 'SafeTrip IQ, reset view' }).hover()
    await preview.getByRole('heading', { name: 'Canada', exact: true }).waitFor()
}))

test('clustering-only country has no BERT score; unknown country is 404', { timeout: 30000 }, async () => withPage(async page => {
    await page.goto(base + '/country/USA')
    await page.getByText('6.0', { exact: true }).waitFor()
    await page.getByText('Score Breakdown', { exact: true }).click()
    await page.getByText(/^Clustering Score\b/).waitFor()
    assert.equal(await page.getByText(/^BERT Score\b/).count(), 0)
    assert.equal((await page.goto(base + '/country/ZZZ')).status(), 404)
}))

test('score and search failures are visible while the globe remains available', { timeout: 30000 }, async () => withPage(async page => {
    await page.route('**/api/countries-scores', route => route.fulfill({ status: 503, body: '{}' }))
    await page.route('**/api/search?*', route => route.fulfill({ status: 503, body: '{}' }))
    await page.goto(base)
    await page.getByRole('alert').filter({ hasText: 'Country scores are temporarily unavailable' }).waitFor()
    await page.getByRole('button', { name: 'Select Portugal on the globe' }).hover()
    await page.getByText('Score unavailable', { exact: true }).waitFor()
    await page.getByRole('combobox', { name: 'Search a country' }).fill('Can')
    await page.getByRole('alert').filter({ hasText: 'Search is temporarily unavailable' }).waitFor()
}))

test('freshness displays the latest recorded update and marks overdue refreshes', { timeout: 30000 }, async () => withPage(async page => {
    const health=await page.request.get(base+'/api/health')
    assert.equal(health.status(),503) // synthetic legacy seeds are never a fresh official publication
    assert.equal((await health.json()).healthy,false)
    assert.equal((await page.request.get(base+'/api/ready')).status(),200)
    await page.goto(base)
    const status = page.getByRole('status').filter({ hasText: 'Last updated at:' })
    await status.getByText('—', { exact: true }).waitFor()
    await page.route('**/api/refresh-status', route => route.fulfill({ contentType: 'application/json',
        body: JSON.stringify({ published_at: '2026-01-01T00:00:00Z', source_kind: 'local_xml', overdue: true }) }))
    await page.reload()
    await status.locator('time[datetime="2026-01-01T00:00:00.000Z"]').waitFor()
    await status.getByText('· refresh overdue', { exact: true }).waitFor()
    await page.unroute('**/api/refresh-status')
    await page.route('**/api/refresh-status', route => route.fulfill({contentType:'application/json',body:JSON.stringify({
        source_kind:'us_uk_official',published_at:'2026-11-01T00:00:00Z',score_published_at:'2026-10-20T00:00:00Z',
        overdue:false,score_overdue:true,refresh_threshold_hours:216,
    })}))
    await page.reload()
    await status.locator('time[datetime="2026-11-01T00:00:00.000Z"]').waitFor()
    await status.getByText('· refresh overdue', { exact: true }).waitFor()
    await page.unroute('**/api/refresh-status')
    await page.route('**/api/refresh-status', route => route.fulfill({ status: 503, body: '{}' }))
    await page.reload()
    await status.getByText('—', { exact: true }).waitFor()
}))

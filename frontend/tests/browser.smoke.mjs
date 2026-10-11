import { before, after, test } from 'node:test'
import assert from 'node:assert/strict'
import { chromium } from 'playwright'

const base = process.env.SAFETRIP_BROWSER_URL ?? 'http://127.0.0.1:3001'
if (!['127.0.0.1', 'localhost'].includes(new URL(base).hostname)) throw new Error('Browser checks require a local fixture server.')
let browser
before(async () => { browser = await chromium.launch({ headless: true }) })
after(async () => { await browser?.close() })

// Geometry is a synthetic Canada polygon; application data comes from real Postgres.
const geometry = { type: 'FeatureCollection', features: [{ type: 'Feature',
    properties: { ISO_A3: 'CAN', NAME: 'Canada' },
    geometry: { type: 'Polygon', coordinates: [[[-120,50],[-120,60],[-100,60],[-100,50],[-120,50]]] },
}] }
async function withPage(run) {
    const context = await browser.newContext()
    try {
        await context.route('**/*', route => {
            const url = route.request().url()
            if (url.startsWith('https://raw.githubusercontent.com/nvkelso/')) {
                return route.fulfill({ contentType: 'application/json', body: JSON.stringify(geometry) })
            }
            return new URL(url).origin === new URL(base).origin ? route.continue() : route.abort()
        })
        await run(await context.newPage())
    } finally { await context.close() }
}

test('search navigates to a real country and shows its score', { timeout: 30000 }, async () => withPage(async page => {
    await page.goto(base)
    await page.getByPlaceholder('Search for a country...').fill('Can')
    await page.locator('li').filter({ hasText: 'Canada' }).click()
    await page.waitForURL('**/country/CAN')
    await page.getByRole('heading', { name: 'Canada', exact: true }).waitFor()
    await page.getByText('10.0', { exact: true }).waitFor()
}))

test('map uses seeded scores, shows tooltip, and navigates', { timeout: 30000 }, async () => withPage(async page => {
    await page.goto(base)
    const country = page.locator('path.rsm-geography').first()
    await country.waitFor()
    assert.equal(await country.getAttribute('fill'), 'rgb(0, 128, 0)')
    await country.hover()
    await page.getByText('Safety Score: 10.0/10', { exact: true }).waitFor()
    await country.click()
    await page.waitForURL('**/country/CAN')
}))

test('clustering-only country has no BERT score; unknown country is 404', { timeout: 30000 }, async () => withPage(async page => {
    await page.goto(base + '/country/USA')
    await page.getByText('6.0', { exact: true }).waitFor()
    await page.getByRole('button', { name: 'Score Breakdown' }).click()
    await page.getByText('Clustering Score', { exact: true }).waitFor()
    assert.equal(await page.getByText('BERT Score', { exact: true }).count(), 0)
    assert.equal((await page.goto(base + '/country/ZZZ')).status(), 404)
}))

test('map and search failures remain visible to users', { timeout: 30000 }, async () => withPage(async page => {
    await page.route('**/api/countries-scores', route => route.fulfill({ status: 503, body: '{}' }))
    await page.route('**/api/search?*', route => route.fulfill({ status: 503, body: '{}' }))
    await page.goto(base)
    await page.getByRole('alert').filter({ hasText: 'Map data is temporarily unavailable' }).waitFor()
    await page.getByPlaceholder('Search for a country...').fill('Can')
    await page.getByRole('alert').filter({ hasText: 'Search is temporarily unavailable' }).waitFor()
}))

test('freshness distinguishes unknown, local overdue, and unavailable data', { timeout: 30000 }, async () => withPage(async page => {
    await page.goto(base)
    await page.getByRole('status').filter({ hasText: 'not yet available' }).waitFor()
    await page.route('**/api/refresh-status', route => route.fulfill({ contentType: 'application/json',
        body: JSON.stringify({ published_at: '2026-01-01T00:00:00Z', source_kind: 'local_xml', overdue: true }) }))
    await page.reload()
    await page.getByRole('status').filter({ hasText: /Local XML data refreshed:.*over 48 hours/ }).waitFor()
    await page.unroute('**/api/refresh-status')
    await page.route('**/api/refresh-status', route => route.fulfill({ status: 503, body: '{}' }))
    await page.reload()
    await page.getByRole('status').filter({ hasText: 'temporarily unavailable' }).waitFor()
}))

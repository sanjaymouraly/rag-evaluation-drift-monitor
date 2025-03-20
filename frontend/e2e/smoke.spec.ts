import { expect, test } from '@playwright/test'

/**
 * Smoke check: every route must render without a React error boundary.
 * Not part of the default suite; run with `npx playwright test e2e/smoke.spec.ts`.
 */
const ROUTES = [
  '/',
  '/runs',
  '/runs/new',
  '/runs/1',
  '/applications',
  '/datasets',
  '/metrics',
  '/compare',
  '/regressions',
  '/drift',
  '/gates',
  '/providers',
  '/evidence',
  '/reports',
  '/system',
  '/does-not-exist',
]

test('every route renders', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(`${page.url()} :: ${error.message}`))
  for (const route of ROUTES) {
    await page.goto(route)
    await page.waitForTimeout(700)
    const body = await page.locator('body').innerText()
    expect(body, `route ${route} rendered an error`).not.toContain('Unexpected Application Error')
    expect(errors.join('\n'), `page errors: ${errors.join('\n')}`).toBe('')
  }
})

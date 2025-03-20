import { expect, test } from '@playwright/test'

/**
 * End-to-end smoke tests for the RAG Quality Monitor dashboard.
 *
 * The selectors are deliberately resilient: they assert on roles, headings and
 * landmarks instead of exact metric values, so the specs survive data changes.
 */

test.describe('dashboard', () => {
  test('overview renders KPI cards, a trend chart and recent runs', async ({ page }) => {
    await page.goto('/')

    await expect(page.getByRole('heading', { name: 'Overview', level: 1 })).toBeVisible()

    const kpiSection = page.getByRole('region', { name: 'Key performance indicators' })
    await expect(kpiSection).toBeVisible()
    await expect(kpiSection.getByText('Projects', { exact: true })).toBeVisible()
    await expect(kpiSection.getByText('Runs', { exact: true })).toBeVisible()
    await expect(kpiSection.getByText('Open alerts', { exact: true })).toBeVisible()

    await expect(page.getByRole('heading', { name: 'Metric trend' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Recent runs' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Gate verdicts' })).toBeVisible()
  })

  test('runs page lists evaluation runs', async ({ page }) => {
    await page.goto('/runs')

    await expect(page.getByRole('heading', { name: 'Evaluation runs', level: 1 })).toBeVisible()
    const table = page.getByRole('table', { name: 'Evaluation runs' })
    await expect(table).toBeVisible()
    await expect(table.locator('tbody tr')).not.toHaveCount(0)

    await expect(page.getByLabel('Status')).toBeVisible()
    await expect(page.getByLabel('Application')).toBeVisible()
    await expect(page.getByLabel('Dataset')).toBeVisible()
  })

  test('run detail shows the aggregate metric table and results', async ({ page }) => {
    await page.goto('/runs')
    const firstRunLink = page.getByRole('table', { name: 'Evaluation runs' }).locator('tbody tr').first().getByRole('link')
    await firstRunLink.click()

    await expect(page.getByRole('heading', { name: /^Run #\d+$/ })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Aggregate metrics' })).toBeVisible()
    await expect(page.getByRole('table', { name: 'Aggregate metrics for this run' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Results' })).toBeVisible()
  })

  test('gate policies page lists policies and rules', async ({ page }) => {
    await page.goto('/gates')

    await expect(page.getByRole('heading', { name: 'Gate policies', level: 1 })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Policies', exact: true })).toBeVisible()
    await expect(page.getByRole('table', { name: 'Gate policies' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Evaluation history' })).toBeVisible()
  })

  test('providers page shows preset cards and the provider table', async ({ page }) => {
    await page.goto('/providers')

    await expect(page.getByRole('heading', { name: 'Providers', level: 1 })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Presets', exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Use this preset' }).first()).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Configured providers', exact: true })).toBeVisible()
  })

  test('navigating between pages keeps the sidebar usable', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('link', { name: 'Metrics' }).click()
    await expect(page.getByRole('heading', { name: 'Metric catalogue', level: 1 })).toBeVisible()

    await page.getByRole('link', { name: 'Datasets' }).click()
    await expect(page.getByRole('heading', { name: 'Datasets', level: 1 })).toBeVisible()
  })
})

import { test, expect } from '@playwright/test';

async function setupMessagesPage(page: import('@playwright/test').Page) {
  await page.addInitScript(() => {
    localStorage.setItem('access_token', 'mock-token-12345');
  });

  await page.route('**/api/v1/auth/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 1,
        username: 'admin',
        role: 'admin',
        is_active: true,
      }),
    });
  });

  await page.route('**/api/v1/areas*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [
          { id: 1, name: 'general', is_public: true },
          { id: 2, name: 'tech', is_public: true },
        ],
        total: 2,
      }),
    });
  });

  await page.route('**/api/v1/messages*', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: [
            {
              id: 1,
              area: 'general',
              area_name: 'general',
              sender_id: 'user123',
              sender_short_name: 'Mario',
              subject: 'Hello everyone',
              content: 'This is my first message on the BBS!',
              body: 'This is my first message on the BBS!',
              timestamp: '2026-01-17T10:00:00Z',
              created_at: '2026-01-17T10:00:00Z',
            },
            {
              id: 2,
              area: 'tech',
              area_name: 'tech',
              sender_id: 'user456',
              sender_short_name: 'Luigi',
              subject: null,
              content: 'Anyone know how to configure the radio?',
              body: 'Anyone know how to configure the radio?',
              timestamp: '2026-01-17T11:00:00Z',
              created_at: '2026-01-17T11:00:00Z',
            },
            {
              id: 3,
              area: 'general',
              area_name: 'general',
              sender_id: 'user789',
              sender_short_name: 'Peach',
              subject: 'Question',
              content: 'How do I send a private message?',
              body: 'How do I send a private message?',
              timestamp: '2026-01-17T12:00:00Z',
              created_at: '2026-01-17T12:00:00Z',
            },
          ],
          total: 3,
          page: 1,
          per_page: 20,
          pages: 1,
        }),
      });
    }
  });

  await page.route('**/api/v1/messages/*', async (route) => {
    if (route.request().method() === 'DELETE') {
      await route.fulfill({ status: 204 });
    }
  });

  await page.route('**/api/v1/messages/bulk-delete', async (route) => {
    const body = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success_count: body.ids.length,
        failed_count: 0,
        errors: [],
      }),
    });
  });
}

test.describe('Messages Page', () => {
  test.beforeEach(async ({ page }) => {
    await setupMessagesPage(page);
    await page.goto('/messages');
  });

  test('should display messages list', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /messages/i })).toBeVisible();
    await expect(page.getByText('Hello everyone')).toBeVisible();
    await expect(page.getByText(/configure the radio/i)).toBeVisible();
  });

  test('should display sender names', async ({ page }) => {
    await expect(page.getByText('Mario')).toBeVisible();
    await expect(page.getByText('Luigi')).toBeVisible();
    await expect(page.getByText('Peach')).toBeVisible();
  });

  test('should display area names in table', async ({ page }) => {
    // Area badges are shown in table cells
    const table = page.getByRole('table');
    await expect(table.locator('text=general').first()).toBeVisible();
    await expect(table.locator('text=tech')).toBeVisible();
  });

  test('should filter by area', async ({ page }) => {
    const areaSelect = page.locator('select').first();
    await areaSelect.selectOption('general');
    await page.getByRole('button', { name: /filter/i }).click();

    // URL should update with area param
    await expect(page).toHaveURL(/area=general/);
  });

  test('should search messages', async ({ page }) => {
    await page.getByPlaceholder(/search/i).fill('radio');
    await page.getByRole('button', { name: /filter/i }).click();

    await expect(page).toHaveURL(/search=radio/);
  });

  test('should open message details modal on view click', async ({ page }) => {
    // Click the view button (eye icon) on first message row
    const firstRow = page.locator('tbody tr').first();
    await firstRow.locator('button').first().click();

    await expect(page.getByRole('dialog')).toBeVisible();
  });

  test('should have checkboxes for bulk selection', async ({ page }) => {
    // Verify checkboxes exist in the table
    const checkboxes = page.locator('input[type="checkbox"]');
    await expect(checkboxes.first()).toBeVisible();
  });

  test('should show delete confirmation on trash click', async ({ page }) => {
    // Click delete button on first message row (last button in row)
    const firstRow = page.locator('tbody tr').first();
    await firstRow.locator('button').last().click();

    // Confirmation modal should appear
    await expect(page.getByRole('dialog')).toBeVisible();
  });

  test('should have select all checkbox in header', async ({ page }) => {
    // Header checkbox exists
    const headerCheckbox = page.locator('thead input[type="checkbox"]');
    await expect(headerCheckbox).toBeVisible();
  });
});

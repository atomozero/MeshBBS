import { test, expect } from '@playwright/test';

async function setupAreasPage(page: import('@playwright/test').Page) {
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
        is_superadmin: true,
      }),
    });
  });

  await page.route('**/api/v1/areas*', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: [
            {
              id: 1,
              name: 'general',
              description: 'General discussion',
              is_public: true,
              is_readonly: false,
              message_count: 500,
              created_at: '2026-01-01T00:00:00Z',
            },
            {
              id: 2,
              name: 'announcements',
              description: 'System announcements',
              is_public: true,
              is_readonly: true,
              message_count: 50,
              created_at: '2026-01-01T00:00:00Z',
            },
            {
              id: 3,
              name: 'tech',
              description: 'Technology discussions',
              is_public: true,
              is_readonly: false,
              message_count: 200,
              created_at: '2026-01-05T00:00:00Z',
            },
          ],
          total: 3,
        }),
      });
    } else if (route.request().method() === 'POST') {
      const body = route.request().postDataJSON();
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 4,
          name: body.name,
          description: body.description,
          is_public: body.is_public ?? true,
          is_readonly: body.is_readonly ?? false,
          message_count: 0,
          created_at: new Date().toISOString(),
        }),
      });
    }
  });

  await page.route('**/api/v1/areas/*', async (route) => {
    if (route.request().method() === 'DELETE') {
      await route.fulfill({ status: 204 });
    } else if (route.request().method() === 'PATCH') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 1,
          name: 'general',
          description: 'Updated description',
          is_public: true,
          is_readonly: false,
          message_count: 500,
        }),
      });
    }
  });
}

test.describe('Areas Page', () => {
  test.beforeEach(async ({ page }) => {
    await setupAreasPage(page);
    await page.goto('/areas');
  });

  test('should display areas page heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /areas/i })).toBeVisible();
  });

  test('should display areas table with data', async ({ page }) => {
    // Wait for table to load
    await expect(page.getByRole('table')).toBeVisible();

    // Check that table has rows with area data
    const table = page.getByRole('table');
    await expect(table.getByText('general', { exact: true })).toBeVisible();
    await expect(table.getByText('General discussion')).toBeVisible();
    await expect(table.getByText('announcements', { exact: true })).toBeVisible();
  });

  test('should show area visibility badges', async ({ page }) => {
    await expect(page.getByText('Public').first()).toBeVisible();
  });

  test('should show read-only badge', async ({ page }) => {
    await expect(page.getByText('Read-only')).toBeVisible();
  });

  test('should have create area button', async ({ page }) => {
    await expect(page.getByRole('button', { name: /create area/i })).toBeVisible();
  });

  test('should show action dropdown on row click', async ({ page }) => {
    // Click dropdown on first area row
    const row = page.locator('tr').filter({ hasText: 'general' });
    await row.locator('button').last().click();

    // Dropdown should show edit and delete options
    await expect(page.locator('text=Edit')).toBeVisible();
    await expect(page.locator('text=Delete')).toBeVisible();
  });

  test('should open edit modal from dropdown', async ({ page }) => {
    await page.locator('tr').filter({ hasText: 'general' }).locator('button').last().click();
    await page.locator('text=Edit').click();

    await expect(page.getByRole('dialog')).toBeVisible();
  });

  test('should open delete confirmation from dropdown', async ({ page }) => {
    await page.locator('tr').filter({ hasText: 'tech' }).locator('button').last().click();
    await page.locator('text=Delete').click();

    await expect(page.getByRole('dialog')).toBeVisible();
  });
});

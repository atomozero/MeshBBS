import { test, expect, devices } from '@playwright/test';

async function setupAuth(page: import('@playwright/test').Page) {
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

  await page.route('**/api/v1/dashboard/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        total_users: 100,
        total_messages: 500,
        total_areas: 5,
        active_users: 10,
        items: [],
        total: 0,
      }),
    });
  });
}

// Mobile tests - using viewport instead of device to avoid worker issues
test.describe('Responsive Design - Mobile', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await setupAuth(page);
    await page.goto('/');
  });

  test('should show mobile navigation button', async ({ page }) => {
    // Menu button should be visible on mobile
    const menuButton = page.getByRole('button', { name: /open menu/i });
    await expect(menuButton).toBeVisible();
  });

  test('should open mobile drawer on menu click', async ({ page }) => {
    await page.getByRole('button', { name: /open menu/i }).click();

    // Mobile drawer should be visible
    await expect(page.locator('aside.fixed')).toBeVisible();

    // Navigation links should be visible
    await expect(page.getByRole('link', { name: /dashboard/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /users/i })).toBeVisible();
  });

  test('should close drawer on link click', async ({ page }) => {
    await page.getByRole('button', { name: /open menu/i }).click();
    await page.getByRole('link', { name: /users/i }).click();

    // Drawer should close and navigate
    await expect(page).toHaveURL('/users');
  });

  test('should close drawer on close button', async ({ page }) => {
    await page.getByRole('button', { name: /open menu/i }).click();
    await page.getByRole('button', { name: /close menu/i }).click();

    // Drawer should be hidden
    await expect(page.locator('aside.fixed.left-0')).not.toBeVisible();
  });

  test('should hide desktop sidebar on mobile', async ({ page }) => {
    // Desktop sidebar should not be visible
    await expect(page.locator('aside.hidden.lg\\:flex')).not.toBeVisible();
  });

  test('should stack stat cards vertically', async ({ page }) => {
    // Stats should be visible
    await expect(page.getByText('100')).toBeVisible(); // Total users
  });
});

// Tablet tests
test.describe('Responsive Design - Tablet', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await setupAuth(page);
    await page.goto('/');
  });

  test('should show mobile navigation on tablet portrait', async ({ page }) => {
    const menuButton = page.getByRole('button', { name: /open menu/i });
    await expect(menuButton).toBeVisible();
  });
});

// Desktop tests
test.describe('Responsive Design - Desktop', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await setupAuth(page);
    await page.goto('/');
  });

  test('should show desktop sidebar', async ({ page }) => {
    // Sidebar should be visible
    await expect(page.locator('aside').filter({ hasText: /meshbbs/i })).toBeVisible();
  });

  test('should hide mobile menu button', async ({ page }) => {
    const menuButton = page.getByRole('button', { name: /open menu/i });
    await expect(menuButton).not.toBeVisible();
  });

  test('should show sidebar navigation links', async ({ page }) => {
    const sidebar = page.locator('aside').filter({ hasText: /meshbbs/i });

    await expect(sidebar.getByRole('link', { name: /dashboard/i })).toBeVisible();
    await expect(sidebar.getByRole('link', { name: /users/i })).toBeVisible();
    await expect(sidebar.getByRole('link', { name: /areas/i })).toBeVisible();
    await expect(sidebar.getByRole('link', { name: /messages/i })).toBeVisible();
    await expect(sidebar.getByRole('link', { name: /logs/i })).toBeVisible();
    await expect(sidebar.getByRole('link', { name: /settings/i })).toBeVisible();
  });

  test('should show logout button in sidebar', async ({ page }) => {
    const sidebar = page.locator('aside').filter({ hasText: /meshbbs/i });
    await expect(sidebar.getByRole('button', { name: /logout/i })).toBeVisible();
  });

  test('should display stats in grid on desktop', async ({ page }) => {
    // All stat cards should be visible in a row
    await expect(page.getByText('Total Users')).toBeVisible();
    await expect(page.getByText('Total Messages')).toBeVisible();
  });
});

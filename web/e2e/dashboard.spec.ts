import { test, expect } from '@playwright/test';

// Helper to mock authenticated state
async function loginAsAdmin(page: import('@playwright/test').Page) {
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
        display_name: 'Administrator',
        role: 'admin',
        is_active: true,
        is_superadmin: true,
      }),
    });
  });

  await page.route('**/api/v1/dashboard/stats', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        total_users: 142,
        total_messages: 1234,
        total_areas: 8,
        active_users: 23,
        users: { total: 142, active_24h: 23, banned: 5, muted: 2 },
        messages: { total: 1234, today: 45, week: 312 },
        areas: { total: 8, public: 6, readonly: 2 },
        private_messages: { total: 500, today: 10, unread: 5 },
        system: { uptime_seconds: 302400, db_size_bytes: 47408128, radio_connected: true },
        system_status: { meshtastic_connected: true, uptime: '3d 12h' },
      }),
    });
  });

  await page.route('**/api/v1/dashboard/activity*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [
          { id: 1, event_type: 'user_joined', description: 'New user joined', timestamp: new Date().toISOString() },
          { id: 2, event_type: 'message_posted', description: 'Message posted in #general', timestamp: new Date().toISOString() },
        ],
        total: 2,
      }),
    });
  });

  await page.route('**/api/v1/dashboard/chart*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
        datasets: [{ label: 'Messages', data: [10, 20, 15, 25, 30, 18, 22] }],
        period: '7d',
      }),
    });
  });

  await page.route('**/api/v1/dashboard/top-users*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [
          { user_id: 'abc123', short_name: 'Mario', message_count: 156 },
          { user_id: 'def456', short_name: 'Luigi', message_count: 89 },
        ],
      }),
    });
  });
}

test.describe('Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto('/');
  });

  test('should display dashboard heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /dashboard/i })).toBeVisible();
  });

  test('should display stats cards', async ({ page }) => {
    // Look for stat card labels
    await expect(page.locator('text=Total Users')).toBeVisible();
    await expect(page.locator('text=Total Messages')).toBeVisible();
    await expect(page.locator('text=Active Areas')).toBeVisible();
  });

  test('should display activity chart section', async ({ page }) => {
    await expect(page.locator('text=Message Activity').first()).toBeVisible();
  });

  test('should have period buttons for chart', async ({ page }) => {
    await expect(page.getByRole('button', { name: '7d' })).toBeVisible();
    await expect(page.getByRole('button', { name: '30d' })).toBeVisible();
    await expect(page.getByRole('button', { name: '90d' })).toBeVisible();
  });

  test('should display top posters', async ({ page }) => {
    await expect(page.locator('text=Top Posters').first()).toBeVisible();
    await expect(page.getByText('Mario')).toBeVisible();
  });

  test('should display recent activity section', async ({ page }) => {
    await expect(page.locator('text=Recent Activity').first()).toBeVisible();
  });

  test('should display system status section', async ({ page }) => {
    await expect(page.locator('text=System Status').first()).toBeVisible();
  });

  test('should show connection indicator', async ({ page }) => {
    await expect(page.locator('text=Connected').first()).toBeVisible();
  });
});

test.describe('Dashboard Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto('/');
  });

  test('should navigate to users page', async ({ page }) => {
    await page.getByRole('link', { name: /users/i }).click();
    await expect(page).toHaveURL('/users');
  });

  test('should navigate to areas page', async ({ page }) => {
    await page.getByRole('link', { name: /areas/i }).click();
    await expect(page).toHaveURL('/areas');
  });

  test('should navigate to messages page', async ({ page }) => {
    await page.getByRole('link', { name: /messages/i }).click();
    await expect(page).toHaveURL('/messages');
  });

  test('should navigate to logs page', async ({ page }) => {
    await page.getByRole('link', { name: /logs/i }).click();
    await expect(page).toHaveURL('/logs');
  });

  test('should navigate to settings page', async ({ page }) => {
    await page.getByRole('link', { name: /settings/i }).click();
    await expect(page).toHaveURL('/settings');
  });
});

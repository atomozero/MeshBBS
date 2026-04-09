import { test, expect } from '@playwright/test';

// Helper to mock authenticated state and users data
async function setupUsersPage(page: import('@playwright/test').Page) {
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

  await page.route('**/api/v1/users*', async (route) => {
    const url = new URL(route.request().url());
    const search = url.searchParams.get('search') || '';

    const allUsers = [
      {
        public_key: 'abc123def456',
        short_name: 'Mario',
        long_name: 'Mario Rossi',
        nickname: 'mario',
        role: 'user',
        status: 'active',
        message_count: 156,
        first_seen: '2026-01-01T10:00:00Z',
        last_seen: '2026-01-17T14:00:00Z',
        is_admin: false,
        is_moderator: false,
        is_banned: false,
        is_muted: false,
      },
      {
        public_key: 'def456ghi789',
        short_name: 'Luigi',
        long_name: 'Luigi Verdi',
        nickname: 'luigi',
        role: 'moderator',
        status: 'active',
        message_count: 89,
        first_seen: '2026-01-05T10:00:00Z',
        last_seen: '2026-01-17T12:00:00Z',
        is_admin: false,
        is_moderator: true,
        is_banned: false,
        is_muted: false,
      },
      {
        public_key: 'ghi789jkl012',
        short_name: 'Spammer',
        long_name: 'Banned User',
        nickname: 'spammer',
        role: 'user',
        status: 'banned',
        message_count: 5,
        first_seen: '2026-01-10T10:00:00Z',
        last_seen: '2026-01-15T10:00:00Z',
        is_admin: false,
        is_moderator: false,
        is_banned: true,
        is_muted: false,
        ban_reason: 'Spam',
      },
    ];

    const filteredUsers = search
      ? allUsers.filter((u) => u.short_name.toLowerCase().includes(search.toLowerCase()))
      : allUsers;

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: filteredUsers,
        total: filteredUsers.length,
        page: 1,
        per_page: 20,
        pages: 1,
      }),
    });
  });
}

test.describe('Users Page', () => {
  test.beforeEach(async ({ page }) => {
    await setupUsersPage(page);
    await page.goto('/users');
  });

  test('should display users list', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /users/i })).toBeVisible();
    await expect(page.getByText('Mario')).toBeVisible();
    await expect(page.getByText('Luigi')).toBeVisible();
  });

  test('should display user roles in table', async ({ page }) => {
    const table = page.getByRole('table');
    await expect(table.locator('text=moderator')).toBeVisible();
    await expect(table.locator('text=user').first()).toBeVisible();
  });

  test('should display user status badges', async ({ page }) => {
    const table = page.getByRole('table');
    await expect(table.locator('text=active').first()).toBeVisible();
    await expect(table.locator('text=banned')).toBeVisible();
  });

  test('should filter users by search', async ({ page }) => {
    const searchInput = page.getByPlaceholder(/search/i);
    await searchInput.fill('Mario');
    await page.getByRole('button', { name: /filter/i }).click();

    await expect(page.getByText('Mario')).toBeVisible();
    await expect(page.getByText('Luigi')).not.toBeVisible();
  });

  test('should show user details modal', async ({ page }) => {
    const firstUserRow = page.locator('tr').filter({ hasText: 'Mario' });
    await firstUserRow.locator('button').last().click();

    await page.locator('text=View Details').click();

    await expect(page.getByRole('dialog')).toBeVisible();
  });

  test('should show action dropdown menu', async ({ page }) => {
    const firstUserRow = page.locator('tr').filter({ hasText: 'Mario' });
    await firstUserRow.locator('button').last().click();

    // Dropdown should show moderation options
    await expect(page.locator('text=View Details')).toBeVisible();
  });

  test('should show unban option for banned users', async ({ page }) => {
    await page.locator('tr').filter({ hasText: 'Spammer' }).locator('button').last().click();

    await expect(page.locator('text=Unban')).toBeVisible();
  });
});

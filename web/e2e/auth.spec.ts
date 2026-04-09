import { test, expect } from '@playwright/test';

test.describe('Authentication', () => {
  test('should display login page elements', async ({ page }) => {
    await page.goto('/login');

    // Check for heading with MeshBBS
    await expect(page.getByRole('heading', { name: 'MeshBBS Admin' })).toBeVisible();
    await expect(page.getByRole('button', { name: /sign in/i })).toBeVisible();

    // Check form fields
    await expect(page.locator('input[name="username"]')).toBeVisible();
    await expect(page.locator('input[name="password"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();
  });

  test('should have required form validation', async ({ page }) => {
    await page.goto('/login');

    // Check that inputs have required attribute
    const usernameInput = page.locator('input[name="username"]');
    await expect(usernameInput).toHaveAttribute('required');

    const passwordInput = page.locator('input[name="password"]');
    await expect(passwordInput).toHaveAttribute('required');
  });

  test('should show password field as password type', async ({ page }) => {
    await page.goto('/login');

    const passwordInput = page.locator('input[name="password"]');
    await expect(passwordInput).toBeVisible();
    await expect(passwordInput).toHaveAttribute('type', 'password');
  });

  test('should redirect to dashboard after login', async ({ page }) => {
    await page.route('**/api/v1/auth/login', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          access_token: 'mock-token-12345',
          refresh_token: 'mock-refresh-token',
          token_type: 'bearer',
          user: {
            id: 1,
            username: 'admin',
            role: 'admin',
            is_active: true,
          },
        }),
      });
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
          items: [],
          total: 0,
        }),
      });
    });

    await page.goto('/login');
    await page.locator('input[name="username"]').fill('admin');
    await page.locator('input[name="password"]').fill('password123');
    await page.locator('button[type="submit"]').click();

    await expect(page).toHaveURL('/');
  });

  test('should redirect to login when not authenticated', async ({ page }) => {
    await page.route('**/api/v1/auth/me', async (route) => {
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Not authenticated' }),
      });
    });

    await page.goto('/');

    await expect(page).toHaveURL('/login');
  });
});

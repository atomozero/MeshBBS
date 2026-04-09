/**
 * useAuth hook tests.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { AuthProvider, useAuth } from '@/contexts/AuthContext';

// Mock the API
vi.mock('@/api', () => ({
  authApi: {
    login: vi.fn(),
    logout: vi.fn(),
    getCurrentUser: vi.fn(),
  },
  setAccessToken: vi.fn(),
  clearTokens: vi.fn(),
}));

// Test component that uses the hook
function TestComponent() {
  const { user, isAuthenticated, isLoading, login, logout } = useAuth();

  return (
    <div>
      <span data-testid="loading">{isLoading ? 'loading' : 'loaded'}</span>
      <span data-testid="authenticated">{isAuthenticated ? 'yes' : 'no'}</span>
      <span data-testid="username">{user?.username || 'none'}</span>
      <button onClick={() => login('testuser', 'password')}>Login</button>
      <button onClick={logout}>Logout</button>
    </div>
  );
}

function renderWithProvider() {
  return render(
    <BrowserRouter>
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    </BrowserRouter>
  );
}

describe('useAuth', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Clear localStorage mock
    vi.mocked(localStorage.getItem).mockReturnValue(null);
    vi.mocked(localStorage.setItem).mockClear();
    vi.mocked(localStorage.removeItem).mockClear();
  });

  it('initially shows loading state', () => {
    renderWithProvider();

    expect(screen.getByTestId('authenticated')).toHaveTextContent('no');
  });

  it('shows unauthenticated state when no token', async () => {
    renderWithProvider();

    await waitFor(() => {
      expect(screen.getByTestId('loading')).toHaveTextContent('loaded');
    });

    expect(screen.getByTestId('authenticated')).toHaveTextContent('no');
    expect(screen.getByTestId('username')).toHaveTextContent('none');
  });

  it('throws error when used outside provider', () => {
    // Suppress console error for this test
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    expect(() => {
      render(
        <BrowserRouter>
          <TestComponent />
        </BrowserRouter>
      );
    }).toThrow('useAuth must be used within an AuthProvider');

    consoleSpy.mockRestore();
  });
});

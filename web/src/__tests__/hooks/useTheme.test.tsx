/**
 * useTheme hook and ThemeContext tests.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { ThemeProvider, useTheme } from '@/contexts/ThemeContext';

// Storage mock data
let mockStorage: Record<string, string> = {};

// Setup localStorage mock properly
beforeEach(() => {
  mockStorage = {};
  vi.mocked(localStorage.getItem).mockImplementation((key: string) => mockStorage[key] ?? null);
  vi.mocked(localStorage.setItem).mockImplementation((key: string, value: string) => {
    mockStorage[key] = value;
  });
  vi.mocked(localStorage.removeItem).mockImplementation((key: string) => {
    delete mockStorage[key];
  });
  vi.mocked(localStorage.clear).mockImplementation(() => {
    mockStorage = {};
  });

  // Clear document classes
  document.documentElement.classList.remove('light', 'dark');
});

afterEach(() => {
  mockStorage = {};
  vi.clearAllMocks();
});

// Test component that uses the hook
function TestComponent() {
  const { theme, resolvedTheme, setTheme, toggleTheme } = useTheme();

  return (
    <div>
      <span data-testid="theme">{theme}</span>
      <span data-testid="resolved">{resolvedTheme}</span>
      <button onClick={() => setTheme('light')} data-testid="set-light">
        Light
      </button>
      <button onClick={() => setTheme('dark')} data-testid="set-dark">
        Dark
      </button>
      <button onClick={() => setTheme('system')} data-testid="set-system">
        System
      </button>
      <button onClick={toggleTheme} data-testid="toggle">
        Toggle
      </button>
    </div>
  );
}

function renderWithProvider(defaultTheme?: 'light' | 'dark' | 'system') {
  return render(
    <ThemeProvider defaultTheme={defaultTheme}>
      <TestComponent />
    </ThemeProvider>
  );
}

describe('useTheme', () => {
  it('uses system theme by default', () => {
    renderWithProvider();

    expect(screen.getByTestId('theme')).toHaveTextContent('system');
    expect(screen.getByTestId('resolved')).toHaveTextContent('light');
  });

  it('sets theme to light', async () => {
    renderWithProvider();

    await act(async () => {
      fireEvent.click(screen.getByTestId('set-light'));
    });

    expect(screen.getByTestId('theme')).toHaveTextContent('light');
    expect(screen.getByTestId('resolved')).toHaveTextContent('light');
    expect(mockStorage['meshbbs-theme']).toBe('light');
  });

  it('sets theme to dark', async () => {
    renderWithProvider();

    await act(async () => {
      fireEvent.click(screen.getByTestId('set-dark'));
    });

    expect(screen.getByTestId('theme')).toHaveTextContent('dark');
    expect(screen.getByTestId('resolved')).toHaveTextContent('dark');
    expect(mockStorage['meshbbs-theme']).toBe('dark');
  });

  it('toggles theme from light to dark', async () => {
    mockStorage['meshbbs-theme'] = 'light';
    renderWithProvider();

    await act(async () => {
      fireEvent.click(screen.getByTestId('toggle'));
    });

    expect(screen.getByTestId('resolved')).toHaveTextContent('dark');
  });

  it('toggles theme from dark to light', async () => {
    mockStorage['meshbbs-theme'] = 'dark';
    renderWithProvider();

    await act(async () => {
      fireEvent.click(screen.getByTestId('toggle'));
    });

    expect(screen.getByTestId('resolved')).toHaveTextContent('light');
  });

  it('applies dark class to document', async () => {
    renderWithProvider();

    await act(async () => {
      fireEvent.click(screen.getByTestId('set-dark'));
    });

    expect(document.documentElement.classList.contains('dark')).toBe(true);
  });

  it('applies light class to document', async () => {
    renderWithProvider();

    await act(async () => {
      fireEvent.click(screen.getByTestId('set-light'));
    });

    expect(document.documentElement.classList.contains('light')).toBe(true);
  });

  it('persists theme to localStorage', async () => {
    renderWithProvider();

    await act(async () => {
      fireEvent.click(screen.getByTestId('set-dark'));
    });

    expect(mockStorage['meshbbs-theme']).toBe('dark');
  });

  it('reads theme from localStorage on mount', () => {
    mockStorage['meshbbs-theme'] = 'dark';
    renderWithProvider();

    expect(screen.getByTestId('theme')).toHaveTextContent('dark');
    expect(screen.getByTestId('resolved')).toHaveTextContent('dark');
  });

  it('throws error when used outside provider', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    expect(() => {
      render(<TestComponent />);
    }).toThrow('useTheme must be used within a ThemeProvider');

    consoleSpy.mockRestore();
  });
});

/**
 * ThemeToggle component tests.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { ThemeToggle, ThemeSelector } from '@/components/ui/ThemeToggle';
import { ThemeProvider } from '@/contexts/ThemeContext';

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

function renderWithProvider(component: React.ReactNode) {
  return render(<ThemeProvider defaultTheme="light">{component}</ThemeProvider>);
}

describe('ThemeToggle', () => {
  it('renders toggle button', () => {
    mockStorage['meshbbs-theme'] = 'light';
    renderWithProvider(<ThemeToggle />);

    expect(screen.getByRole('button')).toBeInTheDocument();
  });

  it('has correct aria-label for light theme', () => {
    mockStorage['meshbbs-theme'] = 'light';
    renderWithProvider(<ThemeToggle />);

    expect(screen.getByRole('button')).toHaveAttribute(
      'aria-label',
      'Switch to dark mode'
    );
  });

  it('toggles theme on click', async () => {
    mockStorage['meshbbs-theme'] = 'light';
    renderWithProvider(<ThemeToggle />);

    await act(async () => {
      fireEvent.click(screen.getByRole('button'));
    });

    expect(mockStorage['meshbbs-theme']).toBe('dark');
  });

  it('shows label when showLabel is true', () => {
    mockStorage['meshbbs-theme'] = 'light';
    renderWithProvider(<ThemeToggle showLabel />);

    expect(screen.getByText('light')).toBeInTheDocument();
  });

  it('hides label by default', () => {
    mockStorage['meshbbs-theme'] = 'light';
    renderWithProvider(<ThemeToggle />);

    expect(screen.queryByText('light')).not.toBeInTheDocument();
  });

  it('applies custom className', () => {
    mockStorage['meshbbs-theme'] = 'light';
    renderWithProvider(<ThemeToggle className="custom-class" />);

    expect(screen.getByRole('button')).toHaveClass('custom-class');
  });
});

describe('ThemeSelector', () => {
  it('renders all theme options', () => {
    mockStorage['meshbbs-theme'] = 'light';
    renderWithProvider(<ThemeSelector />);

    expect(screen.getByRole('button', { name: /light/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /dark/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /system/i })).toBeInTheDocument();
  });

  it('sets theme to light when Light button clicked', async () => {
    mockStorage['meshbbs-theme'] = 'dark';
    renderWithProvider(<ThemeSelector />);

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /light/i }));
    });

    expect(mockStorage['meshbbs-theme']).toBe('light');
  });

  it('sets theme to dark when Dark button clicked', async () => {
    mockStorage['meshbbs-theme'] = 'light';
    renderWithProvider(<ThemeSelector />);

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /dark/i }));
    });

    expect(mockStorage['meshbbs-theme']).toBe('dark');
  });

  it('sets theme to system when System button clicked', async () => {
    mockStorage['meshbbs-theme'] = 'light';
    renderWithProvider(<ThemeSelector />);

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /system/i }));
    });

    expect(mockStorage['meshbbs-theme']).toBe('system');
  });

  it('marks current theme as pressed', () => {
    mockStorage['meshbbs-theme'] = 'dark';
    renderWithProvider(<ThemeSelector />);

    expect(screen.getByRole('button', { name: /dark/i })).toHaveAttribute(
      'aria-pressed',
      'true'
    );
    expect(screen.getByRole('button', { name: /light/i })).toHaveAttribute(
      'aria-pressed',
      'false'
    );
  });

  it('applies custom className', () => {
    mockStorage['meshbbs-theme'] = 'light';
    const { container } = renderWithProvider(
      <ThemeSelector className="custom-class" />
    );

    expect(container.querySelector('.custom-class')).toBeInTheDocument();
  });
});

/**
 * ErrorBoundary component tests.
 */

import { describe, it, expect, vi, beforeEach, afterAll } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ErrorBoundary, ErrorFallback } from '@/components/error/ErrorBoundary';

// Component that throws an error
function ThrowError({ shouldThrow = true }: { shouldThrow?: boolean }) {
  if (shouldThrow) {
    throw new Error('Test error message');
  }
  return <div>Content rendered successfully</div>;
}

describe('ErrorBoundary', () => {
  // Suppress console.error for these tests since we're testing error handling
  const originalError = console.error;

  beforeEach(() => {
    console.error = vi.fn();
  });

  afterAll(() => {
    console.error = originalError;
  });

  it('renders children when there is no error', () => {
    render(
      <ErrorBoundary>
        <div>Test content</div>
      </ErrorBoundary>
    );

    expect(screen.getByText('Test content')).toBeInTheDocument();
  });

  it('renders error UI when child throws', () => {
    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    );

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
  });

  it('shows error message in development mode', () => {
    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    );

    // The error details should be visible in dev mode
    expect(screen.getByText(/Error Details/)).toBeInTheDocument();
    expect(screen.getByText('Test error message')).toBeInTheDocument();
  });

  it('renders custom fallback when provided', () => {
    render(
      <ErrorBoundary fallback={<div>Custom error UI</div>}>
        <ThrowError />
      </ErrorBoundary>
    );

    expect(screen.getByText('Custom error UI')).toBeInTheDocument();
    expect(screen.queryByText('Something went wrong')).not.toBeInTheDocument();
  });

  it('calls onError callback when error occurs', () => {
    const onError = vi.fn();

    render(
      <ErrorBoundary onError={onError}>
        <ThrowError />
      </ErrorBoundary>
    );

    expect(onError).toHaveBeenCalledTimes(1);
    expect(onError).toHaveBeenCalledWith(
      expect.any(Error),
      expect.objectContaining({ componentStack: expect.any(String) })
    );
  });

  it('shows Try Again button', () => {
    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    );

    expect(screen.getByRole('button', { name: /Try Again/i })).toBeInTheDocument();
  });

  it('shows Reload Page button', () => {
    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    );

    expect(screen.getByRole('button', { name: /Reload Page/i })).toBeInTheDocument();
  });

  it('shows Go Home button', () => {
    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    );

    expect(screen.getByRole('button', { name: /Go Home/i })).toBeInTheDocument();
  });
});

describe('ErrorFallback', () => {
  it('renders error message', () => {
    const error = new Error('Component error');
    const resetFn = vi.fn();

    render(<ErrorFallback error={error} resetErrorBoundary={resetFn} />);

    expect(screen.getByText('Error loading component')).toBeInTheDocument();
    expect(screen.getByText('Component error')).toBeInTheDocument();
  });

  it('calls resetErrorBoundary when Retry is clicked', () => {
    const error = new Error('Component error');
    const resetFn = vi.fn();

    render(<ErrorFallback error={error} resetErrorBoundary={resetFn} />);

    fireEvent.click(screen.getByRole('button', { name: /Retry/i }));

    expect(resetFn).toHaveBeenCalledTimes(1);
  });

  it('displays error styling', () => {
    const error = new Error('Test');
    const resetFn = vi.fn();

    const { container } = render(
      <ErrorFallback error={error} resetErrorBoundary={resetFn} />
    );

    // Check for red/error styling classes
    expect(container.firstChild).toHaveClass('bg-red-50');
  });
});

/**
 * Input component tests.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Input } from '@/components/ui/Input';

describe('Input', () => {
  it('renders with label', () => {
    render(<Input label="Username" name="username" />);
    expect(screen.getByLabelText('Username')).toBeInTheDocument();
  });

  it('handles value changes', () => {
    const handleChange = vi.fn();
    render(<Input name="test" onChange={handleChange} />);

    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'hello' } });

    expect(handleChange).toHaveBeenCalled();
  });

  it('shows error message', () => {
    render(<Input name="email" error="Invalid email" />);
    expect(screen.getByText('Invalid email')).toBeInTheDocument();
  });

  it('shows hint text', () => {
    render(<Input name="password" hint="Must be at least 8 characters" />);
    expect(screen.getByText('Must be at least 8 characters')).toBeInTheDocument();
  });

  it('does not show hint when error is present', () => {
    render(<Input name="test" error="Error" hint="Hint" />);

    expect(screen.getByText('Error')).toBeInTheDocument();
    expect(screen.queryByText('Hint')).not.toBeInTheDocument();
  });

  it('can be disabled', () => {
    render(<Input name="test" disabled />);

    const input = screen.getByRole('textbox');
    expect(input).toBeDisabled();
  });

  it('supports different types', () => {
    render(<Input name="email" type="email" />);

    const input = screen.getByRole('textbox');
    expect(input).toHaveAttribute('type', 'email');
  });

  it('renders with left icon', () => {
    render(
      <Input name="search" leftIcon={<span data-testid="left-icon">🔍</span>} />
    );

    expect(screen.getByTestId('left-icon')).toBeInTheDocument();
  });
});

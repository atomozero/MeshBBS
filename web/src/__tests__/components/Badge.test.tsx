/**
 * Badge component tests.
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Badge, StatusBadge, RoleBadge } from '@/components/ui/Badge';

describe('Badge', () => {
  it('renders with text', () => {
    render(<Badge>New</Badge>);
    expect(screen.getByText('New')).toBeInTheDocument();
  });

  it('applies variant styles', () => {
    const { rerender } = render(<Badge variant="success">Success</Badge>);
    expect(screen.getByText('Success')).toHaveClass('badge-success');

    rerender(<Badge variant="danger">Danger</Badge>);
    expect(screen.getByText('Danger')).toHaveClass('badge-danger');

    rerender(<Badge variant="warning">Warning</Badge>);
    expect(screen.getByText('Warning')).toHaveClass('badge-warning');
  });
});

describe('StatusBadge', () => {
  it('renders correct variant for active status', () => {
    render(<StatusBadge status="active" />);
    expect(screen.getByText('Active')).toHaveClass('badge-success');
  });

  it('renders correct variant for banned status', () => {
    render(<StatusBadge status="banned" />);
    expect(screen.getByText('Banned')).toHaveClass('badge-danger');
  });

  it('renders correct variant for muted status', () => {
    render(<StatusBadge status="muted" />);
    expect(screen.getByText('Muted')).toHaveClass('badge-warning');
  });

  it('handles unknown status', () => {
    render(<StatusBadge status="unknown" />);
    expect(screen.getByText('unknown')).toHaveClass('badge-default');
  });
});

describe('RoleBadge', () => {
  it('renders admin role', () => {
    render(<RoleBadge role="admin" />);
    expect(screen.getByText('Admin')).toHaveClass('badge-danger');
  });

  it('renders moderator role', () => {
    render(<RoleBadge role="moderator" />);
    expect(screen.getByText('Moderator')).toHaveClass('badge-warning');
  });

  it('renders user role', () => {
    render(<RoleBadge role="user" />);
    expect(screen.getByText('User')).toHaveClass('badge-default');
  });
});

import type { HTMLAttributes, ReactNode } from 'react';

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info';
  size?: 'sm' | 'md';
  children: ReactNode;
}

const variantStyles = {
  default: 'badge-default',
  success: 'badge-success',
  warning: 'badge-warning',
  danger: 'badge-danger',
  info: 'badge-info',
};

const sizeStyles = {
  sm: 'px-1.5 py-0.5 text-xs',
  md: 'px-2 py-1 text-xs',
};

export function Badge({
  variant = 'default',
  size = 'md',
  children,
  className = '',
  ...props
}: BadgeProps) {
  return (
    <span
      className={`${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
      {...props}
    >
      {children}
    </span>
  );
}

// Status-specific badges
export function StatusBadge({ status }: { status: string }) {
  const statusConfig: Record<string, { variant: BadgeProps['variant']; label: string }> = {
    active: { variant: 'success', label: 'Active' },
    online: { variant: 'success', label: 'Online' },
    offline: { variant: 'default', label: 'Offline' },
    banned: { variant: 'danger', label: 'Banned' },
    muted: { variant: 'warning', label: 'Muted' },
    kicked: { variant: 'warning', label: 'Kicked' },
    pending: { variant: 'info', label: 'Pending' },
    approved: { variant: 'success', label: 'Approved' },
    rejected: { variant: 'danger', label: 'Rejected' },
  };

  const config = statusConfig[status.toLowerCase()] || { variant: 'default', label: status };

  return <Badge variant={config.variant}>{config.label}</Badge>;
}

export function RoleBadge({ role }: { role: string }) {
  const roleConfig: Record<string, { variant: BadgeProps['variant']; label: string }> = {
    admin: { variant: 'danger', label: 'Admin' },
    moderator: { variant: 'warning', label: 'Moderator' },
    user: { variant: 'default', label: 'User' },
  };

  const config = roleConfig[role.toLowerCase()] || { variant: 'default', label: role };

  return <Badge variant={config.variant}>{config.label}</Badge>;
}

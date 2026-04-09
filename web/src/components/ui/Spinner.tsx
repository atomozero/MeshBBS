import { Loader2 } from 'lucide-react';

export interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const sizeStyles = {
  sm: 'w-4 h-4',
  md: 'w-6 h-6',
  lg: 'w-8 h-8',
};

export function Spinner({ size = 'md', className = '' }: SpinnerProps) {
  return (
    <Loader2
      className={`animate-spin text-primary-500 ${sizeStyles[size]} ${className}`}
      aria-hidden="true"
    />
  );
}

// Full page loading spinner
export function LoadingPage({ message = 'Loading...' }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
      <Spinner size="lg" />
      <p className="text-gray-500 dark:text-gray-400">{message}</p>
    </div>
  );
}

// Inline loading indicator
export function LoadingInline({ text = 'Loading...' }: { text?: string }) {
  return (
    <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400">
      <Spinner size="sm" />
      <span className="text-sm">{text}</span>
    </div>
  );
}

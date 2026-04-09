import clsx from 'clsx';

interface SkeletonProps {
  className?: string;
  variant?: 'text' | 'circular' | 'rectangular';
  width?: string | number;
  height?: string | number;
  animation?: 'pulse' | 'wave' | 'none';
}

export function Skeleton({
  className,
  variant = 'text',
  width,
  height,
  animation = 'pulse',
}: SkeletonProps) {
  const baseClasses = clsx(
    'bg-gray-200 dark:bg-gray-700',
    {
      'rounded': variant === 'text',
      'rounded-full': variant === 'circular',
      'rounded-lg': variant === 'rectangular',
      'animate-pulse': animation === 'pulse',
      'animate-shimmer': animation === 'wave',
    },
    className
  );

  const style: React.CSSProperties = {
    width: typeof width === 'number' ? `${width}px` : width,
    height: typeof height === 'number' ? `${height}px` : height,
  };

  if (variant === 'text' && !height) {
    style.height = '1em';
  }

  return <div className={baseClasses} style={style} />;
}

interface SkeletonTextProps {
  lines?: number;
  className?: string;
}

export function SkeletonText({ lines = 3, className }: SkeletonTextProps) {
  return (
    <div className={clsx('space-y-2', className)}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          variant="text"
          width={i === lines - 1 ? '75%' : '100%'}
        />
      ))}
    </div>
  );
}

export function SkeletonCard({ className }: { className?: string }) {
  return (
    <div className={clsx('card p-6 space-y-4', className)}>
      <div className="flex items-center gap-4">
        <Skeleton variant="circular" width={48} height={48} />
        <div className="flex-1 space-y-2">
          <Skeleton width="60%" height={16} />
          <Skeleton width="40%" height={12} />
        </div>
      </div>
      <SkeletonText lines={2} />
    </div>
  );
}

export function SkeletonTable({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div className="overflow-hidden">
      <table className="min-w-full">
        <thead>
          <tr className="border-b border-gray-200 dark:border-gray-700">
            {Array.from({ length: cols }).map((_, i) => (
              <th key={i} className="px-4 py-3">
                <Skeleton width="80%" height={14} />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: rows }).map((_, rowIndex) => (
            <tr key={rowIndex} className="border-b border-gray-100 dark:border-gray-800">
              {Array.from({ length: cols }).map((_, colIndex) => (
                <td key={colIndex} className="px-4 py-3">
                  <Skeleton
                    width={colIndex === 0 ? '90%' : `${60 + Math.random() * 30}%`}
                    height={14}
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function SkeletonStatCard() {
  return (
    <div className="card p-6">
      <div className="flex items-center justify-between">
        <div className="space-y-2 flex-1">
          <Skeleton width="60%" height={14} />
          <Skeleton width="40%" height={32} />
        </div>
        <Skeleton variant="circular" width={48} height={48} />
      </div>
      <div className="mt-4 pt-4 border-t border-gray-100 dark:border-gray-800">
        <Skeleton width="80%" height={12} />
      </div>
    </div>
  );
}

export function SkeletonChart() {
  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-4">
        <Skeleton width={150} height={20} />
        <div className="flex gap-2">
          <Skeleton width={40} height={32} variant="rectangular" />
          <Skeleton width={40} height={32} variant="rectangular" />
          <Skeleton width={40} height={32} variant="rectangular" />
        </div>
      </div>
      <div className="h-64 flex items-end justify-between gap-2">
        {Array.from({ length: 7 }).map((_, i) => (
          <div key={i} className="flex-1">
            <Skeleton
              variant="rectangular"
              height={`${30 + Math.random() * 70}%`}
              className="w-full"
            />
          </div>
        ))}
      </div>
    </div>
  );
}

export function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <Skeleton width={200} height={32} className="mb-2" />
        <Skeleton width={300} height={16} />
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {Array.from({ length: 4 }).map((_, i) => (
          <SkeletonStatCard key={i} />
        ))}
      </div>

      {/* Chart and Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <SkeletonChart />
        </div>
        <div className="card p-6 space-y-4">
          <Skeleton width={120} height={20} />
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex items-center gap-3">
              <Skeleton variant="circular" width={32} height={32} />
              <div className="flex-1 space-y-1">
                <Skeleton width="80%" height={14} />
                <Skeleton width="50%" height={12} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function TablePageSkeleton() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <Skeleton width={150} height={32} className="mb-2" />
          <Skeleton width={250} height={16} />
        </div>
        <Skeleton width={120} height={40} variant="rectangular" />
      </div>

      {/* Filters */}
      <div className="card p-4">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1">
            <Skeleton height={40} variant="rectangular" />
          </div>
          <div className="flex gap-2">
            <Skeleton width={120} height={40} variant="rectangular" />
            <Skeleton width={120} height={40} variant="rectangular" />
            <Skeleton width={80} height={40} variant="rectangular" />
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="card p-0 overflow-hidden">
        <SkeletonTable rows={10} cols={6} />
      </div>

      {/* Pagination */}
      <div className="flex justify-between items-center">
        <Skeleton width={150} height={16} />
        <div className="flex gap-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} width={40} height={40} variant="rectangular" />
          ))}
        </div>
      </div>
    </div>
  );
}

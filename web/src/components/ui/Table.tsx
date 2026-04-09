import type { ReactNode, HTMLAttributes } from 'react';

export interface TableProps extends HTMLAttributes<HTMLTableElement> {
  children: ReactNode;
}

export function Table({ children, className = '', ...props }: TableProps) {
  return (
    <div className="overflow-x-auto">
      <table className={`w-full text-sm ${className}`} {...props}>
        {children}
      </table>
    </div>
  );
}

export interface TableHeadProps extends HTMLAttributes<HTMLTableSectionElement> {
  children: ReactNode;
}

export function TableHead({ children, className = '', ...props }: TableHeadProps) {
  return (
    <thead
      className={`bg-gray-50 dark:bg-gray-800 text-gray-600 dark:text-gray-400 ${className}`}
      {...props}
    >
      {children}
    </thead>
  );
}

export interface TableBodyProps extends HTMLAttributes<HTMLTableSectionElement> {
  children: ReactNode;
}

export function TableBody({ children, className = '', ...props }: TableBodyProps) {
  return (
    <tbody className={`divide-y divide-gray-200 dark:divide-gray-700 ${className}`} {...props}>
      {children}
    </tbody>
  );
}

export interface TableRowProps extends HTMLAttributes<HTMLTableRowElement> {
  children: ReactNode;
  clickable?: boolean;
}

export function TableRow({ children, clickable = false, className = '', ...props }: TableRowProps) {
  return (
    <tr
      className={`
        ${clickable ? 'hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer' : ''}
        ${className}
      `.trim()}
      {...props}
    >
      {children}
    </tr>
  );
}

export interface TableHeaderProps extends HTMLAttributes<HTMLTableCellElement> {
  children: ReactNode;
  sortable?: boolean;
  sorted?: 'asc' | 'desc' | null;
  onSort?: () => void;
}

export function TableHeader({
  children,
  sortable = false,
  sorted = null,
  onSort,
  className = '',
  ...props
}: TableHeaderProps) {
  return (
    <th
      className={`
        px-4 py-3 text-left text-xs font-medium uppercase tracking-wider
        ${sortable ? 'cursor-pointer select-none hover:text-gray-900 dark:hover:text-gray-200' : ''}
        ${className}
      `.trim()}
      onClick={sortable ? onSort : undefined}
      {...props}
    >
      <div className="flex items-center gap-1">
        {children}
        {sortable && sorted && (
          <span className="text-primary-500">
            {sorted === 'asc' ? '↑' : '↓'}
          </span>
        )}
      </div>
    </th>
  );
}

export interface TableCellProps extends HTMLAttributes<HTMLTableCellElement> {
  children: ReactNode;
}

export function TableCell({ children, className = '', ...props }: TableCellProps) {
  return (
    <td
      className={`px-4 py-3 text-gray-700 dark:text-gray-300 ${className}`}
      {...props}
    >
      {children}
    </td>
  );
}

// Empty state component
export interface TableEmptyProps {
  message?: string;
  colSpan: number;
}

export function TableEmpty({ message = 'No data available', colSpan }: TableEmptyProps) {
  return (
    <tr>
      <td
        colSpan={colSpan}
        className="px-4 py-8 text-center text-gray-500 dark:text-gray-400"
      >
        {message}
      </td>
    </tr>
  );
}

import { useState, useRef, useEffect, type ReactNode } from 'react';
import { ChevronDown } from 'lucide-react';

export interface DropdownProps {
  trigger: ReactNode;
  children: ReactNode;
  align?: 'left' | 'right';
  className?: string;
}

export function Dropdown({ trigger, children, align = 'left', className = '' }: DropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    function handleEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setIsOpen(false);
      }
    }

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      return () => document.removeEventListener('keydown', handleEscape);
    }
  }, [isOpen]);

  return (
    <div ref={dropdownRef} className={`relative inline-block ${className}`}>
      <div onClick={() => setIsOpen(!isOpen)}>{trigger}</div>
      {isOpen && (
        <div
          className={`
            absolute z-50 mt-2 min-w-[160px]
            bg-white dark:bg-gray-800 rounded-lg shadow-lg
            border border-gray-200 dark:border-gray-700
            py-1 animate-fade-in
            ${align === 'right' ? 'right-0' : 'left-0'}
          `}
        >
          {children}
        </div>
      )}
    </div>
  );
}

export interface DropdownItemProps {
  onClick?: () => void;
  disabled?: boolean;
  danger?: boolean;
  icon?: ReactNode;
  children: ReactNode;
}

export function DropdownItem({
  onClick,
  disabled = false,
  danger = false,
  icon,
  children,
}: DropdownItemProps) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`
        w-full px-4 py-2 text-left text-sm flex items-center gap-2
        ${
          disabled
            ? 'text-gray-400 cursor-not-allowed'
            : danger
            ? 'text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20'
            : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
        }
        transition-colors
      `}
    >
      {icon && <span className="w-4 h-4">{icon}</span>}
      {children}
    </button>
  );
}

export function DropdownDivider() {
  return <div className="my-1 border-t border-gray-200 dark:border-gray-700" />;
}

// Menu button with dropdown
export interface MenuButtonProps {
  label: string;
  items: Array<{
    label: string;
    onClick: () => void;
    icon?: ReactNode;
    danger?: boolean;
    disabled?: boolean;
  }>;
}

export function MenuButton({ label, items }: MenuButtonProps) {
  return (
    <Dropdown
      trigger={
        <button className="btn-secondary flex items-center gap-1">
          {label}
          <ChevronDown className="w-4 h-4" />
        </button>
      }
    >
      {items.map((item, index) => (
        <DropdownItem
          key={index}
          onClick={item.onClick}
          icon={item.icon}
          danger={item.danger}
          disabled={item.disabled}
        >
          {item.label}
        </DropdownItem>
      ))}
    </Dropdown>
  );
}

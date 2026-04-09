import { forwardRef, type InputHTMLAttributes } from 'react';

export interface SwitchProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label?: string;
  description?: string;
}

export const Switch = forwardRef<HTMLInputElement, SwitchProps>(
  ({ label, description, className = '', id, ...props }, ref) => {
    const inputId = id || props.name;

    return (
      <div className={`flex items-center justify-between gap-4 ${className}`}>
        {(label || description) && (
          <div className="flex-1">
            {label && (
              <label
                htmlFor={inputId}
                className="text-sm font-medium text-gray-700 dark:text-gray-300 cursor-pointer"
              >
                {label}
              </label>
            )}
            {description && (
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                {description}
              </p>
            )}
          </div>
        )}
        <div className="relative">
          <input
            ref={ref}
            type="checkbox"
            id={inputId}
            className="peer sr-only"
            {...props}
          />
          <div
            className={`
              w-11 h-6 rounded-full
              bg-gray-200 dark:bg-gray-700
              peer-checked:bg-primary-500
              peer-focus:ring-2 peer-focus:ring-primary-500/50
              peer-disabled:opacity-50 peer-disabled:cursor-not-allowed
              transition-colors
            `}
          />
          <div
            className={`
              absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow
              peer-checked:translate-x-5
              transition-transform
            `}
          />
        </div>
      </div>
    );
  }
);

Switch.displayName = 'Switch';

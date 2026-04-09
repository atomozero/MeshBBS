import { forwardRef, type InputHTMLAttributes } from 'react';
import { Check } from 'lucide-react';

export interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label?: string;
  description?: string;
}

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(
  ({ label, description, className = '', id, ...props }, ref) => {
    const inputId = id || props.name;

    return (
      <div className={`flex items-start gap-3 ${className}`}>
        <div className="relative flex items-center">
          <input
            ref={ref}
            type="checkbox"
            id={inputId}
            className="peer sr-only"
            {...props}
          />
          <div
            className={`
              w-5 h-5 border-2 rounded flex items-center justify-center
              border-gray-300 dark:border-gray-600
              peer-checked:bg-primary-500 peer-checked:border-primary-500
              peer-focus:ring-2 peer-focus:ring-primary-500/50
              peer-disabled:opacity-50 peer-disabled:cursor-not-allowed
              transition-colors
            `}
          >
            <Check
              className="w-3.5 h-3.5 text-white opacity-0 peer-checked:opacity-100"
              strokeWidth={3}
            />
          </div>
        </div>
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
      </div>
    );
  }
);

Checkbox.displayName = 'Checkbox';

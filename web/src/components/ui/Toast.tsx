import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';
import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from 'lucide-react';

export type ToastVariant = 'success' | 'error' | 'warning' | 'info';

export interface Toast {
  id: string;
  variant: ToastVariant;
  message: string;
  duration?: number;
}

interface ToastContextValue {
  toasts: Toast[];
  addToast: (toast: Omit<Toast, 'id'>) => void;
  removeToast: (id: string) => void;
  success: (message: string) => void;
  error: (message: string) => void;
  warning: (message: string) => void;
  info: (message: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  const addToast = useCallback(
    (toast: Omit<Toast, 'id'>) => {
      const id = Math.random().toString(36).substring(2, 9);
      const newToast = { ...toast, id };

      setToasts((prev) => [...prev, newToast]);

      // Auto remove after duration
      const duration = toast.duration ?? 5000;
      if (duration > 0) {
        setTimeout(() => {
          removeToast(id);
        }, duration);
      }
    },
    [removeToast]
  );

  const success = useCallback(
    (message: string) => addToast({ variant: 'success', message }),
    [addToast]
  );
  const error = useCallback(
    (message: string) => addToast({ variant: 'error', message }),
    [addToast]
  );
  const warning = useCallback(
    (message: string) => addToast({ variant: 'warning', message }),
    [addToast]
  );
  const info = useCallback(
    (message: string) => addToast({ variant: 'info', message }),
    [addToast]
  );

  return (
    <ToastContext.Provider
      value={{ toasts, addToast, removeToast, success, error, warning, info }}
    >
      {children}
      <ToastContainer toasts={toasts} removeToast={removeToast} />
    </ToastContext.Provider>
  );
}

interface ToastContainerProps {
  toasts: Toast[];
  removeToast: (id: string) => void;
}

function ToastContainer({ toasts, removeToast }: ToastContainerProps) {
  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onClose={() => removeToast(toast.id)} />
      ))}
    </div>
  );
}

interface ToastItemProps {
  toast: Toast;
  onClose: () => void;
}

const variantStyles = {
  success: {
    container: 'bg-green-50 dark:bg-green-900 border-green-200 dark:border-green-700',
    icon: 'text-green-500',
    text: 'text-green-800 dark:text-green-200',
  },
  error: {
    container: 'bg-red-50 dark:bg-red-900 border-red-200 dark:border-red-700',
    icon: 'text-red-500',
    text: 'text-red-800 dark:text-red-200',
  },
  warning: {
    container: 'bg-yellow-50 dark:bg-yellow-900 border-yellow-200 dark:border-yellow-700',
    icon: 'text-yellow-500',
    text: 'text-yellow-800 dark:text-yellow-200',
  },
  info: {
    container: 'bg-blue-50 dark:bg-blue-900 border-blue-200 dark:border-blue-700',
    icon: 'text-blue-500',
    text: 'text-blue-800 dark:text-blue-200',
  },
};

const icons = {
  success: CheckCircle,
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
};

function ToastItem({ toast, onClose }: ToastItemProps) {
  const styles = variantStyles[toast.variant];
  const Icon = icons[toast.variant];

  return (
    <div
      className={`
        flex items-center gap-3 px-4 py-3 rounded-lg border shadow-lg
        animate-slide-in ${styles.container}
      `}
      role="alert"
    >
      <Icon className={`w-5 h-5 flex-shrink-0 ${styles.icon}`} />
      <p className={`text-sm flex-1 ${styles.text}`}>{toast.message}</p>
      <button
        onClick={onClose}
        className={`flex-shrink-0 hover:opacity-70 transition-opacity ${styles.icon}`}
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}

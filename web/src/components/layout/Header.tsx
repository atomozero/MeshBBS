import { Menu, Bell, Search, Radio } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useWebSocket } from '@/contexts';
import { ThemeToggle, LanguageSwitcher } from '@/components/ui';

interface HeaderProps {
  onMenuClick: () => void;
  title?: string;
}

export function Header({ onMenuClick, title }: HeaderProps) {
  const { t } = useTranslation();
  const { isConnected } = useWebSocket();

  return (
    <header className="sticky top-0 z-30 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800">
      <div className="flex items-center justify-between h-16 px-4 lg:px-6">
        {/* Mobile menu button */}
        <div className="flex items-center gap-4">
          <button
            onClick={onMenuClick}
            className="lg:hidden p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
            aria-label="Open menu"
          >
            <Menu className="w-6 h-6" />
          </button>

          {/* Mobile logo */}
          <div className="flex items-center gap-2 lg:hidden">
            <Radio className="w-6 h-6 text-primary-500" />
            <span className="font-bold text-gray-900 dark:text-white">MeshBBS</span>
          </div>

          {/* Page title */}
          {title && (
            <h1 className="hidden lg:block text-xl font-semibold text-gray-900 dark:text-white">
              {title}
            </h1>
          )}
        </div>

        {/* Right side actions */}
        <div className="flex items-center gap-3">
          {/* Connection status */}
          <div
            className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium ${
              isConnected
                ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
            }`}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                isConnected ? 'bg-green-500' : 'bg-red-500'
              }`}
            />
            {isConnected ? t('status.connected') : t('status.disconnected')}
          </div>

          {/* Language switcher */}
          <LanguageSwitcher />

          {/* Theme toggle */}
          <ThemeToggle />

          {/* Search button */}
          <button
            className="hidden sm:flex p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"
            aria-label={t('actions.search')}
          >
            <Search className="w-5 h-5" />
          </button>

          {/* Notifications button */}
          <button
            className="relative p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"
            aria-label="Notifications"
          >
            <Bell className="w-5 h-5" />
            {/* Notification badge */}
            <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full" />
          </button>
        </div>
      </div>
    </header>
  );
}

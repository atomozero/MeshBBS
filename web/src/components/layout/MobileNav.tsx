import { NavLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  LayoutDashboard,
  Users,
  MessageSquare,
  Folder,
  FileText,
  Settings,
  LogOut,
  X,
  Radio,
} from 'lucide-react';
import { useAuth } from '@/contexts';

const navItems = [
  { to: '/', icon: LayoutDashboard, labelKey: 'nav.dashboard' },
  { to: '/users', icon: Users, labelKey: 'nav.users' },
  { to: '/areas', icon: Folder, labelKey: 'nav.areas' },
  { to: '/messages', icon: MessageSquare, labelKey: 'nav.messages' },
  { to: '/logs', icon: FileText, labelKey: 'nav.logs' },
  { to: '/settings', icon: Settings, labelKey: 'nav.settings' },
];

interface MobileNavProps {
  isOpen: boolean;
  onClose: () => void;
}

export function MobileNav({ isOpen, onClose }: MobileNavProps) {
  const { t } = useTranslation();
  const { logout, user } = useAuth();

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 z-40 lg:hidden animate-fade-in"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer */}
      <aside className="fixed inset-y-0 left-0 w-72 bg-gray-900 text-white z-50 lg:hidden animate-slide-in">
        {/* Header */}
        <div className="flex items-center justify-between h-16 px-4 border-b border-gray-800">
          <div className="flex items-center gap-3">
            <Radio className="w-8 h-8 text-primary-400" />
            <span className="text-xl font-bold">MeshBBS</span>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-white"
            aria-label="Close menu"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-4 py-6 space-y-1 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              onClick={onClose}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-primary-500/20 text-primary-400'
                    : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                }`
              }
            >
              <item.icon className="w-5 h-5" />
              {t(item.labelKey)}
            </NavLink>
          ))}
        </nav>

        {/* User section */}
        <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-gray-800">
          <div className="flex items-center gap-3 px-4 py-2 mb-2">
            <div className="w-8 h-8 rounded-full bg-primary-500 flex items-center justify-center text-sm font-medium">
              {user?.username?.charAt(0).toUpperCase() || 'A'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{user?.username || 'Admin'}</p>
              <p className="text-xs text-gray-500 capitalize">{user?.role || 'admin'}</p>
            </div>
          </div>
          <button
            onClick={() => {
              logout();
              onClose();
            }}
            className="flex items-center gap-3 w-full px-4 py-2.5 rounded-lg text-sm font-medium text-gray-400 hover:bg-gray-800 hover:text-white transition-colors"
          >
            <LogOut className="w-5 h-5" />
            {t('nav.logout')}
          </button>
        </div>
      </aside>
    </>
  );
}

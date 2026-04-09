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

export function Sidebar() {
  const { t } = useTranslation();
  const { logout, user } = useAuth();

  return (
    <aside className="hidden lg:flex lg:flex-col lg:w-64 lg:fixed lg:inset-y-0 bg-gray-900 text-white">
      {/* Logo */}
      <div className="flex items-center gap-3 h-16 px-6 border-b border-gray-800">
        <Radio className="w-8 h-8 text-primary-400" />
        <span className="text-xl font-bold">MeshBBS</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-4 py-6 space-y-1 overflow-y-auto">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
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
      <div className="p-4 border-t border-gray-800">
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
          onClick={logout}
          className="flex items-center gap-3 w-full px-4 py-2.5 rounded-lg text-sm font-medium text-gray-400 hover:bg-gray-800 hover:text-white transition-colors"
        >
          <LogOut className="w-5 h-5" />
          {t('nav.logout')}
        </button>
      </div>
    </aside>
  );
}

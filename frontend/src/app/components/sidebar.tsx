import { Link, useLocation } from 'react-router';
import { 
  LayoutDashboard, 
  Upload, 
  Cog, 
  ListChecks, 
  Search, 
  FileDown, 
  Settings,
  Video
} from 'lucide-react';

const navItems = [
  { path: '/', icon: LayoutDashboard, label: 'Overview' },
  { path: '/videos', icon: Video, label: 'Videos' },
  { path: '/jobs', icon: Cog, label: 'Jobs' },
  { path: '/review-queue', icon: ListChecks, label: 'Review Queue' },
  { path: '/search', icon: Search, label: 'Search' },
  { path: '/export', icon: FileDown, label: 'Export & Backup' },
  { path: '/settings', icon: Settings, label: 'Settings' },
];

export function Sidebar() {
  const location = useLocation();
  
  return (
    <aside className="w-64 bg-white border-r border-gray-200 h-screen flex flex-col">
      {/* Logo */}
      <div className="p-6 border-b border-gray-200">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center">
            <Video className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="font-semibold text-gray-900">Southview OCR</h1>
            <p className="text-xs text-gray-500">Index Card Digitization</p>
          </div>
        </div>
      </div>
      
      {/* Navigation */}
      <nav className="flex-1 p-4">
        <ul className="space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            
            return (
              <li key={item.path}>
                <Link
                  to={item.path}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${
                    isActive
                      ? 'bg-blue-50 text-blue-700'
                      : 'text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  <Icon className="w-5 h-5" />
                  <span className="font-medium">{item.label}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
      
      {/* User Info */}
      <div className="p-4 border-t border-gray-200">
        <div className="flex items-center gap-3 px-3 py-2">
          <div className="w-8 h-8 bg-gray-300 rounded-full flex items-center justify-center">
            <span className="text-sm font-medium text-gray-700">AD</span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-900 truncate">Admin User</p>
            <p className="text-xs text-gray-500 truncate">admin@southview.org</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
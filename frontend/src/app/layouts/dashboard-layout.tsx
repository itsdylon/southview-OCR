import { ReactNode, useState } from 'react';
import { Menu } from 'lucide-react';
import { useNavigate } from 'react-router';
import { useAuth } from '../auth/auth-provider';
import { Sidebar } from '../components/sidebar';

interface DashboardLayoutProps {
  children: ReactNode;
}

export function DashboardLayout({ children }: DashboardLayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const navigate = useNavigate();
  const { username, logout } = useAuth();

  async function handleLogout() {
    await logout();
    navigate('/login', { replace: true });
  }

  return (
    <div className="flex h-screen bg-gray-50">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex-1 flex flex-col overflow-auto">
        {/* Mobile header */}
        <div className="sticky top-0 z-30 flex items-center gap-3 bg-gray-50 px-4 py-3 border-b border-gray-200 lg:hidden">
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-2 rounded-lg hover:bg-gray-100"
          >
            <Menu className="w-5 h-5 text-gray-700" />
          </button>
          <span className="font-semibold text-gray-900">SVC OCR</span>
        </div>
        <div className="sticky top-0 z-20 hidden items-center justify-end gap-4 border-b border-gray-200 bg-gray-50/95 px-6 py-3 backdrop-blur lg:flex">
          <p className="text-sm text-gray-500">
            Signed in as <span className="font-semibold text-gray-800">{username ?? 'admin'}</span>
          </p>
          <button
            onClick={handleLogout}
            className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-100"
          >
            Log out
          </button>
        </div>
        <main className="flex-1">
          {children}
        </main>
      </div>
    </div>
  );
}

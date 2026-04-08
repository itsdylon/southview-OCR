import { Navigate, Outlet, useLocation } from 'react-router';
import { useAuth } from './auth-provider';

export function ProtectedRoute() {
  const { authenticated, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-stone-950 text-stone-100">
        <div className="space-y-4 text-center">
          <div className="mx-auto h-12 w-12 animate-spin rounded-full border-4 border-amber-300/30 border-t-amber-300" />
          <p className="text-sm uppercase tracking-[0.24em] text-stone-300">Opening Southview OCR</p>
        </div>
      </div>
    );
  }

  if (!authenticated) {
    const next = `${location.pathname}${location.search}${location.hash}`;
    return <Navigate to={`/login${next && next !== '/' ? `?next=${encodeURIComponent(next)}` : ''}`} replace />;
  }

  return <Outlet />;
}

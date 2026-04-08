import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { ArrowRight, LockKeyhole, ShieldCheck, Video } from 'lucide-react';
import { useAuth } from '../auth/auth-provider';

export default function LoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { authenticated, login } = useAuth();
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (authenticated) {
      navigate(searchParams.get('next') || '/', { replace: true });
    }
  }, [authenticated, navigate, searchParams]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(username, password);
      navigate(searchParams.get('next') || '/', { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign-in failed');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="mx-auto flex min-h-screen max-w-7xl flex-col px-6 py-8 lg:px-8">
        <header className="mb-10 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-600">
            <Video className="h-6 w-6 text-white" />
          </div>
          <div>
            <h1 className="font-semibold text-gray-900">SVC OCR</h1>
            <p className="text-xs text-gray-500">Index Card Digitization</p>
          </div>
        </header>

        <div className="flex flex-1 flex-col justify-center gap-8 lg:grid lg:grid-cols-[1.1fr_480px] lg:items-center lg:gap-12">
          <section className="max-w-2xl">
            <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-blue-700">
              <ShieldCheck className="h-4 w-4" />
              Admin protected
            </div>
            <h2 className="max-w-xl text-4xl font-bold tracking-tight text-gray-900 lg:text-5xl">
              Sign in to continue working in Southview OCR
            </h2>
            <p className="mt-5 max-w-xl text-base leading-7 text-gray-600">Enter the admin credentials to open the dashboard.</p>
          </section>

          <section className="w-full max-w-md lg:max-w-none">
            <div className="rounded-2xl border border-gray-200 bg-white p-8 shadow-sm">
              <div className="mb-8 flex items-center gap-4">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-50 text-blue-700">
                  <LockKeyhole className="h-7 w-7" />
                </div>
                <div>
                  <p className="text-sm font-semibold uppercase tracking-[0.18em] text-gray-500">Admin access</p>
                  <h3 className="text-2xl font-semibold text-gray-900">Sign in</h3>
                </div>
              </div>

              <form onSubmit={handleSubmit} className="space-y-5">
                <label className="block">
                  <span className="mb-2 block text-sm font-medium text-gray-700">Username</span>
                  <input
                    value={username}
                    onChange={(event) => setUsername(event.target.value)}
                    autoComplete="username"
                    className="w-full rounded-xl border border-gray-300 bg-white px-4 py-3 text-gray-900 placeholder:text-gray-400 focus:border-blue-500 focus:outline-none"
                    placeholder="admin"
                  />
                </label>

                <label className="block">
                  <span className="mb-2 block text-sm font-medium text-gray-700">Password</span>
                  <input
                    type="password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    autoComplete="current-password"
                    className="w-full rounded-xl border border-gray-300 bg-white px-4 py-3 text-gray-900 placeholder:text-gray-400 focus:border-blue-500 focus:outline-none"
                    placeholder="Enter your password"
                  />
                </label>

                {error ? (
                  <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    {error}
                  </div>
                ) : null}

                <button
                  type="submit"
                  disabled={submitting}
                  className="flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-70"
                >
                  {submitting ? 'Signing in...' : 'Sign in'}
                  {!submitting ? <ArrowRight className="h-4 w-4" /> : null}
                </button>
              </form>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

import { createContext, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { fetchSession, login as loginRequest, logout as logoutRequest, subscribeToUnauthorized } from '../data/api';

interface AuthState {
  authenticated: boolean;
  username: string | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshSession: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [authenticated, setAuthenticated] = useState(false);
  const [username, setUsername] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function refreshSession() {
    try {
      const session = await fetchSession();
      setAuthenticated(session.authenticated);
      setUsername(session.authenticated ? session.username : null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refreshSession().catch((error) => {
      console.error('Failed to restore session', error);
      setLoading(false);
    });
  }, []);

  useEffect(() => {
    return subscribeToUnauthorized(() => {
      setAuthenticated(false);
      setUsername(null);
      setLoading(false);
    });
  }, []);

  async function login(username: string, password: string) {
    const session = await loginRequest(username, password);
    setAuthenticated(session.authenticated);
    setUsername(session.username);
  }

  async function logout() {
    await logoutRequest();
    setAuthenticated(false);
    setUsername(null);
  }

  return (
    <AuthContext.Provider value={{ authenticated, username, loading, login, logout, refreshSession }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}

import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { getAccessToken, getRefreshToken, setTokens, clearTokens as clearStoredTokens } from './auth';

type AuthState = {
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
};

type AuthContextValue = AuthState & {
  signIn: (tokens: { accessToken: string; refreshToken?: string }) => void;
  signOut: () => void;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [accessToken, setAccessToken] = useState<string | null>(getAccessToken());
  const [refreshToken, setRefreshToken] = useState<string | null>(getRefreshToken());

  useEffect(() => {
    const onExpired = () => {
      setAccessToken(null);
      setRefreshToken(null);
    };
    window.addEventListener('ntheemba:auth-expired', onExpired as EventListener);
    return () => window.removeEventListener('ntheemba:auth-expired', onExpired as EventListener);
  }, []);

  const signIn = (tokens: { accessToken: string; refreshToken?: string }) => {
    setTokens({ accessToken: tokens.accessToken, refreshToken: tokens.refreshToken });
    setAccessToken(tokens.accessToken);
    if (tokens.refreshToken) setRefreshToken(tokens.refreshToken);
  };

  const signOut = () => {
    clearStoredTokens();
    setAccessToken(null);
    setRefreshToken(null);
    if (typeof window !== 'undefined') window.dispatchEvent(new CustomEvent('ntheemba:auth-expired'));
  };

  const value: AuthContextValue = {
    accessToken,
    refreshToken,
    isAuthenticated: !!accessToken,
    signIn,
    signOut,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
};

export default AuthProvider;

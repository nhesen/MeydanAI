"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { api, ApiError } from "@/services/api-client";
import { getSessionToken, setSessionToken } from "@/lib/session";
import type { AuthUser } from "@/types/api";

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    await Promise.resolve();
    if (!getSessionToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const response = await api.getMe();
      setUser(response.data);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setSessionToken(null);
      }
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    async function initialize() {
      await Promise.resolve();
      if (!getSessionToken()) {
        setUser(null);
        setLoading(false);
        return;
      }
      try {
        const response = await api.getMe();
        setUser(response.data);
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          setSessionToken(null);
        }
        setUser(null);
      } finally {
        setLoading(false);
      }
    }
    void initialize();
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const response = await api.login(email, password);
    setSessionToken(response.data.access_token);
    setUser(response.data.user);
  }, []);

  const register = useCallback(async (email: string, password: string) => {
    const response = await api.register(email, password);
    setSessionToken(response.data.access_token);
    setUser(response.data.user);
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      setUser(null);
    }
  }, []);

  const value = useMemo(
    () => ({ user, loading, login, register, logout, refresh }),
    [user, loading, login, register, logout, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}

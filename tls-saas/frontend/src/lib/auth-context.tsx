"use client";

/**
 * Auth Context — Provides authentication state across the app.
 */

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import Cookies from "js-cookie";
import { authApi } from "./api";

interface User {
  id: number;
  email: string;
  full_name: string;
  phone: string;
  is_active: boolean;
  is_admin: boolean;
  has_push_subscription: boolean;
  created_at: string;
  active_plan: string | null;
  subscription_expires: string | null;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName: string, phone?: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    try {
      const token = Cookies.get("access_token");
      if (!token) {
        setUser(null);
        return;
      }
      const userData = await authApi.getMe();
      setUser(userData);
    } catch {
      setUser(null);
      Cookies.remove("access_token");
      Cookies.remove("refresh_token");
    }
  }, []);

  useEffect(() => {
    refreshUser().finally(() => setLoading(false));
  }, [refreshUser]);

  const login = async (email: string, password: string) => {
    const data = await authApi.login({ email, password });
    Cookies.set("access_token", data.access_token, { expires: 1 });
    Cookies.set("refresh_token", data.refresh_token, { expires: 30 });
    setUser(data.user);
  };

  const register = async (email: string, password: string, fullName: string, phone?: string) => {
    const data = await authApi.register({ email, password, full_name: fullName, phone });
    Cookies.set("access_token", data.access_token, { expires: 1 });
    Cookies.set("refresh_token", data.refresh_token, { expires: 30 });
    setUser(data.user);
  };

  const logout = () => {
    Cookies.remove("access_token");
    Cookies.remove("refresh_token");
    setUser(null);
    if (typeof window !== "undefined") {
      window.location.href = "/";
    }
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}

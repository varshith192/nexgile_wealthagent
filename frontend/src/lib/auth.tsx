"use client";

/**
 * Session state.
 *
 * One sign-in path serves every role (§5). The token identifies the user; the
 * server decides what they may see, so nothing here is a security boundary —
 * it only decides what to render.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, api, clearSession, readStoredUser, setSession } from "@/lib/api";
import type { LoginResponse, UserProfile } from "@/lib/types";

type AuthState = {
  user: UserProfile | null;
  status: "loading" | "authenticated" | "anonymous";
  signIn: (email: string, password: string, rememberMe: boolean) => Promise<UserProfile>;
  signOut: () => Promise<void>;
  can: (permission: string) => boolean;
  isRole: (...roles: string[]) => boolean;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<UserProfile | null>(null);
  const [status, setStatus] = useState<AuthState["status"]>("loading");

  useEffect(() => {
    let cancelled = false;

    // Render immediately from the cached profile, then confirm with the server.
    const cached = readStoredUser<UserProfile>();
    if (cached) {
      setUser(cached);
      setStatus("authenticated");
    }

    api
      .get<UserProfile>("/api/auth/me")
      .then((profile) => {
        if (cancelled) return;
        setUser(profile);
        setStatus("authenticated");
      })
      .catch((error) => {
        if (cancelled) return;
        if (error instanceof ApiError && error.isAuthError) clearSession();
        setUser(null);
        setStatus("anonymous");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const signIn = useCallback(async (email: string, password: string, rememberMe: boolean) => {
    const response = await api.post<LoginResponse>("/api/auth/login", {
      email,
      password,
      remember_me: rememberMe,
    });
    setSession(response.access_token, response.user);
    setUser(response.user);
    setStatus("authenticated");
    return response.user;
  }, []);

  const signOut = useCallback(async () => {
    try {
      await api.post("/api/auth/logout");
    } catch {
      /* the local session is cleared regardless */
    }
    clearSession();
    setUser(null);
    setStatus("anonymous");
    router.push("/login");
  }, [router]);

  const can = useCallback(
    (permission: string) =>
      Boolean(user && (user.permissions.includes("admin:all") || user.permissions.includes(permission))),
    [user],
  );

  const isRole = useCallback((...roles: string[]) => Boolean(user && roles.includes(user.role)), [user]);

  const value = useMemo<AuthState>(
    () => ({ user, status, signIn, signOut, can, isRole }),
    [user, status, signIn, signOut, can, isRole],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>");
  return context;
}

"use client";

import { create } from "zustand";

export type UserRole = "ADMIN" | "ANALYST" | "VIEWER";

export interface AuthUser {
  id: string;
  email: string;
  role: UserRole;
  preferred_timezone?: string;
  must_change_password?: boolean;
  onboarding_completed?: boolean;
  [key: string]: unknown;
}

interface AuthState {
  accessToken: string | null;
  user: AuthUser | null;
  setAccessToken: (token: string | null) => void;
  setUser: (user: AuthUser | null) => void;
  logout: () => void;
}

// Zustand store:管理 access_token + 當前使用者
// refresh_token 由 backend 寫 httpOnly cookie,前端讀不到也不該讀
export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  user: null,
  setAccessToken: (token) => set({ accessToken: token }),
  setUser: (user) => set({ user }),
  logout: () => set({ accessToken: null, user: null }),
}));

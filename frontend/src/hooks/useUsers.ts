"use client";

import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { api, type ApiEnvelope } from "@/lib/api";
import type { AdminUserItem, UserRole } from "@/lib/api-types";

// Phase 16 § I / § L:用戶管理 hooks(admin only)
//   - useUsers():列表
//   - useCreateUser():建立(初始密碼 + must_change_password=true)
//   - useUpdateUser():部分更新
//   - useResetUserPassword():重設密碼
//   - useDeleteUser():軟刪除
//   - useRevokeSession():強制下線

const USERS_KEY = ["admin", "users"] as const;

export interface UseUsersParams {
  cursor?: string | null;
  limit?: number;
  includeDeleted?: boolean;
}

export function useUsers(params: UseUsersParams = {}, enabled = true) {
  const { cursor, limit = 50, includeDeleted = false } = params;
  return useQuery({
    queryKey: [...USERS_KEY, { cursor, limit, includeDeleted }],
    enabled,
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<AdminUserItem[]>>("/users", {
        params: {
          cursor: cursor || undefined,
          limit,
          include_deleted: includeDeleted,
        },
      });
      return {
        items: res.data.data ?? [],
        nextCursor: res.data.pagination?.next_cursor ?? null,
        hasMore: res.data.pagination?.has_more ?? false,
      };
    },
  });
}

export interface CreateUserVars {
  email: string;
  password: string;
  full_name?: string | null;
  role: UserRole;
  must_change_password?: boolean;
}

export function useCreateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: CreateUserVars) => {
      const res = await api.post<ApiEnvelope<AdminUserItem>>("/users", {
        email: vars.email,
        password: vars.password,
        full_name: vars.full_name ?? null,
        role: vars.role,
        must_change_password: vars.must_change_password ?? true,
      });
      return res.data.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: USERS_KEY });
    },
  });
}

export interface UpdateUserVars {
  id: string;
  full_name?: string | null;
  role?: UserRole | null;
  is_active?: boolean | null;
}

export function useUpdateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: UpdateUserVars) => {
      const res = await api.patch<ApiEnvelope<AdminUserItem>>(
        `/users/${vars.id}`,
        {
          full_name: vars.full_name ?? null,
          role: vars.role ?? null,
          is_active: vars.is_active ?? null,
        },
      );
      return res.data.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: USERS_KEY });
    },
  });
}

export interface ResetPasswordVars {
  id: string;
  new_password: string;
  must_change_password?: boolean;
}

export function useResetUserPassword() {
  return useMutation({
    mutationFn: async (vars: ResetPasswordVars) => {
      const res = await api.post(`/users/${vars.id}/reset-password`, {
        new_password: vars.new_password,
        must_change_password: vars.must_change_password ?? true,
      });
      return res.data;
    },
  });
}

export function useDeleteUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/users/${id}`);
      return id;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: USERS_KEY });
    },
  });
}

export function useRevokeSession() {
  return useMutation({
    mutationFn: async (vars: { userId: string; jti: string }) => {
      const res = await api.delete(
        `/admin/users/${vars.userId}/sessions/${vars.jti}`,
      );
      return res.data;
    },
  });
}

/**
 * Authentication API functions.
 */

import { api, setAccessToken, clearAccessToken } from './client';
import type { AdminUser, TokenResponse } from '@/types';

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface LoginResponse extends TokenResponse {
  user: AdminUser;
}

export interface AdminCreateRequest {
  username: string;
  password: string;
  display_name?: string;
  email?: string;
  is_superadmin?: boolean;
}

export interface AdminUpdateRequest {
  display_name?: string;
  email?: string;
  is_active?: boolean;
  is_superadmin?: boolean;
}

export const authApi = {
  /**
   * Login with username and password.
   */
  login: async (credentials: LoginCredentials): Promise<LoginResponse> => {
    const response = await api.post<LoginResponse>('/auth/login', credentials);
    setAccessToken(response.access_token);
    return response;
  },

  /**
   * Logout and clear tokens.
   */
  logout: async (): Promise<void> => {
    try {
      await api.post('/auth/logout');
    } finally {
      clearAccessToken();
    }
  },

  /**
   * Get current admin user info.
   */
  getCurrentUser: async (): Promise<AdminUser> => {
    return api.get<AdminUser>('/auth/me');
  },

  /**
   * Change password.
   */
  changePassword: async (currentPassword: string, newPassword: string): Promise<void> => {
    await api.post('/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    });
  },

  /**
   * List all admin users (superadmin only for full info).
   */
  listAdmins: async (): Promise<AdminUser[]> => {
    return api.get<AdminUser[]>('/auth/admins');
  },

  /**
   * Create a new admin user.
   */
  createAdmin: async (data: {
    username: string;
    password: string;
    display_name?: string;
    email?: string;
    is_superadmin?: boolean;
  }): Promise<AdminUser> => {
    return api.post<AdminUser>('/auth/admins', data);
  },

  /**
   * Update an admin user.
   */
  updateAdmin: async (
    adminId: number,
    data: {
      display_name?: string;
      email?: string;
      is_active?: boolean;
      is_superadmin?: boolean;
    }
  ): Promise<AdminUser> => {
    return api.patch<AdminUser>(`/auth/admins/${adminId}`, data);
  },

  /**
   * Delete an admin user.
   */
  deleteAdmin: async (adminId: number): Promise<void> => {
    await api.delete(`/auth/admins/${adminId}`);
  },
};

/**
 * Users API functions.
 */

import { api } from './client';
import type { User, UserDetail, PaginatedResponse } from '@/types';

export interface UserFilters {
  page?: number;
  per_page?: number;
  search?: string;
  role?: 'all' | 'admin' | 'moderator' | 'user';
  status?: 'all' | 'active' | 'banned' | 'muted' | 'kicked';
  active_hours?: number;
}

export const usersApi = {
  /**
   * List users with pagination and filters.
   */
  list: async (filters: UserFilters = {}): Promise<PaginatedResponse<User>> => {
    return api.get<PaginatedResponse<User>>('/users', { params: filters });
  },

  /**
   * Get user details by public key.
   */
  getByKey: async (publicKey: string): Promise<UserDetail> => {
    return api.get<UserDetail>(`/users/${publicKey}`);
  },

  /**
   * Ban a user.
   */
  ban: async (publicKey: string, reason: string, durationHours?: number): Promise<{ message: string }> => {
    return api.post<{ message: string }>(`/users/${publicKey}/ban`, {
      reason,
      duration_hours: durationHours,
    });
  },

  /**
   * Unban a user.
   */
  unban: async (publicKey: string): Promise<{ message: string }> => {
    return api.post<{ message: string }>(`/users/${publicKey}/unban`);
  },

  /**
   * Mute a user.
   */
  mute: async (publicKey: string, reason: string, durationHours?: number): Promise<{ message: string }> => {
    return api.post<{ message: string }>(`/users/${publicKey}/mute`, {
      reason,
      duration_hours: durationHours,
    });
  },

  /**
   * Unmute a user.
   */
  unmute: async (publicKey: string): Promise<{ message: string }> => {
    return api.post<{ message: string }>(`/users/${publicKey}/unmute`);
  },

  /**
   * Kick a user (temporary ban).
   */
  kick: async (publicKey: string, reason: string, durationHours: number): Promise<{ message: string }> => {
    return api.post<{ message: string }>(`/users/${publicKey}/kick`, {
      reason,
      duration_hours: durationHours,
    });
  },

  /**
   * Unkick a user.
   */
  unkick: async (publicKey: string): Promise<{ message: string }> => {
    return api.post<{ message: string }>(`/users/${publicKey}/unkick`);
  },

  /**
   * Promote user to moderator or admin.
   */
  promote: async (publicKey: string, role: 'moderator' | 'admin'): Promise<{ message: string }> => {
    return api.post<{ message: string }>(`/users/${publicKey}/promote`, { role });
  },

  /**
   * Demote user from moderator or admin.
   */
  demote: async (publicKey: string): Promise<{ message: string }> => {
    return api.post<{ message: string }>(`/users/${publicKey}/demote`);
  },

  /**
   * Get user activity history.
   */
  getActivity: async (publicKey: string, limit = 20): Promise<{ items: unknown[] }> => {
    return api.get<{ items: unknown[] }>(`/users/${publicKey}/activity`, {
      params: { limit },
    });
  },
};

/**
 * Areas API functions.
 */

import { api } from './client';
import type { Area, AreaStats, Message, PaginatedResponse } from '@/types';

export interface AreaListResponse {
  items: Area[];
  total: number;
}

export const areasApi = {
  /**
   * List all areas.
   */
  list: async (includeHidden = true): Promise<AreaListResponse> => {
    return api.get<AreaListResponse>('/areas', {
      params: { include_hidden: includeHidden },
    });
  },

  /**
   * Get area by name.
   */
  getByName: async (name: string): Promise<Area> => {
    return api.get<Area>(`/areas/${name}`);
  },

  /**
   * Get area statistics.
   */
  getStats: async (name: string): Promise<AreaStats> => {
    return api.get<AreaStats>(`/areas/${name}/stats`);
  },

  /**
   * Get messages in an area.
   */
  getMessages: async (
    name: string,
    page = 1,
    perPage = 20
  ): Promise<PaginatedResponse<Message>> => {
    return api.get<PaginatedResponse<Message>>(`/areas/${name}/messages`, {
      params: { page, per_page: perPage },
    });
  },

  /**
   * Create a new area.
   */
  create: async (data: {
    name: string;
    description?: string;
    is_public?: boolean;
    is_readonly?: boolean;
  }): Promise<Area> => {
    return api.post<Area>('/areas', data);
  },

  /**
   * Update an area.
   */
  update: async (
    name: string,
    data: {
      description?: string;
      is_public?: boolean;
      is_readonly?: boolean;
    }
  ): Promise<Area> => {
    return api.patch<Area>(`/areas/${name}`, data);
  },

  /**
   * Delete an area.
   */
  delete: async (name: string, deleteMessages = true): Promise<void> => {
    await api.delete(`/areas/${name}`, {
      params: { delete_messages: deleteMessages },
    });
  },
};

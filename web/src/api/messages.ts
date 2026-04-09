/**
 * Messages API functions.
 */

import { api } from './client';
import type { Message, PrivateMessage, PaginatedResponse } from '@/types';

export interface MessageFilters {
  page?: number;
  per_page?: number;
  area?: string;
  sender?: string;
  search?: string;
  start_date?: string;
  end_date?: string;
}

export interface MessageDetailResponse extends Message {
  replies: Message[];
}

export interface BulkDeleteResponse {
  success_count: number;
  failed_count: number;
  errors: string[];
}

export const messagesApi = {
  /**
   * List public messages with filters.
   */
  list: async (filters: MessageFilters = {}): Promise<PaginatedResponse<Message>> => {
    return api.get<PaginatedResponse<Message>>('/messages', { params: filters });
  },

  /**
   * Get message details with replies.
   */
  getById: async (id: number): Promise<MessageDetailResponse> => {
    return api.get<MessageDetailResponse>(`/messages/${id}`);
  },

  /**
   * Delete a message.
   */
  delete: async (id: number): Promise<void> => {
    await api.delete(`/messages/${id}`);
  },

  /**
   * Bulk delete messages.
   */
  bulkDelete: async (ids: number[]): Promise<BulkDeleteResponse> => {
    return api.post<BulkDeleteResponse>('/messages/bulk-delete', { ids });
  },

  /**
   * List private messages.
   */
  listPrivate: async (
    page = 1,
    perPage = 20,
    userKey?: string,
    unreadOnly = false
  ): Promise<PaginatedResponse<PrivateMessage>> => {
    return api.get<PaginatedResponse<PrivateMessage>>('/messages/private', {
      params: {
        page,
        per_page: perPage,
        user_key: userKey,
        unread_only: unreadOnly,
      },
    });
  },

  /**
   * Delete a private message.
   */
  deletePrivate: async (id: number): Promise<void> => {
    await api.delete(`/messages/private/${id}`);
  },
};

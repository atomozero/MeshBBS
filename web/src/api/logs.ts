/**
 * Activity logs API functions.
 */

import { api } from './client';
import type { LogEntry, PaginatedResponse } from '@/types';

export interface LogFilters {
  page?: number;
  per_page?: number;
  event_type?: string;
  user_key?: string;
  search?: string;
  start_date?: string;
  end_date?: string;
}

export interface LogStatsResponse {
  total_entries: number;
  entries_today: number;
  entries_week: number;
  by_type: Record<string, number>;
}

export interface EventTypeInfo {
  value: string;
  name: string;
}

export const logsApi = {
  /**
   * List activity logs with filters.
   */
  list: async (filters: LogFilters = {}): Promise<PaginatedResponse<LogEntry>> => {
    return api.get<PaginatedResponse<LogEntry>>('/logs', { params: filters });
  },

  /**
   * Get log statistics.
   */
  getStats: async (): Promise<LogStatsResponse> => {
    return api.get<LogStatsResponse>('/logs/stats');
  },

  /**
   * List available event types.
   */
  getEventTypes: async (): Promise<{ types: EventTypeInfo[] }> => {
    return api.get<{ types: EventTypeInfo[] }>('/logs/types');
  },

  /**
   * Delete old logs.
   */
  clearOld: async (days: number): Promise<{ message: string; deleted_count: number }> => {
    return api.delete<{ message: string; deleted_count: number }>('/logs', {
      params: { days },
    });
  },

  /**
   * Export logs.
   */
  export: async (
    format: 'json' | 'csv' = 'json',
    startDate?: string,
    endDate?: string,
    limit = 1000
  ): Promise<unknown> => {
    const response = await api.get('/logs/export', {
      params: {
        format,
        start_date: startDate,
        end_date: endDate,
        limit,
      },
      responseType: format === 'csv' ? 'blob' : 'json',
    });
    return response;
  },
};

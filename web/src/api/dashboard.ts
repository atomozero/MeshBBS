/**
 * Dashboard API functions.
 */

import { api } from './client';
import type { DashboardStats, ActivityItem, ChartData, TopPoster } from '@/types';

export interface ActivityFeedResponse {
  items: ActivityItem[];
  total: number;
}

export interface TopUsersResponse {
  items: TopPoster[];
}

export const dashboardApi = {
  /**
   * Get dashboard statistics.
   */
  getStats: async (): Promise<DashboardStats> => {
    return api.get<DashboardStats>('/dashboard/stats');
  },

  /**
   * Get recent activity feed.
   */
  getActivity: async (limit = 20, offset = 0): Promise<ActivityFeedResponse> => {
    return api.get<ActivityFeedResponse>('/dashboard/activity', {
      params: { limit, offset },
    });
  },

  /**
   * Get chart data for activity over time.
   */
  getChartData: async (period: '7d' | '30d' | '90d' = '7d'): Promise<ChartData> => {
    return api.get<ChartData>('/dashboard/chart', {
      params: { period },
    });
  },

  /**
   * Get top users by message count.
   */
  getTopUsers: async (limit = 10): Promise<TopUsersResponse> => {
    return api.get<TopUsersResponse>('/dashboard/top-users', {
      params: { limit },
    });
  },
};

/**
 * Settings API functions.
 */

import { api } from './client';
import type { BBSSettings, RetentionStats, SystemInfo } from '@/types';

export interface UpdateSettingsRequest {
  bbs_name?: string;
  welcome_message?: string;
  max_message_length?: number;
  session_timeout?: number;
  allow_registration?: boolean;
  require_approval?: boolean;
  default_area?: string;
  retention_days?: number;
  enable_logging?: boolean;
}

export interface BackupInfo {
  filename: string;
  size: number;
  created_at: string;
}

export interface BackupListResponse {
  backups: BackupInfo[];
}

export const settingsApi = {
  /**
   * Get current BBS settings.
   */
  get: async (): Promise<BBSSettings> => {
    return api.get<BBSSettings>('/settings');
  },

  /**
   * Update BBS settings.
   */
  update: async (data: UpdateSettingsRequest): Promise<BBSSettings> => {
    return api.patch<BBSSettings>('/settings', data);
  },

  /**
   * Get system information.
   */
  getSystemInfo: async (): Promise<SystemInfo> => {
    return api.get<SystemInfo>('/settings/system');
  },

  /**
   * Get retention statistics.
   */
  getRetentionStats: async (): Promise<RetentionStats> => {
    return api.get<RetentionStats>('/settings/retention');
  },

  /**
   * Trigger manual cleanup.
   */
  triggerCleanup: async (): Promise<{ message: string; deleted: number }> => {
    return api.post<{ message: string; deleted: number }>('/settings/cleanup');
  },

  /**
   * Create a backup.
   */
  createBackup: async (): Promise<{ message: string; filename: string }> => {
    return api.post<{ message: string; filename: string }>('/settings/backup');
  },

  /**
   * List available backups.
   */
  listBackups: async (): Promise<BackupListResponse> => {
    return api.get<BackupListResponse>('/settings/backups');
  },

  /**
   * Restore from a backup.
   */
  restoreBackup: async (filename: string): Promise<{ message: string }> => {
    return api.post<{ message: string }>('/settings/restore', { filename });
  },

  /**
   * Delete a backup.
   */
  deleteBackup: async (filename: string): Promise<void> => {
    await api.delete(`/settings/backups/${filename}`);
  },

  /**
   * Download a backup file.
   */
  downloadBackup: async (filename: string): Promise<Blob> => {
    const response = await api.get<Blob>(`/settings/backups/${filename}/download`, {
      responseType: 'blob',
    });
    return response;
  },
};

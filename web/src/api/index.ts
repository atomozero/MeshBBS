/**
 * API module exports.
 */

export { api, setAccessToken, getAccessToken, clearTokens, clearAccessToken } from './client';
export { authApi } from './auth';
export { dashboardApi } from './dashboard';
export { usersApi } from './users';
export { areasApi } from './areas';
export { messagesApi } from './messages';
export { logsApi } from './logs';
export { settingsApi } from './settings';
export {
  createWebSocketClient,
  getWebSocketClient,
  resetWebSocketClient,
  type WebSocketClient,
  type WebSocketEventHandler,
} from './websocket';

// Re-export types from API modules
export type { LoginCredentials, LoginResponse, AdminCreateRequest, AdminUpdateRequest } from './auth';
export type { ActivityFeedResponse, TopUsersResponse } from './dashboard';
export type { UserFilters } from './users';
export type { AreaListResponse } from './areas';
export type { MessageFilters, MessageDetailResponse, BulkDeleteResponse } from './messages';
export type { LogFilters, LogStatsResponse, EventTypeInfo } from './logs';
export type { UpdateSettingsRequest, BackupInfo, BackupListResponse } from './settings';

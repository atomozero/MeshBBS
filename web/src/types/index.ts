/**
 * Type definitions for MeshBBS Admin interface.
 */

// Auth types
export interface AdminUser {
  id: number;
  username: string;
  display_name: string;
  email: string | null;
  is_active: boolean;
  is_superadmin: boolean;
  role: 'admin' | 'moderator';
  created_at: string | null;
  last_login: string | null;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token?: string;
  token_type: string;
  expires_in: number;
  user?: AdminUser;
}

// User types
export interface User {
  public_key: string;
  nickname: string | null;
  short_name: string | null;
  long_name: string | null;
  first_seen: string;
  last_seen: string;
  is_admin: boolean;
  is_moderator: boolean;
  is_banned: boolean;
  ban_reason: string | null;
  is_muted: boolean;
  mute_reason: string | null;
  kicked_until: string | null;
  kick_reason: string | null;
  message_count: number;
  role: 'admin' | 'moderator' | 'user';
  status: 'active' | 'banned' | 'muted' | 'kicked';
}

export interface UserDetail extends User {
  activity_history: ActivityItem[];
}

// Area types
export interface Area {
  id: number;
  name: string;
  description: string | null;
  is_public: boolean;
  is_readonly: boolean;
  message_count: number;
  created_at: string | null;
  last_post_at: string | null;
}

export interface AreaStats {
  name: string;
  message_count: number;
  unique_posters: number;
  messages_today: number;
  messages_week: number;
  last_post_at: string | null;
  top_posters: TopPoster[];
}

export interface TopPoster {
  public_key: string;
  user_id: string;
  nickname: string;
  short_name: string | null;
  message_count: number;
}

// Message types
export interface Message {
  id: number;
  area_name: string;
  area: string;
  sender_key: string;
  sender_id: string | null;
  sender_nickname: string | null;
  sender_short_name: string | null;
  subject: string | null;
  body: string;
  content: string;
  parent_id: number | null;
  reply_count: number;
  timestamp: string | null;
  created_at: string | null;
  hops: number | null;
  rssi: number | null;
}

export interface PrivateMessage {
  id: number;
  sender_key: string;
  sender_nickname: string | null;
  recipient_key: string;
  recipient_nickname: string | null;
  body: string;
  is_read: boolean;
  created_at: string | null;
}

// Activity log types
export interface ActivityItem {
  id: number;
  event_type: string;
  user_key: string | null;
  user_nickname: string | null;
  details: string | null;
  description: string | null;
  timestamp: string;
  icon?: string;
  color?: string;
}

export interface LogEntry {
  id: number;
  event_type: string;
  user_key: string | null;
  user_nickname: string | null;
  details: string | null;
  timestamp: string | null;
}

// Dashboard types
export interface DashboardStats {
  users: UserStats;
  messages: MessageStats;
  areas: AreaStatsBasic;
  private_messages: PMStats;
  system: SystemStatus;
  // Computed properties for easy access
  total_users: number;
  total_messages: number;
  total_areas: number;
  active_users: number;
  user_growth?: number;
  system_status?: {
    meshtastic_connected: boolean;
    uptime: string;
  };
}

export interface UserStats {
  total: number;
  active_24h: number;
  active_7d: number;
  banned: number;
  muted: number;
  kicked: number;
  admins: number;
  moderators: number;
}

export interface MessageStats {
  total: number;
  today: number;
  week: number;
  month: number;
}

export interface AreaStatsBasic {
  total: number;
  public: number;
  readonly: number;
}

export interface PMStats {
  total: number;
  today: number;
  unread: number;
}

export interface SystemStatus {
  uptime_seconds: number;
  db_size_bytes: number;
  db_path: string;
  radio_connected: boolean;
  radio_port: string;
  python_version: string;
  bbs_version: string;
  web_version: string;
}

export interface ChartDataset {
  label: string;
  data: number[];
  borderColor?: string;
  backgroundColor?: string;
}

export interface ChartData {
  labels: string[];
  messages: number[];
  users: number[];
  datasets?: ChartDataset[];
  period: string;
}

// Settings types
export interface BBSSettings {
  bbs_name: string;
  welcome_message?: string;
  default_area: string;
  max_message_length: number;
  session_timeout?: number;
  allow_registration?: boolean;
  require_approval?: boolean;
  retention_days?: number;
  pm_retention_days: number;
  log_retention_days: number;
  enable_logging?: boolean;
  allow_ephemeral_pm: boolean;
  serial_port: string;
  baud_rate: number;
  database_path: string;
  log_path: string;
}

export interface RetentionStats {
  pm_retention_days: number;
  log_retention_days: number;
  expired_pms: number;
  expired_logs: number;
  messages_to_clean?: number;
  logs_to_clean?: number;
  last_cleanup: string | null;
  next_cleanup: string | null;
}

export interface SystemInfo {
  bbs_version: string;
  web_version: string;
  version?: string;
  python_version: string;
  platform: string;
  hostname: string;
  uptime_seconds: number;
  uptime?: string;
  db_path: string;
  db_size_bytes: number;
  database_size?: number;
  disk_usage?: number;
  db_tables: Record<string, number>;
  memory_available: number | null;
  memory_total: number | null;
}

// Pagination types
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

// API error types
export interface ApiError {
  detail: string;
  status_code?: number;
}

// Event types for WebSocket
export type WebSocketEventType =
  | 'connected'
  | 'disconnected'
  | 'connection_error'
  | 'error'
  | 'user_joined'
  | 'user_left'
  | 'user_banned'
  | 'user_unbanned'
  | 'new_message'
  | 'message_deleted'
  | 'system_status'
  | 'stats_update'
  | 'activity';

export interface WebSocketMessage {
  type: WebSocketEventType;
  data: unknown;
  timestamp: string;
}

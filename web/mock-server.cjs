/**
 * Mock API server for development testing.
 * Run with: node mock-server.js
 */

const http = require('http');

const PORT = 8080;

// Mock data
const mockUser = {
  id: 1,
  username: 'admin',
  display_name: 'Administrator',
  email: 'admin@meshbbs.local',
  is_superadmin: true,
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
  last_login: new Date().toISOString(),
};

const mockUsers = [
  { id: 1, public_key: 'ABC123DEF456', nickname: 'Mario', role: 'admin', is_banned: false, is_muted: false, last_seen: new Date().toISOString(), created_at: '2026-01-10T10:00:00Z', message_count: 42 },
  { id: 2, public_key: 'GHI789JKL012', nickname: 'Luigi', role: 'moderator', is_banned: false, is_muted: false, last_seen: new Date().toISOString(), created_at: '2026-01-11T11:00:00Z', message_count: 28 },
  { id: 3, public_key: 'MNO345PQR678', nickname: 'Peach', role: 'user', is_banned: false, is_muted: false, last_seen: new Date().toISOString(), created_at: '2026-01-12T12:00:00Z', message_count: 15 },
  { id: 4, public_key: 'STU901VWX234', nickname: 'Toad', role: 'user', is_banned: true, is_muted: false, last_seen: '2026-01-15T08:00:00Z', created_at: '2026-01-13T13:00:00Z', message_count: 5 },
];

const mockAreas = [
  { id: 1, name: 'generale', description: 'Area di discussione generale', is_public: true, is_readonly: false, message_count: 156, created_at: '2026-01-01T00:00:00Z' },
  { id: 2, name: 'tech', description: 'Discussioni tecniche', is_public: true, is_readonly: false, message_count: 89, created_at: '2026-01-02T00:00:00Z' },
  { id: 3, name: 'emergenze', description: 'Comunicazioni di emergenza', is_public: true, is_readonly: true, message_count: 12, created_at: '2026-01-03T00:00:00Z' },
  { id: 4, name: 'trading', description: 'Scambi e commercio', is_public: true, is_readonly: false, message_count: 45, created_at: '2026-01-04T00:00:00Z' },
];

const mockMessages = [
  { id: 1, area_id: 1, area_name: 'generale', sender_key: 'ABC123DEF456', sender_nickname: 'Mario', content: 'Ciao a tutti! Benvenuti nella BBS.', created_at: '2026-01-17T10:00:00Z', reply_count: 2 },
  { id: 2, area_id: 1, area_name: 'generale', sender_key: 'GHI789JKL012', sender_nickname: 'Luigi', content: 'Grazie Mario! Bel progetto.', parent_id: 1, created_at: '2026-01-17T10:05:00Z', reply_count: 0 },
  { id: 3, area_id: 2, area_name: 'tech', sender_key: 'MNO345PQR678', sender_nickname: 'Peach', content: 'Qualcuno ha esperienza con LoRa a lunga distanza?', created_at: '2026-01-17T11:00:00Z', reply_count: 1 },
  { id: 4, area_id: 2, area_name: 'tech', sender_key: 'ABC123DEF456', sender_nickname: 'Mario', content: 'Si! Con antenna esterna arrivo a 5km in pianura.', parent_id: 3, created_at: '2026-01-17T11:30:00Z', reply_count: 0 },
];

const mockLogs = [
  { id: 1, timestamp: '2026-01-17T12:00:00Z', event_type: 'USER_LOGIN', user_key: 'ABC123DEF456', details: 'Login da 192.168.1.100' },
  { id: 2, timestamp: '2026-01-17T11:55:00Z', event_type: 'MESSAGE_POSTED', user_key: 'ABC123DEF456', details: 'Messaggio #4 in area tech' },
  { id: 3, timestamp: '2026-01-17T11:30:00Z', event_type: 'USER_REGISTERED', user_key: 'STU901VWX234', details: 'Nuovo utente: Toad' },
  { id: 4, timestamp: '2026-01-17T11:00:00Z', event_type: 'MESSAGE_POSTED', user_key: 'MNO345PQR678', details: 'Messaggio #3 in area tech' },
  { id: 5, timestamp: '2026-01-17T10:05:00Z', event_type: 'MESSAGE_POSTED', user_key: 'GHI789JKL012', details: 'Messaggio #2 in area generale' },
];

const mockStats = {
  total_users: 4,
  active_users_24h: 3,
  total_messages: 156,
  total_areas: 4,
  total_private_messages: 23,
  messages_today: 12,
  uptime_seconds: 86400,
};

// JWT mock token
const MOCK_TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwidXNlcm5hbWUiOiJhZG1pbiIsImlhdCI6MTcwNTU3NjAwMH0.mock_signature';

// Parse JSON body
function parseBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => {
      try {
        resolve(body ? JSON.parse(body) : {});
      } catch (e) {
        reject(e);
      }
    });
  });
}

// Send JSON response
function sendJson(res, data, status = 200) {
  res.writeHead(status, {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, PUT, PATCH, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  });
  res.end(JSON.stringify(data));
}

// Request handler
const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const path = url.pathname;
  const method = req.method;

  console.log(`${method} ${path}`);

  // CORS preflight
  if (method === 'OPTIONS') {
    res.writeHead(204, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, PATCH, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    });
    return res.end();
  }

  try {
    // Auth routes
    if (path === '/api/v1/auth/login' && method === 'POST') {
      const body = await parseBody(req);
      if (body.username === 'admin' && body.password === 'admin') {
        return sendJson(res, {
          access_token: MOCK_TOKEN,
          refresh_token: MOCK_TOKEN,
          token_type: 'bearer',
          user: mockUser,
        });
      }
      return sendJson(res, { detail: 'Credenziali non valide' }, 401);
    }

    if (path === '/api/v1/auth/me' && method === 'GET') {
      return sendJson(res, mockUser);
    }

    if (path === '/api/v1/auth/logout' && method === 'POST') {
      return sendJson(res, { message: 'Logged out' });
    }

    // Users
    if (path === '/api/v1/users' && method === 'GET') {
      const page = parseInt(url.searchParams.get('page') || '1');
      const limit = parseInt(url.searchParams.get('limit') || '10');
      return sendJson(res, {
        items: mockUsers,
        total: mockUsers.length,
        page,
        limit,
        pages: 1,
      });
    }

    // Areas
    if (path === '/api/v1/areas' && method === 'GET') {
      return sendJson(res, {
        items: mockAreas,
        total: mockAreas.length,
        page: 1,
        limit: 10,
        pages: 1,
      });
    }

    // Messages
    if (path === '/api/v1/messages' && method === 'GET') {
      return sendJson(res, {
        items: mockMessages,
        total: mockMessages.length,
        page: 1,
        limit: 10,
        pages: 1,
      });
    }

    // Logs
    if (path === '/api/v1/logs' && method === 'GET') {
      return sendJson(res, {
        items: mockLogs,
        total: mockLogs.length,
        page: 1,
        limit: 10,
        pages: 1,
      });
    }

    // Dashboard
    if (path === '/api/v1/dashboard/stats' && method === 'GET') {
      return sendJson(res, {
        users: { total: 5, active_24h: 3, active_7d: 4, banned: 1, muted: 1, kicked: 0, admins: 1, moderators: 1 },
        messages: { total: 302, today: 15, week: 89, month: 245 },
        areas: { total: 4, public: 4, readonly: 1 },
        private_messages: { total: 23, today: 5, unread: 3 },
        system: { uptime_seconds: 172800, db_size_bytes: 2621440, db_path: '/data/bbs.db', radio_connected: true, radio_port: '/dev/ttyUSB0', python_version: '3.11.2', bbs_version: '1.4.0', web_version: '1.4.0' },
        total_users: 5,
        total_messages: 302,
        total_areas: 4,
        active_users: 3,
        user_growth: 12,
        system_status: { meshtastic_connected: true, uptime: '2 days, 0 hours' },
      });
    }

    if (path === '/api/v1/dashboard/activity' && method === 'GET') {
      return sendJson(res, {
        items: mockLogs.map(l => ({
          ...l,
          description: l.details,
        })),
        total: mockLogs.length,
      });
    }

    if (path === '/api/v1/dashboard/chart' && method === 'GET') {
      const labels = [];
      const messages = [];
      const users = [];
      for (let i = 6; i >= 0; i--) {
        const date = new Date();
        date.setDate(date.getDate() - i);
        labels.push(date.toLocaleDateString('it-IT', { weekday: 'short' }));
        messages.push(Math.floor(Math.random() * 30) + 10);
        users.push(Math.floor(Math.random() * 5) + 1);
      }
      return sendJson(res, {
        labels,
        messages,
        users,
        datasets: [{ label: 'Messages', data: messages }],
        period: '7d',
      });
    }

    if (path === '/api/v1/dashboard/top-users' && method === 'GET') {
      return sendJson(res, {
        items: mockUsers.slice(0, 5).map(u => ({
          public_key: u.public_key,
          user_id: u.public_key,
          nickname: u.nickname,
          short_name: u.nickname.substring(0, 4),
          message_count: u.message_count,
        })),
      });
    }

    // Stats
    if (path === '/api/v1/stats' && method === 'GET') {
      return sendJson(res, mockStats);
    }

    if (path === '/api/v1/stats/dashboard' && method === 'GET') {
      return sendJson(res, {
        ...mockStats,
        recent_activity: mockLogs.slice(0, 5),
        messages_by_area: mockAreas.map(a => ({ area: a.name, count: a.message_count })),
        users_by_role: [
          { role: 'admin', count: 1 },
          { role: 'moderator', count: 1 },
          { role: 'user', count: 2 },
        ],
      });
    }

    // Logs extras
    if (path === '/api/v1/logs/types' && method === 'GET') {
      return sendJson(res, ['USER_LOGIN', 'USER_LOGOUT', 'MESSAGE_POSTED', 'USER_REGISTERED', 'USER_BANNED']);
    }

    if (path === '/api/v1/logs/stats' && method === 'GET') {
      return sendJson(res, { total: mockLogs.length, today: 3 });
    }

    // Settings
    if (path === '/api/v1/settings' && method === 'GET') {
      return sendJson(res, {
        bbs_name: 'MeshBBS Demo',
        bbs_description: 'Sistema BBS per reti mesh LoRa',
        welcome_message: 'Benvenuto nella BBS!',
        pm_retention_days: 30,
        log_retention_days: 90,
        rate_limit_enabled: true,
        rate_limit_commands_per_minute: 30,
      });
    }

    if (path === '/api/v1/settings/system' && method === 'GET') {
      return sendJson(res, {
        version: '1.4.0',
        uptime: '2 days',
        database_size: '2.5 MB',
      });
    }

    if (path === '/api/v1/settings/retention' && method === 'GET') {
      return sendJson(res, {
        pm_retention_days: 30,
        log_retention_days: 90,
      });
    }

    if (path === '/api/v1/settings/backups' && method === 'GET') {
      return sendJson(res, {
        auto_backup: true,
        backups: [
          { name: 'backup_2026-01-17.db', size: '2.4 MB', date: '2026-01-17' },
        ],
      });
    }

    // WebSocket placeholder
    if (path === '/ws') {
      return sendJson(res, { message: 'WebSocket not available in mock' });
    }

    // 404
    sendJson(res, { detail: `Not found: ${path}` }, 404);

  } catch (error) {
    console.error('Error:', error);
    sendJson(res, { detail: 'Internal server error' }, 500);
  }
});

server.listen(PORT, () => {
  console.log(`\n🚀 Mock API server running at http://localhost:${PORT}`);
  console.log(`\n📝 Credenziali di test:`);
  console.log(`   Username: admin`);
  console.log(`   Password: admin`);
  console.log(`\n💡 Il frontend è disponibile su http://localhost:3000\n`);
});

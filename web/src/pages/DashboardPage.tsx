import { useEffect, useState } from 'react';
import {
  Users,
  MessageSquare,
  Folder,
  Activity,
  TrendingUp,
  Clock,
  Server,
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { Card, CardHeader, CardContent, Badge, LoadingPage, Alert } from '@/components/ui';
import { dashboardApi } from '@/api';
import type { DashboardStats, ChartData, ActivityItem, TopPoster } from '@/types';

interface StatCardProps {
  title: string;
  value: number | string;
  icon: React.ElementType;
  trend?: { value: number; positive: boolean };
  color: string;
}

function StatCard({ title, value, icon: Icon, trend, color }: StatCardProps) {
  return (
    <Card padding="md" className="flex items-center gap-4">
      <div className={`p-3 rounded-lg ${color}`}>
        <Icon className="w-6 h-6 text-white" />
      </div>
      <div className="flex-1">
        <p className="text-sm text-gray-500 dark:text-gray-400">{title}</p>
        <p className="text-2xl font-bold text-gray-900 dark:text-white">{value}</p>
        {trend && (
          <div
            className={`flex items-center text-xs ${
              trend.positive ? 'text-green-500' : 'text-red-500'
            }`}
          >
            <TrendingUp className={`w-3 h-3 mr-1 ${!trend.positive && 'rotate-180'}`} />
            {trend.value}% from last week
          </div>
        )}
      </div>
    </Card>
  );
}

function formatTimeAgo(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

export function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [chartData, setChartData] = useState<ChartData | null>(null);
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [topUsers, setTopUsers] = useState<TopPoster[]>([]);
  const [chartPeriod, setChartPeriod] = useState<'7d' | '30d' | '90d'>('7d');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true);
        const [statsData, activityData, topUsersData] = await Promise.all([
          dashboardApi.getStats(),
          dashboardApi.getActivity(10),
          dashboardApi.getTopUsers(5),
        ]);
        setStats(statsData);
        setActivity(activityData.items);
        setTopUsers(topUsersData.items);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load dashboard data');
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, []);

  useEffect(() => {
    const fetchChartData = async () => {
      try {
        const data = await dashboardApi.getChartData(chartPeriod);
        setChartData(data);
      } catch (err) {
        console.error('Failed to load chart data:', err);
      }
    };

    fetchChartData();
  }, [chartPeriod]);

  if (isLoading) {
    return <LoadingPage message="Loading dashboard..." />;
  }

  if (error) {
    return (
      <Alert variant="error" title="Error loading dashboard">
        {error}
      </Alert>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Dashboard</h1>
        <p className="text-gray-500 dark:text-gray-400">
          Overview of your MeshBBS network
        </p>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total Users"
          value={stats?.total_users || 0}
          icon={Users}
          color="bg-blue-500"
          trend={stats?.user_growth ? { value: stats.user_growth, positive: true } : undefined}
        />
        <StatCard
          title="Total Messages"
          value={stats?.total_messages || 0}
          icon={MessageSquare}
          color="bg-green-500"
        />
        <StatCard
          title="Active Areas"
          value={stats?.total_areas || 0}
          icon={Folder}
          color="bg-purple-500"
        />
        <StatCard
          title="Online Now"
          value={stats?.active_users || 0}
          icon={Activity}
          color="bg-orange-500"
        />
      </div>

      {/* Charts and activity */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Activity chart */}
        <Card padding="none" className="lg:col-span-2">
          <CardHeader
            title="Message Activity"
            action={
              <div className="flex gap-1">
                {(['7d', '30d', '90d'] as const).map((period) => (
                  <button
                    key={period}
                    onClick={() => setChartPeriod(period)}
                    className={`px-3 py-1 text-xs rounded-md transition-colors ${
                      chartPeriod === period
                        ? 'bg-primary-500 text-white'
                        : 'text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800'
                    }`}
                  >
                    {period}
                  </button>
                ))}
              </div>
            }
            className="px-6 pt-4"
          />
          <CardContent className="px-6 pb-6">
            <div className="h-64">
              {chartData?.labels && chartData.datasets && chartData.datasets.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart
                    data={chartData.labels.map((label, i) => ({
                      name: label,
                      messages: chartData.datasets![0]?.data[i] || 0,
                    }))}
                    margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis
                      dataKey="name"
                      tick={{ fontSize: 12 }}
                      stroke="#9ca3af"
                    />
                    <YAxis tick={{ fontSize: 12 }} stroke="#9ca3af" />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#1f2937',
                        border: 'none',
                        borderRadius: '8px',
                        color: '#fff',
                      }}
                    />
                    <Line
                      type="monotone"
                      dataKey="messages"
                      stroke="#3b82f6"
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full flex items-center justify-center text-gray-400">
                  No chart data available
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Top users */}
        <Card padding="none">
          <CardHeader title="Top Posters" className="px-6 pt-4" />
          <CardContent className="px-6 pb-6">
            <div className="space-y-4">
              {topUsers.length > 0 ? (
                topUsers.map((user, index) => (
                  <div key={user.user_id} className="flex items-center gap-3">
                    <div
                      className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                        index === 0
                          ? 'bg-yellow-100 text-yellow-700'
                          : index === 1
                          ? 'bg-gray-100 text-gray-700'
                          : index === 2
                          ? 'bg-orange-100 text-orange-700'
                          : 'bg-gray-50 text-gray-500'
                      }`}
                    >
                      {index + 1}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                        {user.short_name || user.user_id.substring(0, 8)}
                      </p>
                      <p className="text-xs text-gray-500">
                        {user.message_count} messages
                      </p>
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-sm text-gray-500 text-center py-4">No data yet</p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent activity and system status */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent activity */}
        <Card padding="none">
          <CardHeader title="Recent Activity" className="px-6 pt-4" />
          <CardContent className="px-6 pb-6">
            <div className="space-y-4">
              {activity.length > 0 ? (
                activity.map((item, index) => (
                  <div key={index} className="flex items-start gap-3">
                    <div className="w-8 h-8 rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
                      <Activity className="w-4 h-4 text-gray-500" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-gray-900 dark:text-white">
                        {item.description || item.event_type}
                      </p>
                      <div className="flex items-center gap-2 mt-1">
                        <Clock className="w-3 h-3 text-gray-400" />
                        <span className="text-xs text-gray-500">
                          {formatTimeAgo(item.timestamp)}
                        </span>
                        {item.event_type && (
                          <Badge variant="default" size="sm">
                            {item.event_type}
                          </Badge>
                        )}
                      </div>
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-sm text-gray-500 text-center py-4">
                  No recent activity
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* System status */}
        <Card padding="none">
          <CardHeader title="System Status" className="px-6 pt-4" />
          <CardContent className="px-6 pb-6">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Server className="w-5 h-5 text-gray-400" />
                  <span className="text-sm text-gray-700 dark:text-gray-300">
                    BBS Server
                  </span>
                </div>
                <Badge variant="success">Online</Badge>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Activity className="w-5 h-5 text-gray-400" />
                  <span className="text-sm text-gray-700 dark:text-gray-300">
                    Meshtastic Connection
                  </span>
                </div>
                <Badge variant={stats?.system_status?.meshtastic_connected ? 'success' : 'danger'}>
                  {stats?.system_status?.meshtastic_connected ? 'Connected' : 'Disconnected'}
                </Badge>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Clock className="w-5 h-5 text-gray-400" />
                  <span className="text-sm text-gray-700 dark:text-gray-300">Uptime</span>
                </div>
                <span className="text-sm text-gray-500">
                  {stats?.system_status?.uptime || 'N/A'}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

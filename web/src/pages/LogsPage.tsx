import { useEffect, useState, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Search,
  Filter,
  Download,
  Trash2,
  Calendar,
  Activity,
} from 'lucide-react';
import {
  Card,
  Input,
  Select,
  Button,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableHeader,
  TableCell,
  TableEmpty,
  Pagination,
  PaginationInfo,
  Badge,
  LoadingPage,
  Alert,
  Modal,
} from '@/components/ui';
import { useToast } from '@/components/ui';
import { logsApi, type LogFilters, type EventTypeInfo, type LogStatsResponse } from '@/api';
import type { LogEntry, PaginatedResponse } from '@/types';

export function LogsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { success, error: showError } = useToast();

  const [logs, setLogs] = useState<PaginatedResponse<LogEntry> | null>(null);
  const [stats, setStats] = useState<LogStatsResponse | null>(null);
  const [eventTypes, setEventTypes] = useState<EventTypeInfo[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [search, setSearch] = useState(searchParams.get('search') || '');
  const [eventType, setEventType] = useState(searchParams.get('type') || 'all');
  const [page, setPage] = useState(parseInt(searchParams.get('page') || '1'));
  const perPage = 50;

  // Modals
  const [clearDays, setClearDays] = useState('30');
  const [clearConfirm, setClearConfirm] = useState(false);
  const [exportModal, setExportModal] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchLogs = useCallback(async () => {
    try {
      setIsLoading(true);
      const filters: LogFilters = {
        page,
        per_page: perPage,
      };
      if (search) filters.search = search;
      if (eventType !== 'all') filters.event_type = eventType;

      const data = await logsApi.list(filters);
      setLogs(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load logs');
    } finally {
      setIsLoading(false);
    }
  }, [page, search, eventType]);

  const fetchStats = useCallback(async () => {
    try {
      const data = await logsApi.getStats();
      setStats(data);
    } catch (err) {
      console.error('Failed to load stats:', err);
    }
  }, []);

  const fetchEventTypes = useCallback(async () => {
    try {
      const data = await logsApi.getEventTypes();
      setEventTypes(data.types);
    } catch (err) {
      console.error('Failed to load event types:', err);
    }
  }, []);

  useEffect(() => {
    fetchEventTypes();
    fetchStats();
  }, [fetchEventTypes, fetchStats]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  useEffect(() => {
    const params = new URLSearchParams();
    if (search) params.set('search', search);
    if (eventType !== 'all') params.set('type', eventType);
    if (page > 1) params.set('page', page.toString());
    setSearchParams(params);
  }, [search, eventType, page, setSearchParams]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchLogs();
  };

  const handleClearOld = async () => {
    const days = parseInt(clearDays);
    if (isNaN(days) || days < 1) return;

    setIsSubmitting(true);
    try {
      const result = await logsApi.clearOld(days);
      success(`Deleted ${result.deleted_count} old log entries`);
      setClearConfirm(false);
      fetchLogs();
      fetchStats();
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Failed to clear logs');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleExport = async (format: 'json' | 'csv') => {
    try {
      const data = await logsApi.export(format);
      const blob = format === 'csv' ? (data as Blob) : new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `logs-export.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      success(`Logs exported as ${format.toUpperCase()}`);
      setExportModal(false);
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Failed to export logs');
    }
  };

  const formatDate = (dateStr?: string | null) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleString();
  };

  const getEventBadgeVariant = (type: string): 'default' | 'success' | 'warning' | 'danger' | 'info' => {
    if (type.includes('error') || type.includes('fail')) return 'danger';
    if (type.includes('success') || type.includes('login')) return 'success';
    if (type.includes('warning') || type.includes('ban') || type.includes('kick')) return 'warning';
    if (type.includes('message') || type.includes('create')) return 'info';
    return 'default';
  };

  const typeOptions = [
    { value: 'all', label: 'All Events' },
    ...eventTypes.map((t) => ({ value: t.value, label: t.name })),
  ];

  if (isLoading && !logs) {
    return <LoadingPage message="Loading logs..." />;
  }

  if (error && !logs) {
    return (
      <Alert variant="error" title="Error loading logs">
        {error}
      </Alert>
    );
  }

  const totalPages = Math.ceil((logs?.total || 0) / perPage);

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Activity Logs</h1>
          <p className="text-gray-500 dark:text-gray-400">
            View system activity and events
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="secondary"
            icon={<Download className="w-4 h-4" />}
            onClick={() => setExportModal(true)}
          >
            Export
          </Button>
          <Button
            variant="danger"
            icon={<Trash2 className="w-4 h-4" />}
            onClick={() => setClearConfirm(true)}
          >
            Clear Old
          </Button>
        </div>
      </div>

      {/* Stats cards */}
      {stats && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Card padding="md">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-lg bg-blue-500">
                <Activity className="w-6 h-6 text-white" />
              </div>
              <div>
                <p className="text-sm text-gray-500">Total Entries</p>
                <p className="text-2xl font-bold">{stats.total_entries.toLocaleString()}</p>
              </div>
            </div>
          </Card>
          <Card padding="md">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-lg bg-green-500">
                <Calendar className="w-6 h-6 text-white" />
              </div>
              <div>
                <p className="text-sm text-gray-500">Today</p>
                <p className="text-2xl font-bold">{stats.entries_today.toLocaleString()}</p>
              </div>
            </div>
          </Card>
          <Card padding="md">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-lg bg-purple-500">
                <Calendar className="w-6 h-6 text-white" />
              </div>
              <div>
                <p className="text-sm text-gray-500">This Week</p>
                <p className="text-2xl font-bold">{stats.entries_week.toLocaleString()}</p>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* Filters */}
      <Card padding="md">
        <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1">
            <Input
              placeholder="Search logs..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              leftIcon={<Search className="w-4 h-4" />}
            />
          </div>
          <div className="flex gap-2">
            <Select
              options={typeOptions}
              value={eventType}
              onChange={(e) => {
                setEventType(e.target.value);
                setPage(1);
              }}
              className="w-40"
            />
            <Button type="submit" variant="primary" icon={<Filter className="w-4 h-4" />}>
              Filter
            </Button>
          </div>
        </form>
      </Card>

      {/* Logs table */}
      <Card padding="none">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeader>Timestamp</TableHeader>
              <TableHeader>Event</TableHeader>
              <TableHeader>User</TableHeader>
              <TableHeader>Details</TableHeader>
            </TableRow>
          </TableHead>
          <TableBody>
            {logs?.items && logs.items.length > 0 ? (
              logs.items.map((log) => (
                <TableRow key={log.id}>
                  <TableCell>
                    <span className="text-sm text-gray-500 whitespace-nowrap">
                      {formatDate(log.timestamp)}
                    </span>
                  </TableCell>
                  <TableCell>
                    <Badge variant={getEventBadgeVariant(log.event_type)}>
                      {log.event_type}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <span className="text-sm text-gray-700 dark:text-gray-300">
                      {log.user_key ? (
                        <span className="font-mono text-xs">
                          {log.user_key.substring(0, 12)}...
                        </span>
                      ) : (
                        'System'
                      )}
                    </span>
                  </TableCell>
                  <TableCell>
                    <span className="text-sm text-gray-500 line-clamp-2">
                      {log.details || '-'}
                    </span>
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <TableEmpty colSpan={4} message="No logs found" />
            )}
          </TableBody>
        </Table>

        {/* Pagination */}
        {logs && logs.total > perPage && (
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 px-4 py-3 border-t border-gray-200 dark:border-gray-700">
            <PaginationInfo currentPage={page} perPage={perPage} total={logs.total} />
            <Pagination
              currentPage={page}
              totalPages={totalPages}
              onPageChange={setPage}
            />
          </div>
        )}
      </Card>

      {/* Clear Old Logs Modal */}
      <Modal
        isOpen={clearConfirm}
        onClose={() => setClearConfirm(false)}
        title="Clear Old Logs"
        size="sm"
      >
        <div className="space-y-4">
          <p className="text-gray-600 dark:text-gray-400">
            Delete log entries older than the specified number of days.
          </p>
          <Input
            label="Days to keep"
            type="number"
            value={clearDays}
            onChange={(e) => setClearDays(e.target.value)}
            min="1"
            hint="Logs older than this will be deleted"
          />
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="ghost" onClick={() => setClearConfirm(false)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              onClick={handleClearOld}
              loading={isSubmitting}
            >
              Clear Logs
            </Button>
          </div>
        </div>
      </Modal>

      {/* Export Modal */}
      <Modal
        isOpen={exportModal}
        onClose={() => setExportModal(false)}
        title="Export Logs"
        size="sm"
      >
        <div className="space-y-4">
          <p className="text-gray-600 dark:text-gray-400">
            Choose a format to export the logs.
          </p>
          <div className="flex gap-3">
            <Button
              variant="secondary"
              onClick={() => handleExport('json')}
              className="flex-1"
            >
              Export as JSON
            </Button>
            <Button
              variant="secondary"
              onClick={() => handleExport('csv')}
              className="flex-1"
            >
              Export as CSV
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

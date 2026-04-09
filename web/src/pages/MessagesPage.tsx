import { useEffect, useState, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Search,
  Filter,
  Trash2,
  Eye,
  MessageSquare,
  Calendar,
  User as UserIcon,
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
  Checkbox,
  LoadingPage,
  Alert,
  Modal,
  ConfirmModal,
} from '@/components/ui';
import { useToast } from '@/components/ui';
import { messagesApi, areasApi, type MessageFilters } from '@/api';
import type { Message, Area, PaginatedResponse } from '@/types';

export function MessagesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { success, error: showError } = useToast();

  const [messages, setMessages] = useState<PaginatedResponse<Message> | null>(null);
  const [areas, setAreas] = useState<Area[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [search, setSearch] = useState(searchParams.get('search') || '');
  const [area, setArea] = useState(searchParams.get('area') || 'all');
  const [page, setPage] = useState(parseInt(searchParams.get('page') || '1'));
  const perPage = 20;

  // Selection
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  // Modals
  const [viewMessage, setViewMessage] = useState<Message | null>(null);
  const [deleteMessage, setDeleteMessage] = useState<Message | null>(null);
  const [bulkDeleteConfirm, setBulkDeleteConfirm] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchMessages = useCallback(async () => {
    try {
      setIsLoading(true);
      const filters: MessageFilters = {
        page,
        per_page: perPage,
      };
      if (search) filters.search = search;
      if (area !== 'all') filters.area = area;

      const data = await messagesApi.list(filters);
      setMessages(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load messages');
    } finally {
      setIsLoading(false);
    }
  }, [page, search, area]);

  const fetchAreas = useCallback(async () => {
    try {
      const data = await areasApi.list(true);
      setAreas(data.items);
    } catch (err) {
      console.error('Failed to load areas:', err);
    }
  }, []);

  useEffect(() => {
    fetchAreas();
  }, [fetchAreas]);

  useEffect(() => {
    fetchMessages();
  }, [fetchMessages]);

  useEffect(() => {
    const params = new URLSearchParams();
    if (search) params.set('search', search);
    if (area !== 'all') params.set('area', area);
    if (page > 1) params.set('page', page.toString());
    setSearchParams(params);
  }, [search, area, page, setSearchParams]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchMessages();
  };

  const handleDelete = async () => {
    if (!deleteMessage) return;

    setIsSubmitting(true);
    try {
      await messagesApi.delete(deleteMessage.id);
      success('Message deleted successfully');
      setDeleteMessage(null);
      fetchMessages();
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Failed to delete message');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleBulkDelete = async () => {
    if (selectedIds.size === 0) return;

    setIsSubmitting(true);
    try {
      const result = await messagesApi.bulkDelete(Array.from(selectedIds));
      success(`${result.success_count} messages deleted successfully`);
      if (result.failed_count > 0) {
        showError(`Failed to delete ${result.failed_count} messages`);
      }
      setSelectedIds(new Set());
      setBulkDeleteConfirm(false);
      fetchMessages();
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Failed to delete messages');
    } finally {
      setIsSubmitting(false);
    }
  };

  const toggleSelection = (id: number) => {
    const newSelection = new Set(selectedIds);
    if (newSelection.has(id)) {
      newSelection.delete(id);
    } else {
      newSelection.add(id);
    }
    setSelectedIds(newSelection);
  };

  const toggleSelectAll = () => {
    if (!messages?.items) return;

    if (selectedIds.size === messages.items.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(messages.items.map((m) => m.id)));
    }
  };

  const formatDate = (dateStr?: string | null) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleString();
  };

  const areaOptions = [
    { value: 'all', label: 'All Areas' },
    ...areas.map((a) => ({ value: a.name, label: a.name })),
  ];

  if (isLoading && !messages) {
    return <LoadingPage message="Loading messages..." />;
  }

  if (error && !messages) {
    return (
      <Alert variant="error" title="Error loading messages">
        {error}
      </Alert>
    );
  }

  const totalPages = Math.ceil((messages?.total || 0) / perPage);
  const allSelected = messages?.items && selectedIds.size === messages.items.length;

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Messages</h1>
          <p className="text-gray-500 dark:text-gray-400">
            View and manage BBS messages
          </p>
        </div>
        {selectedIds.size > 0 && (
          <Button
            variant="danger"
            icon={<Trash2 className="w-4 h-4" />}
            onClick={() => setBulkDeleteConfirm(true)}
          >
            Delete ({selectedIds.size})
          </Button>
        )}
      </div>

      {/* Filters */}
      <Card padding="md">
        <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1">
            <Input
              placeholder="Search messages..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              leftIcon={<Search className="w-4 h-4" />}
            />
          </div>
          <div className="flex gap-2">
            <Select
              options={areaOptions}
              value={area}
              onChange={(e) => {
                setArea(e.target.value);
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

      {/* Messages table */}
      <Card padding="none">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeader className="w-10">
                <Checkbox
                  checked={allSelected}
                  onChange={toggleSelectAll}
                  aria-label="Select all"
                />
              </TableHeader>
              <TableHeader>Message</TableHeader>
              <TableHeader>Area</TableHeader>
              <TableHeader>Sender</TableHeader>
              <TableHeader>Date</TableHeader>
              <TableHeader className="text-right">Actions</TableHeader>
            </TableRow>
          </TableHead>
          <TableBody>
            {messages?.items && messages.items.length > 0 ? (
              messages.items.map((message) => (
                <TableRow key={message.id}>
                  <TableCell>
                    <Checkbox
                      checked={selectedIds.has(message.id)}
                      onChange={() => toggleSelection(message.id)}
                      aria-label={`Select message ${message.id}`}
                    />
                  </TableCell>
                  <TableCell>
                    <div className="max-w-md">
                      {message.subject && (
                        <p className="font-medium text-gray-900 dark:text-white truncate">
                          {message.subject}
                        </p>
                      )}
                      <p className="text-sm text-gray-500 truncate">
                        {message.content.substring(0, 100)}
                        {message.content.length > 100 && '...'}
                      </p>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="info">{message.area}</Badge>
                  </TableCell>
                  <TableCell>
                    <span className="text-sm text-gray-700 dark:text-gray-300">
                      {message.sender_short_name || message.sender_id?.substring(0, 8) || 'Unknown'}
                    </span>
                  </TableCell>
                  <TableCell>
                    <span className="text-sm text-gray-500">
                      {formatDate(message.timestamp || message.created_at)}
                    </span>
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <button
                        onClick={() => setViewMessage(message)}
                        className="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-800 rounded text-gray-500"
                        aria-label="View message"
                      >
                        <Eye className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => setDeleteMessage(message)}
                        className="p-1.5 hover:bg-red-100 dark:hover:bg-red-900/30 rounded text-red-500"
                        aria-label="Delete message"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <TableEmpty colSpan={6} message="No messages found" />
            )}
          </TableBody>
        </Table>

        {/* Pagination */}
        {messages && messages.total > perPage && (
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 px-4 py-3 border-t border-gray-200 dark:border-gray-700">
            <PaginationInfo currentPage={page} perPage={perPage} total={messages.total} />
            <Pagination
              currentPage={page}
              totalPages={totalPages}
              onPageChange={setPage}
            />
          </div>
        )}
      </Card>

      {/* View Message Modal */}
      <Modal
        isOpen={!!viewMessage}
        onClose={() => setViewMessage(null)}
        title="Message Details"
        size="lg"
      >
        {viewMessage && (
          <div className="space-y-4">
            {viewMessage.subject && (
              <div>
                <p className="text-sm text-gray-500">Subject</p>
                <p className="font-medium text-gray-900 dark:text-white">
                  {viewMessage.subject}
                </p>
              </div>
            )}
            <div className="grid grid-cols-2 gap-4">
              <div className="flex items-center gap-2">
                <UserIcon className="w-4 h-4 text-gray-400" />
                <div>
                  <p className="text-xs text-gray-500">Sender</p>
                  <p className="text-sm font-medium">
                    {viewMessage.sender_short_name || viewMessage.sender_id || 'Unknown'}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-gray-400" />
                <div>
                  <p className="text-xs text-gray-500">Area</p>
                  <p className="text-sm font-medium">{viewMessage.area}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Calendar className="w-4 h-4 text-gray-400" />
                <div>
                  <p className="text-xs text-gray-500">Date</p>
                  <p className="text-sm font-medium">
                    {formatDate(viewMessage.timestamp || viewMessage.created_at)}
                  </p>
                </div>
              </div>
            </div>
            <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
              <p className="text-sm text-gray-500 mb-2">Content</p>
              <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4">
                <p className="text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
                  {viewMessage.content}
                </p>
              </div>
            </div>
          </div>
        )}
      </Modal>

      {/* Delete Confirmation */}
      <ConfirmModal
        isOpen={!!deleteMessage}
        onClose={() => setDeleteMessage(null)}
        onConfirm={handleDelete}
        title="Delete Message"
        message="Are you sure you want to delete this message? This action cannot be undone."
        confirmText="Delete"
        variant="danger"
        loading={isSubmitting}
      />

      {/* Bulk Delete Confirmation */}
      <ConfirmModal
        isOpen={bulkDeleteConfirm}
        onClose={() => setBulkDeleteConfirm(false)}
        onConfirm={handleBulkDelete}
        title="Delete Selected Messages"
        message={`Are you sure you want to delete ${selectedIds.size} messages? This action cannot be undone.`}
        confirmText="Delete All"
        variant="danger"
        loading={isSubmitting}
      />
    </div>
  );
}

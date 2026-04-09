import { useEffect, useState, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Search,
  Filter,
  MoreVertical,
  Ban,
  VolumeX,
  UserX,
  Shield,
  ShieldOff,
  Eye,
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
  StatusBadge,
  RoleBadge,
  Dropdown,
  DropdownItem,
  DropdownDivider,
  LoadingPage,
  Alert,
  Modal,
  ConfirmModal,
  Textarea,
} from '@/components/ui';
import { useToast } from '@/components/ui';
import { usersApi, type UserFilters } from '@/api';
import type { User, PaginatedResponse } from '@/types';

const roleOptions = [
  { value: 'all', label: 'All Roles' },
  { value: 'admin', label: 'Admin' },
  { value: 'moderator', label: 'Moderator' },
  { value: 'user', label: 'User' },
];

const statusOptions = [
  { value: 'all', label: 'All Status' },
  { value: 'active', label: 'Active' },
  { value: 'banned', label: 'Banned' },
  { value: 'muted', label: 'Muted' },
  { value: 'kicked', label: 'Kicked' },
];

type ModerationAction = 'ban' | 'unban' | 'mute' | 'unmute' | 'kick' | 'unkick' | 'promote' | 'demote';

export function UsersPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { success, error: showError } = useToast();

  const [users, setUsers] = useState<PaginatedResponse<User> | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [search, setSearch] = useState(searchParams.get('search') || '');
  const [role, setRole] = useState<string>(searchParams.get('role') || 'all');
  const [status, setStatus] = useState<string>(searchParams.get('status') || 'all');
  const [page, setPage] = useState(parseInt(searchParams.get('page') || '1'));
  const perPage = 20;

  // Moderation modal
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [moderationAction, setModerationAction] = useState<ModerationAction | null>(null);
  const [moderationReason, setModerationReason] = useState('');
  const [moderationDuration, setModerationDuration] = useState('24');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // User details modal
  const [viewUser, setViewUser] = useState<User | null>(null);

  const fetchUsers = useCallback(async () => {
    try {
      setIsLoading(true);
      const filters: UserFilters = {
        page,
        per_page: perPage,
      };
      if (search) filters.search = search;
      if (role !== 'all') filters.role = role as UserFilters['role'];
      if (status !== 'all') filters.status = status as UserFilters['status'];

      const data = await usersApi.list(filters);
      setUsers(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load users');
    } finally {
      setIsLoading(false);
    }
  }, [page, search, role, status]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  useEffect(() => {
    const params = new URLSearchParams();
    if (search) params.set('search', search);
    if (role !== 'all') params.set('role', role);
    if (status !== 'all') params.set('status', status);
    if (page > 1) params.set('page', page.toString());
    setSearchParams(params);
  }, [search, role, status, page, setSearchParams]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchUsers();
  };

  const handleModerationSubmit = async () => {
    if (!selectedUser || !moderationAction) return;

    setIsSubmitting(true);
    try {
      const duration = parseInt(moderationDuration);

      switch (moderationAction) {
        case 'ban':
          await usersApi.ban(selectedUser.public_key, moderationReason, duration || undefined);
          success(`User ${selectedUser.short_name || 'User'} has been banned`);
          break;
        case 'unban':
          await usersApi.unban(selectedUser.public_key);
          success(`User ${selectedUser.short_name || 'User'} has been unbanned`);
          break;
        case 'mute':
          await usersApi.mute(selectedUser.public_key, moderationReason, duration || undefined);
          success(`User ${selectedUser.short_name || 'User'} has been muted`);
          break;
        case 'unmute':
          await usersApi.unmute(selectedUser.public_key);
          success(`User ${selectedUser.short_name || 'User'} has been unmuted`);
          break;
        case 'kick':
          await usersApi.kick(selectedUser.public_key, moderationReason, duration);
          success(`User ${selectedUser.short_name || 'User'} has been kicked`);
          break;
        case 'unkick':
          await usersApi.unkick(selectedUser.public_key);
          success(`User ${selectedUser.short_name || 'User'} has been unkicked`);
          break;
        case 'promote':
          await usersApi.promote(selectedUser.public_key, 'moderator');
          success(`User ${selectedUser.short_name || 'User'} has been promoted to moderator`);
          break;
        case 'demote':
          await usersApi.demote(selectedUser.public_key);
          success(`User ${selectedUser.short_name || 'User'} has been demoted`);
          break;
      }

      fetchUsers();
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Moderation action failed');
    } finally {
      setIsSubmitting(false);
      closeModeration();
    }
  };

  const closeModeration = () => {
    setSelectedUser(null);
    setModerationAction(null);
    setModerationReason('');
    setModerationDuration('24');
  };

  const openModeration = (user: User, action: ModerationAction) => {
    setSelectedUser(user);
    setModerationAction(action);
  };

  const needsReason = ['ban', 'mute', 'kick'].includes(moderationAction || '');
  const needsDuration = ['kick'].includes(moderationAction || '');

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleDateString();
  };

  if (isLoading && !users) {
    return <LoadingPage message="Loading users..." />;
  }

  if (error && !users) {
    return (
      <Alert variant="error" title="Error loading users">
        {error}
      </Alert>
    );
  }

  const totalPages = Math.ceil((users?.total || 0) / perPage);

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Users</h1>
        <p className="text-gray-500 dark:text-gray-400">
          Manage BBS users and permissions
        </p>
      </div>

      {/* Filters */}
      <Card padding="md">
        <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1">
            <Input
              placeholder="Search by name or ID..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              leftIcon={<Search className="w-4 h-4" />}
            />
          </div>
          <div className="flex gap-2">
            <Select
              options={roleOptions}
              value={role}
              onChange={(e) => {
                setRole(e.target.value);
                setPage(1);
              }}
              className="w-36"
            />
            <Select
              options={statusOptions}
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
                setPage(1);
              }}
              className="w-36"
            />
            <Button type="submit" variant="primary" icon={<Filter className="w-4 h-4" />}>
              Filter
            </Button>
          </div>
        </form>
      </Card>

      {/* Users table */}
      <Card padding="none">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeader>User</TableHeader>
              <TableHeader>Role</TableHeader>
              <TableHeader>Status</TableHeader>
              <TableHeader>Messages</TableHeader>
              <TableHeader>Last Seen</TableHeader>
              <TableHeader className="text-right">Actions</TableHeader>
            </TableRow>
          </TableHead>
          <TableBody>
            {users?.items && users.items.length > 0 ? (
              users.items.map((user) => (
                <TableRow key={user.public_key}>
                  <TableCell>
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-primary-100 dark:bg-primary-900 flex items-center justify-center text-primary-600 dark:text-primary-400 text-sm font-medium">
                        {(user.short_name || user.public_key).charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <p className="font-medium text-gray-900 dark:text-white">
                          {user.short_name || 'Unknown'}
                        </p>
                        <p className="text-xs text-gray-500 font-mono">
                          {user.public_key.substring(0, 16)}...
                        </p>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>
                    <RoleBadge role={user.role || 'user'} />
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={user.status || 'active'} />
                  </TableCell>
                  <TableCell>{user.message_count || 0}</TableCell>
                  <TableCell>{formatDate(user.last_seen)}</TableCell>
                  <TableCell className="text-right">
                    <Dropdown
                      trigger={
                        <button className="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded">
                          <MoreVertical className="w-4 h-4 text-gray-500" />
                        </button>
                      }
                      align="right"
                    >
                      <DropdownItem
                        onClick={() => setViewUser(user)}
                        icon={<Eye className="w-4 h-4" />}
                      >
                        View Details
                      </DropdownItem>
                      <DropdownDivider />
                      {user.status === 'banned' ? (
                        <DropdownItem
                          onClick={() => openModeration(user, 'unban')}
                          icon={<Ban className="w-4 h-4" />}
                        >
                          Unban
                        </DropdownItem>
                      ) : (
                        <DropdownItem
                          onClick={() => openModeration(user, 'ban')}
                          icon={<Ban className="w-4 h-4" />}
                          danger
                        >
                          Ban
                        </DropdownItem>
                      )}
                      {user.status === 'muted' ? (
                        <DropdownItem
                          onClick={() => openModeration(user, 'unmute')}
                          icon={<VolumeX className="w-4 h-4" />}
                        >
                          Unmute
                        </DropdownItem>
                      ) : (
                        <DropdownItem
                          onClick={() => openModeration(user, 'mute')}
                          icon={<VolumeX className="w-4 h-4" />}
                          danger
                        >
                          Mute
                        </DropdownItem>
                      )}
                      {user.status === 'kicked' ? (
                        <DropdownItem
                          onClick={() => openModeration(user, 'unkick')}
                          icon={<UserX className="w-4 h-4" />}
                        >
                          Unkick
                        </DropdownItem>
                      ) : (
                        <DropdownItem
                          onClick={() => openModeration(user, 'kick')}
                          icon={<UserX className="w-4 h-4" />}
                          danger
                        >
                          Kick
                        </DropdownItem>
                      )}
                      <DropdownDivider />
                      {user.role === 'moderator' ? (
                        <DropdownItem
                          onClick={() => openModeration(user, 'demote')}
                          icon={<ShieldOff className="w-4 h-4" />}
                        >
                          Demote
                        </DropdownItem>
                      ) : user.role !== 'admin' ? (
                        <DropdownItem
                          onClick={() => openModeration(user, 'promote')}
                          icon={<Shield className="w-4 h-4" />}
                        >
                          Promote to Mod
                        </DropdownItem>
                      ) : null}
                    </Dropdown>
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <TableEmpty colSpan={6} message="No users found" />
            )}
          </TableBody>
        </Table>

        {/* Pagination */}
        {users && users.total > perPage && (
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 px-4 py-3 border-t border-gray-200 dark:border-gray-700">
            <PaginationInfo currentPage={page} perPage={perPage} total={users.total} />
            <Pagination
              currentPage={page}
              totalPages={totalPages}
              onPageChange={setPage}
            />
          </div>
        )}
      </Card>

      {/* Moderation Modal */}
      {moderationAction && needsReason && (
        <Modal
          isOpen={!!selectedUser}
          onClose={closeModeration}
          title={`${moderationAction.charAt(0).toUpperCase()}${moderationAction.slice(1)} User`}
          size="sm"
        >
          <div className="space-y-4">
            <p className="text-gray-600 dark:text-gray-400">
              {moderationAction === 'ban' && 'This user will be banned from the BBS.'}
              {moderationAction === 'mute' && 'This user will not be able to send messages.'}
              {moderationAction === 'kick' && 'This user will be temporarily removed.'}
            </p>
            <Textarea
              label="Reason"
              value={moderationReason}
              onChange={(e) => setModerationReason(e.target.value)}
              placeholder="Enter a reason..."
              required
            />
            {needsDuration && (
              <Input
                label="Duration (hours)"
                type="number"
                value={moderationDuration}
                onChange={(e) => setModerationDuration(e.target.value)}
                min="1"
                required
              />
            )}
            <div className="flex justify-end gap-3 pt-2">
              <Button variant="ghost" onClick={closeModeration}>
                Cancel
              </Button>
              <Button
                variant="danger"
                onClick={handleModerationSubmit}
                loading={isSubmitting}
                disabled={!moderationReason.trim()}
              >
                Confirm
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Confirm Modal for actions without reason */}
      {moderationAction && !needsReason && (
        <ConfirmModal
          isOpen={!!selectedUser}
          onClose={closeModeration}
          onConfirm={handleModerationSubmit}
          title={`${moderationAction.charAt(0).toUpperCase()}${moderationAction.slice(1)} User`}
          message={`Are you sure you want to ${moderationAction} ${selectedUser?.short_name || 'this user'}?`}
          confirmText={moderationAction.charAt(0).toUpperCase() + moderationAction.slice(1)}
          variant={['unban', 'unmute', 'unkick', 'promote'].includes(moderationAction) ? 'primary' : 'danger'}
          loading={isSubmitting}
        />
      )}

      {/* User Details Modal */}
      <Modal
        isOpen={!!viewUser}
        onClose={() => setViewUser(null)}
        title="User Details"
        size="md"
      >
        {viewUser && (
          <div className="space-y-4">
            <div className="flex items-center gap-4">
              <div className="w-16 h-16 rounded-full bg-primary-100 dark:bg-primary-900 flex items-center justify-center text-primary-600 dark:text-primary-400 text-2xl font-medium">
                {(viewUser.short_name || viewUser.public_key).charAt(0).toUpperCase()}
              </div>
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                  {viewUser.short_name || 'Unknown'}
                </h3>
                <p className="text-sm text-gray-500 font-mono">{viewUser.public_key}</p>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4 pt-4 border-t border-gray-200 dark:border-gray-700">
              <div>
                <p className="text-sm text-gray-500">Role</p>
                <RoleBadge role={viewUser.role || 'user'} />
              </div>
              <div>
                <p className="text-sm text-gray-500">Status</p>
                <StatusBadge status={viewUser.status || 'active'} />
              </div>
              <div>
                <p className="text-sm text-gray-500">Messages</p>
                <p className="font-medium">{viewUser.message_count || 0}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Last Seen</p>
                <p className="font-medium">{formatDate(viewUser.last_seen)}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">First Seen</p>
                <p className="font-medium">{formatDate(viewUser.first_seen)}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Long Name</p>
                <p className="font-medium">{viewUser.long_name || 'N/A'}</p>
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

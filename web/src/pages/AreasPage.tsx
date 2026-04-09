import { useEffect, useState, useCallback } from 'react';
import {
  Plus,
  MoreVertical,
  Edit,
  Trash2,
  Eye,
  Lock,
  Unlock,
  Globe,
  EyeOff,
} from 'lucide-react';
import {
  Card,
  Button,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableHeader,
  TableCell,
  TableEmpty,
  Badge,
  Dropdown,
  DropdownItem,
  DropdownDivider,
  LoadingPage,
  Alert,
  Modal,
  ConfirmModal,
  Input,
  Textarea,
  Switch,
} from '@/components/ui';
import { useToast } from '@/components/ui';
import { areasApi } from '@/api';
import type { Area } from '@/types';

interface AreaFormData {
  name: string;
  description: string;
  is_public: boolean;
  is_readonly: boolean;
}

const initialFormData: AreaFormData = {
  name: '',
  description: '',
  is_public: true,
  is_readonly: false,
};

export function AreasPage() {
  const { success, error: showError } = useToast();

  const [areas, setAreas] = useState<Area[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modal states
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [editArea, setEditArea] = useState<Area | null>(null);
  const [deleteArea, setDeleteArea] = useState<Area | null>(null);
  const [viewArea, setViewArea] = useState<Area | null>(null);

  // Form state
  const [formData, setFormData] = useState<AreaFormData>(initialFormData);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchAreas = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await areasApi.list(true);
      setAreas(data.items);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load areas');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAreas();
  }, [fetchAreas]);

  const handleCreate = async () => {
    if (!formData.name.trim()) return;

    setIsSubmitting(true);
    try {
      await areasApi.create({
        name: formData.name.trim(),
        description: formData.description.trim() || undefined,
        is_public: formData.is_public,
        is_readonly: formData.is_readonly,
      });
      success(`Area "${formData.name}" created successfully`);
      setIsCreateModalOpen(false);
      setFormData(initialFormData);
      fetchAreas();
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Failed to create area');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUpdate = async () => {
    if (!editArea) return;

    setIsSubmitting(true);
    try {
      await areasApi.update(editArea.name, {
        description: formData.description.trim() || undefined,
        is_public: formData.is_public,
        is_readonly: formData.is_readonly,
      });
      success(`Area "${editArea.name}" updated successfully`);
      setEditArea(null);
      setFormData(initialFormData);
      fetchAreas();
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Failed to update area');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteArea) return;

    setIsSubmitting(true);
    try {
      await areasApi.delete(deleteArea.name, true);
      success(`Area "${deleteArea.name}" deleted successfully`);
      setDeleteArea(null);
      fetchAreas();
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Failed to delete area');
    } finally {
      setIsSubmitting(false);
    }
  };

  const openEditModal = (area: Area) => {
    setFormData({
      name: area.name,
      description: area.description || '',
      is_public: area.is_public,
      is_readonly: area.is_readonly,
    });
    setEditArea(area);
  };

  const closeCreateModal = () => {
    setIsCreateModalOpen(false);
    setFormData(initialFormData);
  };

  const closeEditModal = () => {
    setEditArea(null);
    setFormData(initialFormData);
  };

  if (isLoading && areas.length === 0) {
    return <LoadingPage message="Loading areas..." />;
  }

  if (error && areas.length === 0) {
    return (
      <Alert variant="error" title="Error loading areas">
        {error}
      </Alert>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Areas</h1>
          <p className="text-gray-500 dark:text-gray-400">
            Manage message boards and discussion areas
          </p>
        </div>
        <Button
          variant="primary"
          icon={<Plus className="w-4 h-4" />}
          onClick={() => setIsCreateModalOpen(true)}
        >
          Create Area
        </Button>
      </div>

      {/* Areas table */}
      <Card padding="none">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeader>Name</TableHeader>
              <TableHeader>Description</TableHeader>
              <TableHeader>Messages</TableHeader>
              <TableHeader>Visibility</TableHeader>
              <TableHeader>Status</TableHeader>
              <TableHeader className="text-right">Actions</TableHeader>
            </TableRow>
          </TableHead>
          <TableBody>
            {areas.length > 0 ? (
              areas.map((area) => (
                <TableRow key={area.name}>
                  <TableCell>
                    <span className="font-medium text-gray-900 dark:text-white">
                      {area.name}
                    </span>
                  </TableCell>
                  <TableCell>
                    <span className="text-gray-500 dark:text-gray-400 line-clamp-1">
                      {area.description || '-'}
                    </span>
                  </TableCell>
                  <TableCell>{area.message_count || 0}</TableCell>
                  <TableCell>
                    {area.is_public ? (
                      <Badge variant="success">
                        <Globe className="w-3 h-3 mr-1" />
                        Public
                      </Badge>
                    ) : (
                      <Badge variant="default">
                        <EyeOff className="w-3 h-3 mr-1" />
                        Hidden
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    {area.is_readonly ? (
                      <Badge variant="warning">
                        <Lock className="w-3 h-3 mr-1" />
                        Read-only
                      </Badge>
                    ) : (
                      <Badge variant="info">
                        <Unlock className="w-3 h-3 mr-1" />
                        Open
                      </Badge>
                    )}
                  </TableCell>
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
                        onClick={() => setViewArea(area)}
                        icon={<Eye className="w-4 h-4" />}
                      >
                        View Details
                      </DropdownItem>
                      <DropdownItem
                        onClick={() => openEditModal(area)}
                        icon={<Edit className="w-4 h-4" />}
                      >
                        Edit
                      </DropdownItem>
                      <DropdownDivider />
                      <DropdownItem
                        onClick={() => setDeleteArea(area)}
                        icon={<Trash2 className="w-4 h-4" />}
                        danger
                      >
                        Delete
                      </DropdownItem>
                    </Dropdown>
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <TableEmpty colSpan={6} message="No areas found" />
            )}
          </TableBody>
        </Table>
      </Card>

      {/* Create Modal */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={closeCreateModal}
        title="Create New Area"
        size="md"
      >
        <div className="space-y-4">
          <Input
            label="Area Name"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            placeholder="e.g., general, announcements"
            required
          />
          <Textarea
            label="Description"
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            placeholder="Optional description for this area"
          />
          <Switch
            label="Public"
            description="Visible to all users"
            checked={formData.is_public}
            onChange={(e) => setFormData({ ...formData, is_public: e.target.checked })}
          />
          <Switch
            label="Read-only"
            description="Users cannot post messages"
            checked={formData.is_readonly}
            onChange={(e) => setFormData({ ...formData, is_readonly: e.target.checked })}
          />
          <div className="flex justify-end gap-3 pt-4">
            <Button variant="ghost" onClick={closeCreateModal}>
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={handleCreate}
              loading={isSubmitting}
              disabled={!formData.name.trim()}
            >
              Create Area
            </Button>
          </div>
        </div>
      </Modal>

      {/* Edit Modal */}
      <Modal
        isOpen={!!editArea}
        onClose={closeEditModal}
        title={`Edit Area: ${editArea?.name}`}
        size="md"
      >
        <div className="space-y-4">
          <Input
            label="Area Name"
            value={formData.name}
            disabled
            hint="Area name cannot be changed"
          />
          <Textarea
            label="Description"
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            placeholder="Optional description for this area"
          />
          <Switch
            label="Public"
            description="Visible to all users"
            checked={formData.is_public}
            onChange={(e) => setFormData({ ...formData, is_public: e.target.checked })}
          />
          <Switch
            label="Read-only"
            description="Users cannot post messages"
            checked={formData.is_readonly}
            onChange={(e) => setFormData({ ...formData, is_readonly: e.target.checked })}
          />
          <div className="flex justify-end gap-3 pt-4">
            <Button variant="ghost" onClick={closeEditModal}>
              Cancel
            </Button>
            <Button variant="primary" onClick={handleUpdate} loading={isSubmitting}>
              Save Changes
            </Button>
          </div>
        </div>
      </Modal>

      {/* Delete Confirmation */}
      <ConfirmModal
        isOpen={!!deleteArea}
        onClose={() => setDeleteArea(null)}
        onConfirm={handleDelete}
        title="Delete Area"
        message={`Are you sure you want to delete "${deleteArea?.name}"? This will also delete all messages in this area. This action cannot be undone.`}
        confirmText="Delete"
        variant="danger"
        loading={isSubmitting}
      />

      {/* View Details Modal */}
      <Modal
        isOpen={!!viewArea}
        onClose={() => setViewArea(null)}
        title="Area Details"
        size="md"
      >
        {viewArea && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-gray-500">Name</p>
                <p className="font-medium text-gray-900 dark:text-white">
                  {viewArea.name}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Messages</p>
                <p className="font-medium text-gray-900 dark:text-white">
                  {viewArea.message_count || 0}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Visibility</p>
                {viewArea.is_public ? (
                  <Badge variant="success">Public</Badge>
                ) : (
                  <Badge variant="default">Hidden</Badge>
                )}
              </div>
              <div>
                <p className="text-sm text-gray-500">Status</p>
                {viewArea.is_readonly ? (
                  <Badge variant="warning">Read-only</Badge>
                ) : (
                  <Badge variant="info">Open</Badge>
                )}
              </div>
            </div>
            {viewArea.description && (
              <div>
                <p className="text-sm text-gray-500">Description</p>
                <p className="text-gray-700 dark:text-gray-300">{viewArea.description}</p>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}

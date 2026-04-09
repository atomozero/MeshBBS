import { useEffect, useState, useCallback } from 'react';
import {
  Save,
  RefreshCw,
  Download,
  Upload,
  Trash2,
  Server,
  Database,
  Clock,
  HardDrive,
} from 'lucide-react';
import {
  Card,
  CardHeader,
  CardContent,
  CardFooter,
  Input,
  Textarea,
  Switch,
  Button,
  LoadingPage,
  Alert,
  ConfirmModal,
} from '@/components/ui';
import { useToast } from '@/components/ui';
import { settingsApi, type UpdateSettingsRequest, type BackupInfo } from '@/api';
import type { BBSSettings, SystemInfo, RetentionStats } from '@/types';

export function SettingsPage() {
  const { success, error: showError } = useToast();

  const [, setSettings] = useState<BBSSettings | null>(null);
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null);
  const [retentionStats, setRetentionStats] = useState<RetentionStats | null>(null);
  const [backups, setBackups] = useState<BackupInfo[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [formData, setFormData] = useState<UpdateSettingsRequest>({});
  const [hasChanges, setHasChanges] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  // Modals
  const [cleanupConfirm, setCleanupConfirm] = useState(false);
  const [backupConfirm, setBackupConfirm] = useState(false);
  const [restoreBackup, setRestoreBackup] = useState<string | null>(null);
  const [deleteBackup, setDeleteBackup] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      setIsLoading(true);
      const [settingsData, systemData, retentionData, backupsData] = await Promise.all([
        settingsApi.get(),
        settingsApi.getSystemInfo(),
        settingsApi.getRetentionStats(),
        settingsApi.listBackups(),
      ]);
      setSettings(settingsData);
      setSystemInfo(systemData);
      setRetentionStats(retentionData);
      setBackups(backupsData.backups);
      setFormData({
        bbs_name: settingsData.bbs_name,
        welcome_message: settingsData.welcome_message,
        max_message_length: settingsData.max_message_length,
        session_timeout: settingsData.session_timeout,
        allow_registration: settingsData.allow_registration,
        require_approval: settingsData.require_approval,
        default_area: settingsData.default_area,
        retention_days: settingsData.retention_days,
        enable_logging: settingsData.enable_logging,
      });
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load settings');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleInputChange = (field: keyof UpdateSettingsRequest, value: unknown) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    setHasChanges(true);
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await settingsApi.update(formData);
      success('Settings saved successfully');
      setHasChanges(false);
      fetchData();
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Failed to save settings');
    } finally {
      setIsSaving(false);
    }
  };

  const handleCleanup = async () => {
    setIsSubmitting(true);
    try {
      const result = await settingsApi.triggerCleanup();
      success(`Cleanup completed. Deleted ${result.deleted} items.`);
      setCleanupConfirm(false);
      fetchData();
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Cleanup failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCreateBackup = async () => {
    setIsSubmitting(true);
    try {
      const result = await settingsApi.createBackup();
      success(`Backup created: ${result.filename}`);
      setBackupConfirm(false);
      fetchData();
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Backup failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRestoreBackup = async () => {
    if (!restoreBackup) return;

    setIsSubmitting(true);
    try {
      await settingsApi.restoreBackup(restoreBackup);
      success('Backup restored successfully. Reloading...');
      setRestoreBackup(null);
      setTimeout(() => window.location.reload(), 1500);
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Restore failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteBackup = async () => {
    if (!deleteBackup) return;

    setIsSubmitting(true);
    try {
      await settingsApi.deleteBackup(deleteBackup);
      success('Backup deleted');
      setDeleteBackup(null);
      fetchData();
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Delete failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDownloadBackup = async (filename: string) => {
    try {
      const blob = await settingsApi.downloadBackup(filename);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Download failed');
    }
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (dateStr?: string | null) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleString();
  };

  if (isLoading) {
    return <LoadingPage message="Loading settings..." />;
  }

  if (error) {
    return (
      <Alert variant="error" title="Error loading settings">
        {error}
      </Alert>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Settings</h1>
          <p className="text-gray-500 dark:text-gray-400">
            Configure your BBS system
          </p>
        </div>
        <Button
          variant="primary"
          icon={<Save className="w-4 h-4" />}
          onClick={handleSave}
          loading={isSaving}
          disabled={!hasChanges}
        >
          Save Changes
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main settings */}
        <div className="lg:col-span-2 space-y-6">
          {/* General settings */}
          <Card padding="none">
            <CardHeader title="General Settings" className="px-6 pt-4" />
            <CardContent className="px-6 pb-6 space-y-4">
              <Input
                label="BBS Name"
                value={formData.bbs_name || ''}
                onChange={(e) => handleInputChange('bbs_name', e.target.value)}
                placeholder="My MeshBBS"
              />
              <Textarea
                label="Welcome Message"
                value={formData.welcome_message || ''}
                onChange={(e) => handleInputChange('welcome_message', e.target.value)}
                placeholder="Welcome to the BBS!"
                hint="Shown to users when they connect"
              />
              <Input
                label="Default Area"
                value={formData.default_area || ''}
                onChange={(e) => handleInputChange('default_area', e.target.value)}
                placeholder="general"
              />
            </CardContent>
          </Card>

          {/* Message settings */}
          <Card padding="none">
            <CardHeader title="Message Settings" className="px-6 pt-4" />
            <CardContent className="px-6 pb-6 space-y-4">
              <Input
                label="Max Message Length"
                type="number"
                value={formData.max_message_length || 0}
                onChange={(e) =>
                  handleInputChange('max_message_length', parseInt(e.target.value))
                }
                min="100"
                max="10000"
              />
              <Input
                label="Retention Days"
                type="number"
                value={formData.retention_days || 0}
                onChange={(e) =>
                  handleInputChange('retention_days', parseInt(e.target.value))
                }
                min="1"
                hint="Messages older than this will be cleaned up"
              />
            </CardContent>
          </Card>

          {/* Access settings */}
          <Card padding="none">
            <CardHeader title="Access Settings" className="px-6 pt-4" />
            <CardContent className="px-6 pb-6 space-y-4">
              <Input
                label="Session Timeout (minutes)"
                type="number"
                value={formData.session_timeout || 0}
                onChange={(e) =>
                  handleInputChange('session_timeout', parseInt(e.target.value))
                }
                min="5"
              />
              <Switch
                label="Allow Registration"
                description="Allow new users to register"
                checked={formData.allow_registration || false}
                onChange={(e) =>
                  handleInputChange('allow_registration', e.target.checked)
                }
              />
              <Switch
                label="Require Approval"
                description="New users must be approved by admin"
                checked={formData.require_approval || false}
                onChange={(e) =>
                  handleInputChange('require_approval', e.target.checked)
                }
              />
              <Switch
                label="Enable Logging"
                description="Log all user activity"
                checked={formData.enable_logging || false}
                onChange={(e) => handleInputChange('enable_logging', e.target.checked)}
              />
            </CardContent>
          </Card>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* System info */}
          <Card padding="none">
            <CardHeader title="System Info" className="px-6 pt-4" />
            <CardContent className="px-6 pb-6 space-y-3">
              <div className="flex items-center gap-3">
                <Server className="w-5 h-5 text-gray-400" />
                <div className="flex-1">
                  <p className="text-xs text-gray-500">Version</p>
                  <p className="text-sm font-medium">{systemInfo?.version || 'N/A'}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Clock className="w-5 h-5 text-gray-400" />
                <div className="flex-1">
                  <p className="text-xs text-gray-500">Uptime</p>
                  <p className="text-sm font-medium">{systemInfo?.uptime || 'N/A'}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Database className="w-5 h-5 text-gray-400" />
                <div className="flex-1">
                  <p className="text-xs text-gray-500">Database Size</p>
                  <p className="text-sm font-medium">
                    {formatBytes(systemInfo?.database_size || 0)}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <HardDrive className="w-5 h-5 text-gray-400" />
                <div className="flex-1">
                  <p className="text-xs text-gray-500">Disk Usage</p>
                  <p className="text-sm font-medium">
                    {formatBytes(systemInfo?.disk_usage || 0)}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Retention stats */}
          {retentionStats && (
            <Card padding="none">
              <CardHeader title="Retention Stats" className="px-6 pt-4" />
              <CardContent className="px-6 pb-6 space-y-3">
                <div className="flex justify-between">
                  <span className="text-sm text-gray-500">Messages to clean</span>
                  <span className="text-sm font-medium">
                    {retentionStats.messages_to_clean || 0}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-gray-500">Logs to clean</span>
                  <span className="text-sm font-medium">
                    {retentionStats.logs_to_clean || 0}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-gray-500">Last cleanup</span>
                  <span className="text-sm font-medium">
                    {formatDate(retentionStats.last_cleanup)}
                  </span>
                </div>
              </CardContent>
              <CardFooter className="px-6 pb-4">
                <Button
                  variant="secondary"
                  size="sm"
                  icon={<RefreshCw className="w-4 h-4" />}
                  onClick={() => setCleanupConfirm(true)}
                  className="w-full"
                >
                  Run Cleanup
                </Button>
              </CardFooter>
            </Card>
          )}

          {/* Backups */}
          <Card padding="none">
            <CardHeader
              title="Backups"
              action={
                <Button
                  variant="secondary"
                  size="sm"
                  icon={<Download className="w-4 h-4" />}
                  onClick={() => setBackupConfirm(true)}
                >
                  Create
                </Button>
              }
              className="px-6 pt-4"
            />
            <CardContent className="px-6 pb-6">
              {backups.length > 0 ? (
                <div className="space-y-2">
                  {backups.map((backup) => (
                    <div
                      key={backup.filename}
                      className="flex items-center justify-between p-2 bg-gray-50 dark:bg-gray-800 rounded"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium truncate">{backup.filename}</p>
                        <p className="text-xs text-gray-500">
                          {formatBytes(backup.size)} · {formatDate(backup.created_at)}
                        </p>
                      </div>
                      <div className="flex gap-1 ml-2">
                        <button
                          onClick={() => handleDownloadBackup(backup.filename)}
                          className="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded text-gray-500"
                          title="Download"
                        >
                          <Download className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => setRestoreBackup(backup.filename)}
                          className="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded text-gray-500"
                          title="Restore"
                        >
                          <Upload className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => setDeleteBackup(backup.filename)}
                          className="p-1 hover:bg-red-100 dark:hover:bg-red-900/30 rounded text-red-500"
                          title="Delete"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-500 text-center py-4">No backups available</p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Cleanup Confirmation */}
      <ConfirmModal
        isOpen={cleanupConfirm}
        onClose={() => setCleanupConfirm(false)}
        onConfirm={handleCleanup}
        title="Run Cleanup"
        message="This will delete old messages and logs based on retention settings. Continue?"
        confirmText="Run Cleanup"
        variant="warning"
        loading={isSubmitting}
      />

      {/* Backup Confirmation */}
      <ConfirmModal
        isOpen={backupConfirm}
        onClose={() => setBackupConfirm(false)}
        onConfirm={handleCreateBackup}
        title="Create Backup"
        message="This will create a backup of the current database. Continue?"
        confirmText="Create Backup"
        variant="primary"
        loading={isSubmitting}
      />

      {/* Restore Confirmation */}
      <ConfirmModal
        isOpen={!!restoreBackup}
        onClose={() => setRestoreBackup(null)}
        onConfirm={handleRestoreBackup}
        title="Restore Backup"
        message={`Are you sure you want to restore from "${restoreBackup}"? This will replace all current data.`}
        confirmText="Restore"
        variant="danger"
        loading={isSubmitting}
      />

      {/* Delete Backup Confirmation */}
      <ConfirmModal
        isOpen={!!deleteBackup}
        onClose={() => setDeleteBackup(null)}
        onConfirm={handleDeleteBackup}
        title="Delete Backup"
        message={`Are you sure you want to delete "${deleteBackup}"? This cannot be undone.`}
        confirmText="Delete"
        variant="danger"
        loading={isSubmitting}
      />
    </div>
  );
}

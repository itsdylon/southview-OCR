import { useState, useEffect } from 'react';
import { FileDown, Download, Database, CheckCircle, Loader2, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';
import { DashboardLayout } from '../layouts/dashboard-layout';
import * as api from '../data/api';

function formatBytes(bytes: number): string {
  if (bytes >= 1_000_000_000) return `${(bytes / 1_000_000_000).toFixed(1)} GB`;
  if (bytes >= 1_000_000) return `${(bytes / 1_000_000).toFixed(1)} MB`;
  if (bytes >= 1_000) return `${(bytes / 1_000).toFixed(1)} KB`;
  return `${bytes} B`;
}

interface BackupEntry {
  filename: string;
  created_at: string;
  size_bytes: number;
}

export default function ExportBackupPage() {
  const [exportFormat, setExportFormat] = useState<'csv' | 'json'>('csv');
  const [statusFilter, setStatusFilter] = useState('all');
  const [exporting, setExporting] = useState(false);
  const [backingUp, setBackingUp] = useState(false);
  const [backups, setBackups] = useState<BackupEntry[]>([]);
  const [backupsLoading, setBackupsLoading] = useState(true);

  // Fetch backups on mount
  useEffect(() => {
    api.fetchBackups()
      .then((data) => {
        setBackups(Array.isArray(data) ? data : []);
      })
      .catch(() => {
        // Backups endpoint may not exist yet; ignore
        setBackups([]);
      })
      .finally(() => setBackupsLoading(false));
  }, []);

  const handleExport = async () => {
    setExporting(true);
    try {
      const mappedStatus = statusFilter === 'approved-corrected' ? undefined : statusFilter === 'all' ? undefined : statusFilter;
      const blob = await api.downloadExport(exportFormat, undefined, mappedStatus);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `southview_export_${new Date().toISOString().slice(0, 10)}.${exportFormat}`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success(`Export downloaded as ${exportFormat.toUpperCase()}`);
    } catch (e: any) {
      toast.error(e.message ?? 'Export failed');
    } finally {
      setExporting(false);
    }
  };

  const handleBackup = async () => {
    setBackingUp(true);
    try {
      await api.triggerBackup();
      toast.success('Backup created successfully');
      // Refresh backup list
      const data = await api.fetchBackups();
      setBackups(Array.isArray(data) ? data : []);
    } catch (e: any) {
      toast.error(e.message ?? 'Backup failed');
    } finally {
      setBackingUp(false);
    }
  };

  return (
    <DashboardLayout>
      <div className="p-8 max-w-5xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Export & Backup</h1>
          <p className="text-gray-600">
            Export approved records and manage database backups
          </p>
        </div>

        {/* Export Section */}
        <div className="mb-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Export Records</h2>
          <div className="bg-white rounded-xl border border-gray-200 p-8">
            <div className="flex items-start gap-8">
              <div className="w-16 h-16 bg-indigo-50 rounded-xl flex items-center justify-center flex-shrink-0">
                <FileDown className="w-8 h-8 text-indigo-600" />
              </div>

              <div className="flex-1 space-y-6">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 mb-1">Export Database</h3>
                  <p className="text-sm text-gray-600">
                    Download processed and approved records for external use
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Review Status
                  </label>
                  <select
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                    className="w-full max-w-xs px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  >
                    <option value="all">All Statuses</option>
                    <option value="approved">Approved Only</option>
                    <option value="approved-flagged">Approved and Flagged</option>
                    <option value="flagged">Flagged Only</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-3">
                    Export Format
                  </label>
                  <div className="flex gap-3">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="radio"
                        value="csv"
                        checked={exportFormat === 'csv'}
                        onChange={(e) => setExportFormat(e.target.value as 'csv')}
                        className="w-4 h-4 text-indigo-600"
                      />
                      <span className="text-sm text-gray-700">CSV (Spreadsheet)</span>
                    </label>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="radio"
                        value="json"
                        checked={exportFormat === 'json'}
                        onChange={(e) => setExportFormat(e.target.value as 'json')}
                        className="w-4 h-4 text-indigo-600"
                      />
                      <span className="text-sm text-gray-700">JSON (API/Database)</span>
                    </label>
                  </div>
                </div>

                <button
                  onClick={handleExport}
                  disabled={exporting}
                  className="flex items-center gap-2 px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-semibold disabled:opacity-50"
                >
                  {exporting ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <Download className="w-5 h-5" />
                  )}
                  {exporting ? 'Exporting...' : 'Download Export'}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Backup Section */}
        <div className="mb-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Database Backup</h2>
          <div className="bg-white rounded-xl border border-gray-200 p-8">
            <div className="flex items-start gap-8">
              <div className="w-16 h-16 bg-green-50 rounded-xl flex items-center justify-center flex-shrink-0">
                <Database className="w-8 h-8 text-green-600" />
              </div>

              <div className="flex-1">
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Manual Backup</h3>
                <p className="text-sm text-gray-600 mb-6">
                  Create a full backup of the SQLite database including all videos, cards, and OCR results
                </p>

                <button
                  onClick={handleBackup}
                  disabled={backingUp}
                  className="flex items-center gap-2 px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-semibold disabled:opacity-50"
                >
                  {backingUp ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <Database className="w-5 h-5" />
                  )}
                  {backingUp ? 'Creating Backup...' : 'Trigger Backup Now'}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Recent Backups */}
        <div>
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Recent Backups</h2>
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200">
                  <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Timestamp</th>
                  <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Filename</th>
                  <th className="text-right px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Size</th>
                  <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Status</th>
                </tr>
              </thead>
              <tbody>
                {backupsLoading ? (
                  <tr>
                    <td colSpan={4} className="px-6 py-8 text-center text-sm text-gray-500">
                      <Loader2 className="w-5 h-5 animate-spin mx-auto mb-2" />
                      Loading backups...
                    </td>
                  </tr>
                ) : backups.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-6 py-8 text-center text-sm text-gray-500">
                      <AlertCircle className="w-5 h-5 mx-auto mb-2 text-gray-400" />
                      No backups found. Trigger one above.
                    </td>
                  </tr>
                ) : (
                  backups.map((b, i) => (
                    <tr key={i} className="border-b border-gray-100 hover:bg-gray-50">
                      <td className="px-6 py-4 text-sm text-gray-600">
                        {b.created_at ? new Date(b.created_at).toLocaleString() : 'Unknown'}
                      </td>
                      <td className="px-6 py-4">
                        <span className="text-sm text-gray-900">{b.filename}</span>
                      </td>
                      <td className="px-6 py-4 text-right text-sm text-gray-900 font-medium">
                        {formatBytes(b.size_bytes)}
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          <CheckCircle className="w-4 h-4 text-green-600" />
                          <span className="text-sm text-green-600">Success</span>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

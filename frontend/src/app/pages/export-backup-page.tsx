import { useState } from 'react';
import { FileDown, Download, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { DashboardLayout } from '../layouts/dashboard-layout';
import * as api from '../data/api';

export default function ExportBackupPage() {
  const [exportFormat, setExportFormat] = useState<'csv' | 'json'>('csv');
  const [statusFilter, setStatusFilter] = useState('all');
  const [exporting, setExporting] = useState(false);

  const handleExport = async () => {
    setExporting(true);
    try {
      const mappedStatus =
        statusFilter === 'approved-corrected'
          ? 'approved,corrected'
          : statusFilter === 'all'
            ? undefined
            : statusFilter;
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

  return (
    <DashboardLayout>
      <div className="p-8 max-w-5xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Export</h1>
          <p className="text-gray-600">
            Export reviewed burial card records
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
                    Download processed records with the current slim field set and full OCR text
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
                    <option value="approved-corrected">Approved and Corrected</option>
                    <option value="approved">Approved Only</option>
                    <option value="corrected">Corrected Only</option>
                    <option value="flagged">Flagged Only</option>
                    <option value="pending">Pending Only</option>
                    <option value="all">All Statuses</option>
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

      </div>
    </DashboardLayout>
  );
}

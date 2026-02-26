import { useState } from 'react';
import { FileDown, Download, Database, CheckCircle } from 'lucide-react';
import { toast } from 'sonner';
import { DashboardLayout } from '../layouts/dashboard-layout';
import { useCardStore } from '../data/mock-db';
import type { CardWithOCR } from '../types/ocr';

function generateExportData(allCards: CardWithOCR[], statusFilter: string) {
  let cards = allCards.filter((c) => c.ocrResult);
  if (statusFilter === 'approved') {
    cards = cards.filter((c) => c.ocrResult?.reviewStatus === 'approved');
  } else if (statusFilter === 'corrected') {
    cards = cards.filter((c) => c.ocrResult?.reviewStatus === 'corrected');
  } else if (statusFilter === 'approved-corrected') {
    cards = cards.filter(
      (c) => c.ocrResult?.reviewStatus === 'approved' || c.ocrResult?.reviewStatus === 'corrected'
    );
  }
  return cards;
}

function downloadCSV(cards: CardWithOCR[]) {
  const headers = [
    'Deceased Name','Address','Owner','Relation','Phone',
    'Date of Death','Date of Burial','Description','Sex','Age',
    'Grave Type','Grave Fee','Undertaker','Board of Health No','SVC No',
    'Confidence','Review Status',
  ];
  const rows = cards.map((c) => {
    const r = c.ocrResult!;
    return [
      r.deceased_name, r.address, r.owner, r.relation, r.phone,
      r.date_of_death, r.date_of_burial, r.description, r.sex, r.age,
      r.grave_type, r.grave_fee, r.undertaker, r.board_of_health_no, r.svc_no,
      r.confidenceScore, r.reviewStatus,
    ].map((v) => `"${(v ?? '').toString().replace(/"/g, '""')}"`).join(',');
  });
  const csv = [headers.join(','), ...rows].join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `southview_export_${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

function downloadJSON(cards: CardWithOCR[]) {
  const data = cards.map((c) => ({ ...c.ocrResult, cardId: c.id, frameNumber: c.frameNumber }));
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `southview_export_${new Date().toISOString().slice(0, 10)}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function ExportBackupPage() {
  const { cards } = useCardStore();
  const [exportFormat, setExportFormat] = useState<'csv' | 'json'>('csv');
  const [statusFilter, setStatusFilter] = useState('all');

  const handleExport = () => {
    const filtered = generateExportData(cards, statusFilter);
    if (filtered.length === 0) {
      toast.error('No records match the selected filters');
      return;
    }
    if (exportFormat === 'csv') {
      downloadCSV(filtered);
    } else {
      downloadJSON(filtered);
    }
    toast.success(`Exported ${filtered.length} records as ${exportFormat.toUpperCase()}`);
  };

  const handleBackup = () => {
    toast.success('Backup triggered', {
      description: 'Database will be backed up to configured location.',
    });
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
                    <option value="corrected">Corrected Only</option>
                    <option value="approved-corrected">Approved + Corrected</option>
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
                  className="flex items-center gap-2 px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-semibold"
                >
                  <Download className="w-5 h-5" />
                  Download Export
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
                  className="flex items-center gap-2 px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-semibold"
                >
                  <Database className="w-5 h-5" />
                  Trigger Backup Now
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
                  <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Type</th>
                  <th className="text-right px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Size</th>
                  <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Status</th>
                  <th className="text-right px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Action</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="px-6 py-4 text-sm text-gray-600">
                    2025-02-20 16:45:00
                  </td>
                  <td className="px-6 py-4">
                    <span className="text-sm text-gray-900">Full Database</span>
                  </td>
                  <td className="px-6 py-4 text-right text-sm text-gray-900 font-medium">
                    124 MB
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <CheckCircle className="w-4 h-4 text-green-600" />
                      <span className="text-sm text-green-600">Success</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <a
                      href="#"
                      className="text-indigo-600 hover:text-indigo-800 text-sm font-medium"
                    >
                      Download
                    </a>
                  </td>
                </tr>
                <tr className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="px-6 py-4 text-sm text-gray-600">
                    2025-02-19 10:30:00
                  </td>
                  <td className="px-6 py-4">
                    <span className="text-sm text-gray-900">Full Database</span>
                  </td>
                  <td className="px-6 py-4 text-right text-sm text-gray-900 font-medium">
                    118 MB
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <CheckCircle className="w-4 h-4 text-green-600" />
                      <span className="text-sm text-green-600">Success</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <a
                      href="#"
                      className="text-indigo-600 hover:text-indigo-800 text-sm font-medium"
                    >
                      Download
                    </a>
                  </td>
                </tr>
                <tr className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="px-6 py-4 text-sm text-gray-600">
                    2025-02-18 14:15:00
                  </td>
                  <td className="px-6 py-4">
                    <span className="text-sm text-gray-900">Full Database</span>
                  </td>
                  <td className="px-6 py-4 text-right text-sm text-gray-900 font-medium">
                    115 MB
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <CheckCircle className="w-4 h-4 text-green-600" />
                      <span className="text-sm text-green-600">Success</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <a
                      href="#"
                      className="text-indigo-600 hover:text-indigo-800 text-sm font-medium"
                    >
                      Download
                    </a>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

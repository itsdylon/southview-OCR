import { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router';
import { Filter, ArrowRight, AlertTriangle, ChevronLeft, ChevronRight } from 'lucide-react';
import { DashboardLayout } from '../layouts/dashboard-layout';
import { ConfidenceBadge } from '../components/confidence-badge';
import { StatusChip } from '../components/status-chip';
import * as api from '../data/api';
import { useMockDb } from '../data/mock-db';
import { getConfidenceBand, type CardWithOCR } from '../types/ocr';
import type { ReviewStatus } from '../types/ocr';

type StatusFilterValue = ReviewStatus | 'all' | 'needs-review';

const STATUS_FILTER_OPTIONS: { value: StatusFilterValue; label: string }[] = [
  { value: 'needs-review', label: 'Needs Review' },
  { value: 'all', label: 'All Statuses' },
  { value: 'flagged', label: 'Flagged' },
  { value: 'pending', label: 'Pending Review' },
  { value: 'approved', label: 'Approved' },
];

function isValidStatusFilter(value: string): value is StatusFilterValue {
  return STATUS_FILTER_OPTIONS.some((o) => o.value === value);
}

export default function OCRReviewQueuePage() {
  const { mergeCards } = useMockDb();
  const [searchParams] = useSearchParams();
  const [showFilters, setShowFilters] = useState(false);
  const [confidenceBand, setConfidenceBand] = useState<string>('all');
  const [cards, setCards] = useState<CardWithOCR[]>([]);
  const [totalCards, setTotalCards] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<Record<string, number>>({});
  const perPage = 50;

  // Derive initial status filter from URL ?filter= param, defaulting to needs-review
  const filterParam = searchParams.get('filter');
  const initialFilter: StatusFilterValue =
    filterParam && isValidStatusFilter(filterParam) ? filterParam : 'needs-review';
  const [statusFilter, setStatusFilter] = useState<StatusFilterValue>(initialFilter);

  // Sync when the URL param changes (e.g. navigating from overview links)
  useEffect(() => {
    if (filterParam && isValidStatusFilter(filterParam)) {
      setStatusFilter(filterParam);
    }
  }, [filterParam]);

  useEffect(() => {
    setPage(1);
  }, [statusFilter, confidenceBand]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const params: Parameters<typeof api.fetchCards>[0] = { page, perPage };
        if (statusFilter === 'needs-review') {
          params.statusIn = 'flagged,pending';
        } else if (statusFilter !== 'all') {
          params.status = statusFilter;
        }

        if (confidenceBand === 'flagged') {
          params.maxConfidence = 0.699999;
        } else if (confidenceBand === 'pending-review') {
          params.minConfidence = 0.7;
          params.maxConfidence = 0.849999;
        } else if (confidenceBand === 'auto-approved') {
          params.minConfidence = 0.85;
        }

        const [result, counts] = await Promise.all([
          api.fetchCards(params),
          api.fetchStats(),
        ]);

        if (cancelled) return;
        setCards(result.cards);
        setTotalCards(result.total);
        setPage(result.page);
        setPages(result.pages);
        setStats(counts);
        mergeCards(result.cards);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Failed to load cards.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [confidenceBand, mergeCards, page, statusFilter]);
  const filteredCards = cards;
  const flaggedCount = stats.flagged ?? 0;
  const pendingCount = stats.pending ?? 0;
  const autoApprovedCount = stats.auto_approved ?? 0;

  return (
    <DashboardLayout>
      <div className="p-8 max-w-7xl mx-auto">
        {/* Next Best Action Banner */}
        {flaggedCount > 0 && (
          <div className="bg-red-600 text-white rounded-xl p-6 mb-8 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <AlertTriangle className="w-6 h-6" />
              <div>
                <h2 className="text-xl font-semibold mb-1">
                  {flaggedCount} flagged cards need immediate review
                </h2>
                <p className="text-white/90">
                  Low confidence scores (&lt;70%) — Start with the most problematic records
                </p>
              </div>
            </div>
            {filteredCards.length > 0 && (
              <Link
                to={`/review/${filteredCards[0].id}`}
                className="flex items-center gap-2 bg-white/20 backdrop-blur px-6 py-3 rounded-lg font-semibold hover:bg-white/30 transition-colors"
              >
                Start Review
                <ArrowRight className="w-5 h-5" />
              </Link>
            )}
          </div>
        )}

        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 mb-2">Review Queue</h1>
            <p className="text-gray-600">
              {loading ? 'Loading cards…' : `${totalCards} cards`} • Sorted by priority (flagged first)
            </p>
          </div>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
          >
            <Filter className="w-5 h-5" />
            Filters
          </button>
        </div>

        {/* Filters */}
        {showFilters && (
          <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Review Status
                </label>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value as StatusFilterValue)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  {STATUS_FILTER_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Confidence Band
                </label>
                <select
                  value={confidenceBand}
                  onChange={(e) => setConfidenceBand(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="all">All Confidence Levels</option>
                  <option value="flagged">Flagged (&lt;70%)</option>
                  <option value="pending-review">Pending (70-84%)</option>
                  <option value="auto-approved">Auto-approved (≥85%)</option>
                </select>
              </div>
            </div>
          </div>
        )}

        {/* Quick Stats */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="bg-white rounded-lg border border-gray-200 p-4 flex items-center gap-4">
            <div className="w-10 h-10 bg-red-50 rounded-lg flex items-center justify-center">
              <AlertTriangle className="w-5 h-5 text-red-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{flaggedCount}</p>
              <p className="text-sm text-gray-600">Flagged (&lt;70%)</p>
            </div>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 p-4 flex items-center gap-4">
            <div className="w-10 h-10 bg-yellow-50 rounded-lg flex items-center justify-center">
              <AlertTriangle className="w-5 h-5 text-yellow-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{pendingCount}</p>
              <p className="text-sm text-gray-600">Pending (70-84%)</p>
            </div>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 p-4 flex items-center gap-4">
            <div className="w-10 h-10 bg-green-50 rounded-lg flex items-center justify-center">
              <AlertTriangle className="w-5 h-5 text-green-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">
                {autoApprovedCount}
              </p>
              <p className="text-sm text-gray-600">Auto-approved (≥85%)</p>
            </div>
          </div>
        </div>

        {/* Cards Table */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          {error && (
            <div className="border-b border-red-100 bg-red-50 px-6 py-4 text-sm text-red-700">
              {error}
            </div>
          )}
          <table className="w-full">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Deceased Name</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Date of Burial</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Description</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Confidence</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Status</th>
                <th className="text-right px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Action</th>
              </tr>
            </thead>
            <tbody>
              {!loading && filteredCards.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-6 py-10 text-center text-sm text-gray-500">
                    No cards match the current filters.
                  </td>
                </tr>
              )}
              {filteredCards.map((card) => (
                <tr key={card.id} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="px-6 py-4">
                    <p className="font-medium text-gray-900">
                      {card.ocrResult?.deceased_name || (
                        <span className="text-gray-400 italic">Unknown</span>
                      )}
                    </p>
                    {card.ocrResult?.sex && card.ocrResult?.age && (
                      <p className="text-sm text-gray-500">
                        {card.ocrResult.sex}, Age {card.ocrResult.age}
                      </p>
                    )}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">
                    {card.ocrResult?.date_of_burial || '—'}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">
                    {card.ocrResult?.description || '—'}
                  </td>
                  <td className="px-6 py-4">
                    {card.ocrResult && (
                      <ConfidenceBadge
                        score={card.ocrResult.confidenceScore}
                        band={getConfidenceBand(card.ocrResult.confidenceScore)}
                      />
                    )}
                  </td>
                  <td className="px-6 py-4">
                    {card.ocrResult && (
                      <StatusChip status={card.ocrResult.reviewStatus} />
                    )}
                  </td>
                  <td className="px-6 py-4 text-right">
                    <Link
                      to={`/review/${card.id}`}
                      className="text-indigo-600 hover:text-indigo-800 text-sm font-medium"
                    >
                      Review →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex items-center justify-between border-t border-gray-200 bg-gray-50 px-6 py-4">
            <p className="text-sm text-gray-600">
              Page {pages === 0 ? 0 : page} of {pages}
            </p>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((current) => Math.max(1, current - 1))}
                disabled={page <= 1 || loading}
                className="inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <ChevronLeft className="w-4 h-4" />
                Previous
              </button>
              <button
                onClick={() => setPage((current) => Math.min(pages, current + 1))}
                disabled={page >= pages || loading}
                className="inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Next
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

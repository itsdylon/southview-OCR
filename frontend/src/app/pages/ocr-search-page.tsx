import { useDeferredValue, useEffect, useState } from 'react';
import { Search as SearchIcon, ChevronDown, ChevronUp, X, ChevronLeft, ChevronRight } from 'lucide-react';
import { DashboardLayout } from '../layouts/dashboard-layout';
import { ConfidenceBadge } from '../components/confidence-badge';
import { StatusChip } from '../components/status-chip';
import * as api from '../data/api';
import { useMockDb } from '../data/mock-db';
import { getConfidenceBand } from '../types/ocr';
import type { CardWithOCR } from '../types/ocr';

export default function OCRSearchPage() {
  const { mergeCards } = useMockDb();
  const [searchQuery, setSearchQuery] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [selectedCard, setSelectedCard] = useState<CardWithOCR | null>(null);
  const [cards, setCards] = useState<CardWithOCR[]>([]);
  const [totalCards, setTotalCards] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const deferredSearchQuery = useDeferredValue(searchQuery.trim());
  const perPage = 50;

  useEffect(() => {
    setPage(1);
  }, [deferredSearchQuery]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const result = await api.fetchCards({
          q: deferredSearchQuery || undefined,
          page,
          perPage,
          sort: 'sequence_index',
        });
        if (cancelled) return;
        setCards(result.cards);
        setTotalCards(result.total);
        setPage(result.page);
        setPages(result.pages);
        mergeCards(result.cards);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Failed to load search results.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [deferredSearchQuery, mergeCards, page]);

  useEffect(() => {
    if (selectedCard && !cards.some((card) => card.id === selectedCard.id)) {
      setSelectedCard(cards[0] ?? null);
    }
    if (!selectedCard && cards.length > 0) {
      setSelectedCard(cards[0]);
    }
  }, [cards, selectedCard]);

  const filteredCards = cards;

  const getPreviewTransform = (rotationDegrees?: number) => {
    const rotation = rotationDegrees || 0;
    const isSideways = rotation % 180 !== 0;
    return `rotate(${rotation}deg) scale(${isSideways ? 1.45 : 1})`;
  };
  
  return (
    <DashboardLayout>
      <div className="p-8 max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Search Database</h1>
          <p className="text-gray-600">
            Search processed and approved burial records
          </p>
        </div>
        
        {/* Search Input */}
        <div className="mb-6">
          <div className="relative">
            <SearchIcon className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by deceased name..."
              className="w-full pl-12 pr-4 py-4 text-lg border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        </div>
        
        {/* Advanced Filters */}
        <div className="mb-6">
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center gap-2 text-gray-700 hover:text-gray-900 font-medium"
          >
            Advanced Filters
            {showAdvanced ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
          </button>
          {showAdvanced && (
            <div className="mt-4 bg-white rounded-xl border border-gray-200 p-6">
              <div className="grid grid-cols-4 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Date Range
                  </label>
                  <input
                    type="text"
                    placeholder="e.g., 1945-1970"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Sex
                  </label>
                  <select className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500">
                    <option value="">All</option>
                    <option value="M">Male</option>
                    <option value="F">Female</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Undertaker
                  </label>
                  <input
                    type="text"
                    placeholder="Enter name"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Location Keywords
                  </label>
                  <input
                    type="text"
                    placeholder="e.g., Section A"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              </div>
            </div>
          )}
        </div>
        
        {/* Results */}
        <div className="flex gap-6">
          {/* Results List */}
          <div className="flex-1">
            <p className="text-sm text-gray-600 mb-4">
              {loading ? 'Searching…' : `${totalCards} results found`}
            </p>
            {error && (
              <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            )}
            <div className="space-y-3">
              {!loading && filteredCards.length === 0 && (
                <div className="rounded-lg border border-gray-200 bg-white px-4 py-10 text-center text-sm text-gray-500">
                  No records match your search.
                </div>
              )}
              {filteredCards.map((card) => (
                <button
                  key={card.id}
                  onClick={() => setSelectedCard(card)}
                  className={`w-full text-left bg-white border rounded-lg p-4 hover:border-indigo-300 transition-colors ${
                    selectedCard?.id === card.id ? 'border-indigo-500 ring-2 ring-indigo-100' : 'border-gray-200'
                  }`}
                >
                  <div className="flex items-start justify-between mb-2">
                    <h3 className="font-semibold text-gray-900">
                      {card.ocrResult?.deceased_name || 'Unknown'}
                    </h3>
                    {card.ocrResult && (
                      <ConfidenceBadge
                        score={card.ocrResult.confidenceScore}
                        band={getConfidenceBand(card.ocrResult.confidenceScore)}
                        size="sm"
                      />
                    )}
                  </div>
                  <div className="text-sm text-gray-600 space-y-0.5">
                    {card.ocrResult?.date_of_burial && (
                      <p>Burial: {card.ocrResult.date_of_burial}</p>
                    )}
                    {card.ocrResult?.description && (
                      <p>Location: {card.ocrResult.description}</p>
                    )}
                    <div className="flex items-center gap-2 mt-2">
                      {card.ocrResult && <StatusChip status={card.ocrResult.reviewStatus} />}
                      <span className="text-xs text-gray-500">Frame #{card.frameNumber}</span>
                    </div>
                  </div>
                </button>
              ))}
            </div>
            <div className="mt-6 flex items-center justify-between">
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
          
          {/* Detail Panel */}
          {selectedCard && selectedCard.ocrResult && (
            <div className="w-[460px] bg-white border border-gray-200 rounded-xl p-6 sticky top-8 h-fit">
              <div className="flex items-start justify-between mb-6">
                <h2 className="text-xl font-bold text-gray-900">
                  {selectedCard.ocrResult.deceased_name || 'Unknown'}
                </h2>
                <button
                  onClick={() => setSelectedCard(null)}
                  className="p-1 hover:bg-gray-100 rounded"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
              
              {/* Image */}
              <div className="mb-6">
                <div className="h-[380px] bg-gray-50 border border-gray-200 rounded-lg p-4 flex items-center justify-center overflow-hidden">
                  <img
                    src={selectedCard.imagePath}
                    alt="Card scan"
                    style={{
                      transform: getPreviewTransform(selectedCard.ocrResult.rotationDegrees),
                      transformOrigin: 'center center',
                    }}
                    className="max-w-full max-h-full w-auto h-auto object-contain rounded-lg"
                  />
                </div>
              </div>
              
              {/* Details */}
              <div className="space-y-4 text-sm">
                <div className="flex items-center justify-between border-b border-gray-100 pb-2">
                  <span className="text-gray-600">Confidence:</span>
                  <ConfidenceBadge
                    score={selectedCard.ocrResult.confidenceScore}
                    band={getConfidenceBand(selectedCard.ocrResult.confidenceScore)}
                  />
                </div>
                <DetailRow label="Sex" value={selectedCard.ocrResult.sex} />
                <DetailRow label="Age" value={selectedCard.ocrResult.age} />
                <DetailRow label="Date of Death" value={selectedCard.ocrResult.date_of_death} />
                <DetailRow label="Date of Burial" value={selectedCard.ocrResult.date_of_burial} />
                <DetailRow label="Description" value={selectedCard.ocrResult.description} />
                <DetailRow label="Undertaker" value={selectedCard.ocrResult.undertaker} />
                <DetailRow label="SVC No." value={selectedCard.ocrResult.svc_no} />
                <div className="border-b border-gray-100 pb-2">
                  <span className="block text-gray-600 mb-2">Full Text:</span>
                  <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 text-xs font-mono text-gray-700 whitespace-pre-wrap max-h-44 overflow-y-auto">
                    {selectedCard.ocrResult.rawText || 'No OCR text available'}
                  </div>
                </div>
              </div>
              
              <div className="mt-6">
                <a
                  href={`/review/${selectedCard.id}`}
                  className="block w-full text-center px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium"
                >
                  View Full Record
                </a>
              </div>
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}

function DetailRow({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="flex justify-between border-b border-gray-100 pb-2">
      <span className="text-gray-600">{label}:</span>
      <span className="text-gray-900 font-medium text-right">{value || '—'}</span>
    </div>
  );
}

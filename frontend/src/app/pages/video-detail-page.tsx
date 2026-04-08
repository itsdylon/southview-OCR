import { useParams, Link, useNavigate } from 'react-router';
import { toast } from 'sonner';
import { ArrowLeft, Play, Eye } from 'lucide-react';
import { DashboardLayout } from '../layouts/dashboard-layout';
import { StatusChip } from '../components/status-chip';
import { ConfidenceBadge } from '../components/confidence-badge';
import { useMockDb } from '../data/mock-db';
import { getConfidenceBand } from '../types/ocr';

export default function VideoDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { getVideoById, getJobsByVideoId, getCardsByVideoId, deleteVideo, deleteCard } = useMockDb();
  const video = getVideoById(id!);

  if (!video) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-full">
          <p className="text-gray-500">Video not found</p>
        </div>
      </DashboardLayout>
    );
  }

  const videoJobs = getJobsByVideoId(video.id);
  const videoCards = getCardsByVideoId(video.id);

  const handleStartPipeline = () => {
    toast.success('Pipeline started', { description: `Processing ${video.filename}` });
  };

  const handleDeleteVideo = async () => {
    if (!window.confirm(`Delete video "${video.filename}" and all extracted records?`)) {
      return;
    }

    try {
      await deleteVideo(video.id);
      toast.success('Video deleted', { description: video.filename });
      navigate('/videos');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to delete video';
      toast.error('Delete failed', { description: message });
    }
  };

  const handleDeleteCard = async (cardId: string, label: string) => {
    if (!window.confirm(`Delete record "${label}"?`)) {
      return;
    }

    try {
      await deleteCard(cardId);
      toast.success('Record deleted', { description: label });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to delete record';
      toast.error('Delete failed', { description: message });
    }
  };

  return (
    <DashboardLayout>
      <div className="p-8 max-w-7xl mx-auto">
        <div className="mb-8">
          <Link
            to="/videos"
            className="inline-flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-4"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Videos
          </Link>
          <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
            <div className="min-w-0">
              <h1 className="text-3xl font-bold text-gray-900 mb-2">{video.filename}</h1>
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-gray-600">
                <span>Duration: {video.duration}</span>
                <span className="text-gray-300">•</span>
                <span>Size: {video.fileSize}</span>
                <span className="text-gray-300">•</span>
                <span>Frames: {video.frameCount || 0}</span>
                <span className="text-gray-300">•</span>
                <span>Cards: {video.cardCount}</span>
              </div>
            </div>
            <div className="flex w-full flex-col gap-3 sm:w-auto sm:min-w-[320px] sm:items-end">
              <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-gray-200 bg-white px-4 py-3 shadow-sm sm:justify-end">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold uppercase tracking-[0.12em] text-gray-500">
                    Status
                  </span>
                  <StatusChip status={video.status} size="md" />
                </div>
                <button
                  onClick={() => void handleDeleteVideo()}
                  className="inline-flex h-11 items-center justify-center rounded-xl border border-red-200 px-4 text-sm font-semibold text-red-700 transition-colors hover:bg-red-50"
                >
                  Delete Video
                </button>
              </div>
              {video.status === 'uploaded' && (
                <button
                  onClick={handleStartPipeline}
                  className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-indigo-600 px-6 text-sm font-semibold text-white transition-colors hover:bg-indigo-700 sm:min-w-[260px]"
                >
                  <Play className="w-5 h-5" />
                  Start Full Pipeline
                </button>
              )}
              {video.status !== 'uploaded' && (
                <div className="text-sm text-gray-500 sm:text-right">
                  Pipeline actions will appear here when the video is ready to run again.
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="mb-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Processing Jobs</h2>
          {videoJobs.length > 0 ? (
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200">
                    <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Job Type</th>
                    <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Status</th>
                    <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Progress</th>
                    <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Created</th>
                    <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Completed</th>
                    <th className="text-right px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {videoJobs.map((job) => (
                    <tr key={job.id} className="border-b border-gray-100 hover:bg-gray-50">
                      <td className="px-6 py-4">
                        <span className="font-medium text-gray-900 capitalize">
                          {job.jobType.replace('_', ' ')}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <StatusChip status={job.status} />
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden max-w-[120px]">
                            <div
                              className="h-full bg-indigo-600 rounded-full transition-all"
                              style={{ width: `${job.progress}%` }}
                            />
                          </div>
                          <span className="text-sm font-medium text-gray-700 w-10 text-right">
                            {job.progress}%
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-600">
                        {new Date(job.createdAt).toLocaleString('en-US', {
                          month: 'short',
                          day: 'numeric',
                          hour: 'numeric',
                          minute: '2-digit',
                        })}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-600">
                        {job.completedAt ? (
                          new Date(job.completedAt).toLocaleString('en-US', {
                            month: 'short',
                            day: 'numeric',
                            hour: 'numeric',
                            minute: '2-digit',
                          })
                        ) : job.errorMessage ? (
                          <span className="text-red-600">{job.errorMessage}</span>
                        ) : (
                          <span className="text-gray-400">—</span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <Link
                          to={`/jobs?jobId=${job.id}`}
                          className="text-indigo-600 hover:text-indigo-800 text-sm font-medium"
                        >
                          View Details
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="bg-gray-50 border border-gray-200 rounded-xl p-8 text-center">
              <p className="text-gray-600">No processing jobs yet</p>
            </div>
          )}
        </div>

        <div>
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Extracted Cards ({videoCards.length})</h2>
          {videoCards.length > 0 ? (
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200">
                    <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Frame #</th>
                    <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Deceased Name</th>
                    <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Description</th>
                    <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Confidence</th>
                    <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Status</th>
                    <th className="text-right px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {videoCards.map((card) => (
                    <tr key={card.id} className="border-b border-gray-100 hover:bg-gray-50">
                      <td className="px-6 py-4">
                        <span className="font-mono text-sm text-gray-600">
                          #{card.frameNumber}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <span className="font-medium text-gray-900">
                          {card.ocrResult?.deceased_name || (
                            <span className="text-gray-400 italic">Unknown</span>
                          )}
                        </span>
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
                        <div className="inline-flex items-center gap-4">
                          <Link
                            to={`/review/${card.id}`}
                            className="inline-flex items-center gap-1 text-indigo-600 hover:text-indigo-800 text-sm font-medium"
                          >
                            <Eye className="w-4 h-4" />
                            Review
                          </Link>
                          <button
                            onClick={() => void handleDeleteCard(card.id, card.ocrResult?.deceased_name || `Frame #${card.frameNumber}`)}
                            className="text-sm font-medium text-red-600 hover:text-red-800"
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="bg-gray-50 border border-gray-200 rounded-xl p-8 text-center">
              <p className="text-gray-600">No cards extracted yet</p>
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}

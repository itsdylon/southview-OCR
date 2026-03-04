import { useParams, Link } from 'react-router';
import { toast } from 'sonner';
import { ArrowLeft, Play, Eye } from 'lucide-react';
import { DashboardLayout } from '../layouts/dashboard-layout';
import { PipelineStepper } from '../components/pipeline-stepper';
import { StatusChip } from '../components/status-chip';
import { ConfidenceBadge } from '../components/confidence-badge';
import { useMockDb } from '../data/mock-db';
import { getConfidenceBand } from '../types/ocr';

export default function VideoDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { getVideoById, getJobsByVideoId, getCardsByVideoId } = useMockDb();
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
  
  return (
    <DashboardLayout>
      <PipelineStepper
        currentStage={video.status === 'uploaded' ? 'upload' : video.status === 'processing' ? 'process' : 'review'}
        stats={{
          upload: video.status === 'uploaded' ? 1 : 0,
          process: video.status === 'processing' ? 1 : 0,
          review: videoCards.filter((c) => c.ocrResult?.reviewStatus === 'pending' || c.ocrResult?.reviewStatus === 'flagged').length,
          publish: videoCards.filter((c) => c.ocrResult?.reviewStatus === 'approved' || c.ocrResult?.reviewStatus === 'corrected').length,
        }}
      />
      
      <div className="p-8 max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <Link
            to="/videos"
            className="inline-flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-4"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Videos
          </Link>
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 mb-2">{video.filename}</h1>
              <div className="flex items-center gap-4 text-sm text-gray-600">
                <span>Duration: {video.duration}</span>
                <span>•</span>
                <span>Size: {video.fileSize}</span>
                <span>•</span>
                <span>Frames: {video.frameCount || 0}</span>
                <span>•</span>
                <span>Cards: {video.cardCount}</span>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <StatusChip status={video.status} size="md" />
              {video.status === 'uploaded' && (
                <button
                  onClick={handleStartPipeline}
                  className="flex items-center gap-2 px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-semibold"
                >
                  <Play className="w-5 h-5" />
                  Start Full Pipeline
                </button>
              )}
            </div>
          </div>
        </div>
        
        {/* Job History */}
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
        
        {/* Cards Table */}
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
                        <Link
                          to={`/review/${card.id}`}
                          className="inline-flex items-center gap-1 text-indigo-600 hover:text-indigo-800 text-sm font-medium"
                        >
                          <Eye className="w-4 h-4" />
                          Review
                        </Link>
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

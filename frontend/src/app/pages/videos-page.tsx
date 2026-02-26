import { useState } from 'react';
import { Link } from 'react-router';
import { Upload, Play } from 'lucide-react';
import { DashboardLayout } from '../layouts/dashboard-layout';
import { StatusChip } from '../components/status-chip';
import { UploadVideoDialog } from '../components/upload-video-dialog';
import { useVideos } from '../data/mock-db';

export default function VideosPage() {
  const videos = useVideos();
  const [uploadOpen, setUploadOpen] = useState(false);
  return (
    <DashboardLayout>
      <div className="p-8 max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 mb-2">Videos</h1>
            <p className="text-gray-600">
              Manage uploaded videos and start processing pipelines
            </p>
          </div>
          <button
            onClick={() => setUploadOpen(true)}
            className="flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-semibold"
          >
            <Upload className="w-5 h-5" />
            Upload Video
          </button>
        </div>

        <UploadVideoDialog open={uploadOpen} onOpenChange={setUploadOpen} />
        
        {/* Videos Table */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Filename</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Status</th>
                <th className="text-right px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Cards</th>
                <th className="text-right px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Frames</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Duration</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Uploaded</th>
                <th className="text-right px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody>
              {videos.map((video) => (
                <tr key={video.id} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="px-6 py-4">
                    <Link
                      to={`/videos/${video.id}`}
                      className="font-medium text-gray-900 hover:text-blue-600"
                    >
                      {video.filename}
                    </Link>
                    <p className="text-sm text-gray-500">{video.fileSize}</p>
                  </td>
                  <td className="px-6 py-4">
                    <StatusChip status={video.status} />
                  </td>
                  <td className="px-6 py-4 text-right">
                    <span className="text-sm font-semibold text-gray-900">
                      {video.cardCount}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <span className="text-sm text-gray-600">
                      {video.frameCount || '—'}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span className="text-sm text-gray-600">{video.duration}</span>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">
                    {new Date(video.uploadedAt).toLocaleString('en-US', {
                      month: 'short',
                      day: 'numeric',
                      year: 'numeric',
                      hour: 'numeric',
                      minute: '2-digit',
                    })}
                  </td>
                  <td className="px-6 py-4 text-right">
                    <Link
                      to={`/videos/${video.id}`}
                      className="inline-flex items-center gap-1 text-blue-600 hover:text-blue-800 text-sm font-medium"
                    >
                      <Play className="w-4 h-4" />
                      View
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </DashboardLayout>
  );
}
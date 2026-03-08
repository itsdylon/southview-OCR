import { useNavigate } from 'react-router';
import { DashboardLayout } from '../layouts/dashboard-layout';
import { UploadWidget } from '../components/upload-video-dialog';

export default function UploadPage() {
  const navigate = useNavigate();

  return (
    <DashboardLayout>
      <div className="p-8 max-w-xl mx-auto">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Upload Video</h1>
        <p className="text-gray-600 mb-6">
          Select a video file to upload for OCR processing.
        </p>
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <UploadWidget onComplete={(video) => navigate(`/videos/${video.id}`)} />
        </div>
      </div>
    </DashboardLayout>
  );
}

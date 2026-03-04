import { createBrowserRouter } from 'react-router';
import OCROverviewPage from './pages/ocr-overview-page';
import VideosPage from './pages/videos-page';
import VideoDetailPage from './pages/video-detail-page';
import OCRJobsPage from './pages/ocr-jobs-page';
import OCRReviewQueuePage from './pages/ocr-review-queue-page';
import OCRReviewVerifyPage from './pages/ocr-review-verify-page';
import OCRSearchPage from './pages/ocr-search-page';
import UploadPage from './pages/upload-page';
import ExportBackupPage from './pages/export-backup-page';
import OCRSettingsPage from './pages/ocr-settings-page';

export const router = createBrowserRouter([
  {
    path: '/',
    Component: OCROverviewPage,
  },
  {
    path: '/upload',
    Component: UploadPage,
  },
  {
    path: '/videos',
    Component: VideosPage,
  },
  {
    path: '/videos/:id',
    Component: VideoDetailPage,
  },
  {
    path: '/jobs',
    Component: OCRJobsPage,
  },
  {
    path: '/review-queue',
    Component: OCRReviewQueuePage,
  },
  {
    path: '/review/:id',
    Component: OCRReviewVerifyPage,
  },
  {
    path: '/search',
    Component: OCRSearchPage,
  },
  {
    path: '/export',
    Component: ExportBackupPage,
  },
  {
    path: '/settings',
    Component: OCRSettingsPage,
  },
]);
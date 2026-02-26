import { useState, useRef, useCallback, useEffect } from 'react';
import { Upload, FileVideo, CheckCircle2, X } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from './ui/dialog';
import { Progress } from './ui/progress';
import { useAddVideo, useJobActions } from '../data/mock-db';

const ACCEPTED_TYPES = ['video/mp4', 'video/x-msvideo', 'video/quicktime', 'video/x-matroska'];
const ACCEPTED_EXTENSIONS = '.mp4,.avi,.mov,.mkv';

type UploadPhase = 'pick' | 'uploading' | 'done';

function formatFileSize(bytes: number): string {
  if (bytes >= 1_000_000_000) return `${(bytes / 1_000_000_000).toFixed(1)} GB`;
  if (bytes >= 1_000_000) return `${(bytes / 1_000_000).toFixed(1)} MB`;
  return `${(bytes / 1_000).toFixed(1)} KB`;
}

function randomDuration(): string {
  const mins = Math.floor(Math.random() * 5) + 1;
  const secs = Math.floor(Math.random() * 60);
  return `${mins}:${String(secs).padStart(2, '0')}`;
}

interface UploadVideoDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function UploadVideoDialog({ open, onOpenChange }: UploadVideoDialogProps) {
  const addVideo = useAddVideo();
  const { addJob, updateJob, updateVideoStatus } = useJobActions();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [phase, setPhase] = useState<UploadPhase>('pick');
  const [file, setFile] = useState<File | null>(null);
  const [progress, setProgress] = useState(0);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset state when dialog closes
  useEffect(() => {
    if (!open) {
      // Small delay so the closing animation finishes before resetting
      const t = setTimeout(() => {
        setPhase('pick');
        setFile(null);
        setProgress(0);
        setDragOver(false);
        setError(null);
      }, 200);
      return () => clearTimeout(t);
    }
  }, [open]);

  const handleFile = useCallback((f: File) => {
    setError(null);
    if (!ACCEPTED_TYPES.includes(f.type) && !f.name.match(/\.(mp4|avi|mov|mkv)$/i)) {
      setError('Unsupported file type. Please select a video file (.mp4, .avi, .mov, .mkv).');
      return;
    }
    setFile(f);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile) handleFile(droppedFile);
    },
    [handleFile]
  );

  const handleUpload = useCallback(() => {
    if (!file) return;
    setPhase('uploading');
    setProgress(0);

    // Simulate upload progress
    let current = 0;
    const interval = setInterval(() => {
      const increment = Math.random() * 15 + 5;
      current = Math.min(current + increment, 100);
      setProgress(Math.round(current));
      if (current >= 100) {
        clearInterval(interval);
        const video = addVideo(file.name, formatFileSize(file.size), randomDuration());

        // Auto-start a frame_extraction job for this video
        updateVideoStatus(video.id, 'processing');
        const job = addJob(video.id, video.filename, 'frame_extraction');

        // Simulate job progress in the background
        let jobProgress = 0;
        const jobInterval = setInterval(() => {
          const inc = Math.random() * 8 + 2;
          jobProgress = Math.min(jobProgress + inc, 100);
          const rounded = Math.round(jobProgress);
          updateJob(job.id, { progress: rounded });
          if (jobProgress >= 100) {
            clearInterval(jobInterval);
            updateJob(job.id, {
              status: 'completed',
              progress: 100,
              completedAt: new Date().toISOString(),
            });
            updateVideoStatus(video.id, 'completed');
          }
        }, 800);

        setPhase('done');
      }
    }, 300);
  }, [file, addVideo, addJob, updateJob, updateVideoStatus]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Upload Video</DialogTitle>
          <DialogDescription>
            Select a video file to upload for OCR processing.
          </DialogDescription>
        </DialogHeader>

        {/* Pick phase — file picker / drag-and-drop */}
        {phase === 'pick' && (
          <div className="space-y-4">
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed p-8 cursor-pointer transition-colors ${
                dragOver
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-300 hover:border-gray-400 hover:bg-gray-50'
              }`}
            >
              <Upload className="w-10 h-10 text-gray-400" />
              <div className="text-center">
                <p className="text-sm font-medium text-gray-700">
                  Drag and drop a video file here
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  or click to browse &mdash; .mp4, .avi, .mov, .mkv
                </p>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept={ACCEPTED_EXTENSIONS}
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) handleFile(f);
                }}
              />
            </div>

            {error && (
              <p className="text-sm text-red-600">{error}</p>
            )}

            {file && (
              <div className="flex items-center gap-3 rounded-lg border border-gray-200 bg-gray-50 p-3">
                <FileVideo className="w-8 h-8 text-blue-600 shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-gray-900 truncate">
                    {file.name}
                  </p>
                  <p className="text-xs text-gray-500">
                    {formatFileSize(file.size)}
                  </p>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setFile(null);
                  }}
                  className="p-1 text-gray-400 hover:text-gray-600 rounded"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            )}

            <DialogFooter>
              <button
                onClick={() => onOpenChange(false)}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleUpload}
                disabled={!file}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Upload
              </button>
            </DialogFooter>
          </div>
        )}

        {/* Uploading phase — progress bar */}
        {phase === 'uploading' && file && (
          <div className="space-y-4 py-2">
            <div className="flex items-center gap-3">
              <FileVideo className="w-8 h-8 text-blue-600 shrink-0" />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-gray-900 truncate">
                  {file.name}
                </p>
                <p className="text-xs text-gray-500">
                  {formatFileSize(file.size)}
                </p>
              </div>
              <span className="text-sm font-semibold text-blue-600 tabular-nums">
                {progress}%
              </span>
            </div>
            <Progress value={progress} className="h-2" />
            <p className="text-xs text-gray-500 text-center">
              Uploading video&hellip; Please don&apos;t close this dialog.
            </p>
          </div>
        )}

        {/* Done phase — success */}
        {phase === 'done' && file && (
          <div className="space-y-4 py-2">
            <div className="flex flex-col items-center gap-3 py-4">
              <CheckCircle2 className="w-12 h-12 text-green-500" />
              <div className="text-center">
                <p className="text-sm font-semibold text-gray-900">
                  Upload complete!
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  Frame extraction has started for {file.name}.
                </p>
                <p className="text-xs text-gray-500">
                  Check the Jobs page to monitor progress.
                </p>
              </div>
            </div>
            <DialogFooter>
              <button
                onClick={() => onOpenChange(false)}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
              >
                Done
              </button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

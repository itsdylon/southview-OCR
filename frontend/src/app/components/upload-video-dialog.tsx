import { useState, useRef, useCallback } from 'react';
import { Upload, FileVideo, CheckCircle2, X, Loader2 } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from './ui/dialog';
import { Progress } from './ui/progress';
import { useApiState } from '../data/mock-db';
import * as api from '../data/api';
import type { Video } from '../types/ocr';

const ACCEPTED_TYPES = ['video/mp4', 'video/x-msvideo', 'video/quicktime', 'video/x-matroska'];
const ACCEPTED_EXTENSIONS = '.mp4,.avi,.mov,.mkv';

type UploadPhase = 'pick' | 'uploading' | 'processing' | 'done';

function formatFileSize(bytes: number): string {
  if (bytes >= 1_000_000_000) return `${(bytes / 1_000_000_000).toFixed(1)} GB`;
  if (bytes >= 1_000_000) return `${(bytes / 1_000_000).toFixed(1)} MB`;
  return `${(bytes / 1_000).toFixed(1)} KB`;
}

/* ------------------------------------------------------------------ */
/* UploadWidget — standalone upload UI (no dialog wrapper)            */
/* ------------------------------------------------------------------ */

interface UploadWidgetProps {
  onComplete?: (video: Video) => void;
  onCancel?: () => void;
  showCancel?: boolean;
}

export function UploadWidget({ onComplete, onCancel, showCancel }: UploadWidgetProps) {
  const { refreshVideos, refreshJobs } = useApiState();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<(() => void) | null>(null);

  const [phase, setPhase] = useState<UploadPhase>('pick');
  const [file, setFile] = useState<File | null>(null);
  const [progress, setProgress] = useState(0);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  const handleUpload = useCallback(async () => {
    if (!file) return;
    setPhase('uploading');
    setProgress(0);
    setError(null);

    try {
      const { promise, abort } = api.uploadVideoWithProgress(file, (pct) => {
        setProgress(pct);
      });
      abortRef.current = abort;

      const video = await promise;

      setPhase('processing');

      await api.startJob(video.id);

      await Promise.all([refreshVideos(), refreshJobs()]);

      if (onComplete) {
        onComplete(video);
      } else {
        setPhase('done');
      }
    } catch (e: any) {
      if (e.name === 'AbortError') return;
      setError(e.message ?? 'Upload failed');
      setPhase('pick');
    }
  }, [file, refreshVideos, refreshJobs, onComplete]);

  return (
    <>
      {/* Pick phase */}
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

          <div className="flex justify-end gap-2">
            {showCancel && onCancel && (
              <button
                onClick={onCancel}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
            )}
            <button
              onClick={handleUpload}
              disabled={!file}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Upload
            </button>
          </div>
        </div>
      )}

      {/* Uploading phase */}
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
            Uploading video&hellip; Please don&apos;t close this page.
          </p>
        </div>
      )}

      {/* Processing phase */}
      {phase === 'processing' && file && (
        <div className="space-y-4 py-2">
          <div className="flex flex-col items-center gap-3 py-4">
            <Loader2 className="w-10 h-10 text-blue-600 animate-spin" />
            <div className="text-center">
              <p className="text-sm font-semibold text-gray-900">
                Processing...
              </p>
              <p className="text-xs text-gray-500 mt-1">
                Starting pipeline for {file.name}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Done phase (only shown when no onComplete callback) */}
      {phase === 'done' && file && (
        <div className="space-y-4 py-2">
          <div className="flex flex-col items-center gap-3 py-4">
            <CheckCircle2 className="w-12 h-12 text-green-500" />
            <div className="text-center">
              <p className="text-sm font-semibold text-gray-900">
                Upload complete!
              </p>
              <p className="text-xs text-gray-500 mt-1">
                Processing has started for {file.name}.
              </p>
              <p className="text-xs text-gray-500">
                Check the Jobs page to monitor progress.
              </p>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

/* ------------------------------------------------------------------ */
/* UploadVideoDialog — thin wrapper around UploadWidget               */
/* ------------------------------------------------------------------ */

interface UploadVideoDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function UploadVideoDialog({ open, onOpenChange }: UploadVideoDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Upload Video</DialogTitle>
          <DialogDescription>
            Select a video file to upload for OCR processing.
          </DialogDescription>
        </DialogHeader>
        <UploadWidget showCancel onCancel={() => onOpenChange(false)} />
      </DialogContent>
    </Dialog>
  );
}

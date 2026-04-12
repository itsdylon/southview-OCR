// Core types for Southview OCR application

export type VideoStatus = 'uploaded' | 'processing' | 'completed' | 'failed';

export type JobType = 'frame_extraction' | 'ocr' | 'full_pipeline';

export type JobStatus = 'queued' | 'running' | 'completed' | 'failed';

export type ReviewStatus = 'pending' | 'approved' | 'flagged' | 'corrected';

export type ConfidenceBand = 'auto-approved' | 'pending-review' | 'flagged';

export interface Video {
  id: string;
  filename: string;
  status: VideoStatus;
  uploadedAt: string;
  processedAt?: string;
  cardCount: number;
  frameCount?: number;
  duration?: string;
  fileSize?: string;
}

export interface Job {
  id: string;
  videoId: string;
  videoName: string;
  jobType: JobType;
  status: JobStatus;
  progress: number;
  createdAt: string;
  startedAt?: string;
  completedAt?: string;
  errorMessage?: string;
}

export interface Card {
  id: string;
  videoId: string;
  imagePath: string;
  frameNumber: number;
  sequenceIndex: number;
  ocrResult?: OCRResult;
}

export interface OCRResult {
  id: string;
  cardId: string;
  reviewStatus: ReviewStatus;
  confidenceScore: number;
  rawText: string;
  rawFieldsJson: string;
  rotationDegrees?: number;
  wordConfidences?: Record<string, number>;
  
  // Structured fields (editable)
  deceased_name: string | null;
  address: string | null;
  owner: string | null;
  relation: string | null;
  phone: string | null;
  date_of_death: string | null;
  date_of_burial: string | null;
  description: string | null;
  sex: string | null;
  age: string | null;
  grave_type: string | null;
  grave_fee: string | null;
  undertaker: string | null;
  board_of_health_no: string | null;
  svc_no: string | null;
  
  // Metadata
  createdAt: string;
  updatedAt?: string;
  reviewVersion: number;
  reviewedBy?: string;
}

export interface CardWithOCR extends Card {
  ocrResult: OCRResult;
}

export interface PipelineStats {
  videosProcessing: number;
  jobsRunning: number;
  cardsFlagged: number;
  cardsPending: number;
  cardsAutoApproved: number;
  cardsApprovedCorrected: number;
}

export interface ConfidenceThresholds {
  autoApprove: number; // >= 0.85
  pendingReview: number; // 0.70
}

export function getConfidenceBand(score: number): ConfidenceBand {
  if (score >= 0.85) return 'auto-approved';
  if (score >= 0.70) return 'pending-review';
  return 'flagged';
}

export function getConfidenceBandLabel(band: ConfidenceBand): string {
  switch (band) {
    case 'auto-approved':
      return 'Auto-approved (≥85%)';
    case 'pending-review':
      return 'Pending Review (70-84%)';
    case 'flagged':
      return 'Flagged (<70%)';
  }
}

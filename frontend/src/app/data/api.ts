/**
 * API client for the Southview OCR backend.
 * All fetch functions handle snake_case → camelCase transformation.
 */

import type { Video, Job, CardWithOCR, OCRResult, ReviewStatus } from '../types/ocr';

// ---------------------------------------------------------------------------
// Error class
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

// ---------------------------------------------------------------------------
// Shared fetch helper
// ---------------------------------------------------------------------------

async function apiFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch { /* ignore */ }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Data transformers
// ---------------------------------------------------------------------------

function formatFileSize(bytes: number | null | undefined): string {
  if (!bytes) return '';
  if (bytes >= 1_000_000_000) return `${(bytes / 1_000_000_000).toFixed(1)} GB`;
  if (bytes >= 1_000_000) return `${(bytes / 1_000_000).toFixed(1)} MB`;
  return `${(bytes / 1_000).toFixed(1)} KB`;
}

function formatDuration(seconds: number | null | undefined): string {
  if (!seconds) return '';
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${mins}:${String(secs).padStart(2, '0')}`;
}

// -- Raw API response shapes (snake_case from backend) --

interface RawVideo {
  id: string;
  filename: string;
  status: string;
  upload_timestamp: string | null;
  duration_seconds: number | null;
  file_size_bytes: number | null;
  frame_count: number | null;
  card_count: number;
  // detail-only fields
  filepath?: string;
  file_hash?: string;
  resolution?: string | null;
  fps?: number | null;
}

interface RawJob {
  id: string;
  video_id: string;
  video_name: string | null;
  job_type: string;
  status: string;
  progress: number;
  error_message: string | null;
  created_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  replaces_job?: string;
}

interface RawCard {
  id: string;
  video_id: string;
  sequence_index: number;
  frame_number: number;
  image_path: string;
  raw_text: string;
  raw_fields_json?: string | null;
  corrected_text: string | null;
  confidence_score: number;
  rotation_degrees?: number | null;
  review_status: string;
  // structured fields (snake_case — matches frontend type)
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
}

interface RawCardDetail {
  id: string;
  video_id: string;
  sequence_index: number;
  frame_number: number;
  image_path: string;
  image_url: string;
  ocr: {
    raw_text: string;
    corrected_text: string | null;
    confidence_score: number;
    word_confidences: string;
    review_status: string;
    reviewed_by: string | null;
    reviewed_at: string | null;
    raw_fields_json: string | null;
    processed_at: string | null;
    rotation_degrees: number | null;
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
  } | null;
}

interface RawCardsResponse {
  total: number;
  page: number;
  per_page: number;
  pages: number;
  cards: RawCard[];
}

// -- Mappers --

function mapVideo(v: RawVideo): Video {
  return {
    id: v.id,
    filename: v.filename,
    status: v.status as Video['status'],
    uploadedAt: v.upload_timestamp ?? new Date().toISOString(),
    cardCount: v.card_count ?? 0,
    frameCount: v.frame_count ?? undefined,
    fileSize: formatFileSize(v.file_size_bytes),
    duration: formatDuration(v.duration_seconds),
  };
}

function mapJob(j: RawJob): Job {
  return {
    id: j.id,
    videoId: j.video_id,
    videoName: j.video_name ?? '',
    jobType: j.job_type as Job['jobType'],
    status: j.status as Job['status'],
    progress: j.progress,
    createdAt: j.created_at ?? new Date().toISOString(),
    startedAt: j.started_at ?? undefined,
    completedAt: j.completed_at ?? undefined,
    errorMessage: j.error_message ?? undefined,
  };
}

function mapCardFromList(c: RawCard): CardWithOCR {
  const imagePath = `/static/frames/${c.video_id}/card_${String(c.sequence_index).padStart(4, '0')}.jpg`;
  return {
    id: c.id,
    videoId: c.video_id,
    imagePath,
    frameNumber: c.frame_number,
    sequenceIndex: c.sequence_index,
    ocrResult: {
      id: c.id, // use card id as fallback
      cardId: c.id,
      reviewStatus: (c.review_status || 'pending') as ReviewStatus,
      confidenceScore: c.confidence_score,
      rawText: c.raw_text,
      rawFieldsJson: c.raw_fields_json ?? '',
      rotationDegrees: c.rotation_degrees ?? 0,
      deceased_name: c.deceased_name,
      address: c.address,
      owner: c.owner,
      relation: c.relation,
      phone: c.phone,
      date_of_death: c.date_of_death,
      date_of_burial: c.date_of_burial,
      description: c.description,
      sex: c.sex,
      age: c.age,
      grave_type: c.grave_type,
      grave_fee: c.grave_fee,
      undertaker: c.undertaker,
      board_of_health_no: c.board_of_health_no,
      svc_no: c.svc_no,
      createdAt: new Date().toISOString(),
    },
  };
}

function mapCardFromDetail(d: RawCardDetail): CardWithOCR {
  const imagePath = d.image_url || `/static/frames/${d.video_id}/card_${String(d.sequence_index).padStart(4, '0')}.jpg`;
  const ocr = d.ocr;
  return {
    id: d.id,
    videoId: d.video_id,
    imagePath,
    frameNumber: d.frame_number,
    sequenceIndex: d.sequence_index,
    ocrResult: {
      id: d.id,
      cardId: d.id,
      reviewStatus: (ocr?.review_status || 'pending') as ReviewStatus,
      confidenceScore: ocr?.confidence_score ?? 0,
      rawText: ocr?.raw_text ?? '',
      rawFieldsJson: ocr?.raw_fields_json ?? '',
      rotationDegrees: ocr?.rotation_degrees ?? 0,
      wordConfidences: ocr?.word_confidences ? JSON.parse(ocr.word_confidences) : undefined,
      deceased_name: ocr?.deceased_name ?? null,
      address: ocr?.address ?? null,
      owner: ocr?.owner ?? null,
      relation: ocr?.relation ?? null,
      phone: ocr?.phone ?? null,
      date_of_death: ocr?.date_of_death ?? null,
      date_of_burial: ocr?.date_of_burial ?? null,
      description: ocr?.description ?? null,
      sex: ocr?.sex ?? null,
      age: ocr?.age ?? null,
      grave_type: ocr?.grave_type ?? null,
      grave_fee: ocr?.grave_fee ?? null,
      undertaker: ocr?.undertaker ?? null,
      board_of_health_no: ocr?.board_of_health_no ?? null,
      svc_no: ocr?.svc_no ?? null,
      createdAt: ocr?.processed_at ?? new Date().toISOString(),
      reviewedBy: ocr?.reviewed_by ?? undefined,
    },
  };
}

// ---------------------------------------------------------------------------
// Public API functions
// ---------------------------------------------------------------------------

export async function fetchVideos(): Promise<Video[]> {
  const raw = await apiFetch<RawVideo[]>('/api/videos');
  return raw.map(mapVideo);
}

export async function fetchVideoDetail(id: string): Promise<Video> {
  const raw = await apiFetch<RawVideo>(`/api/videos/${id}`);
  return mapVideo(raw);
}

export async function deleteVideo(videoId: string): Promise<void> {
  await apiFetch(`/api/videos/${videoId}`, { method: 'DELETE' });
}

export async function uploadVideo(file: File): Promise<{ video: Video; xhr: XMLHttpRequest }> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const formData = new FormData();
    formData.append('file', file);

    xhr.open('POST', '/api/videos/upload');

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const raw = JSON.parse(xhr.responseText) as RawVideo;
          // Upload response has slightly different shape — fill defaults
          const video: Video = {
            id: raw.id,
            filename: raw.filename,
            status: raw.status as Video['status'],
            uploadedAt: new Date().toISOString(),
            cardCount: 0,
            frameCount: raw.frame_count ?? undefined,
            fileSize: formatFileSize(raw.file_size_bytes),
            duration: formatDuration(raw.duration_seconds),
          };
          resolve({ video, xhr });
        } catch (e) {
          reject(new Error('Failed to parse upload response'));
        }
      } else {
        let detail = xhr.statusText;
        try {
          const body = JSON.parse(xhr.responseText);
          detail = body.detail ?? detail;
        } catch { /* ignore */ }
        reject(new ApiError(xhr.status, detail));
      }
    };

    xhr.onerror = () => reject(new Error('Network error during upload'));
    xhr.send(formData);
  });
}

/**
 * Upload a video with progress tracking via a callback.
 * Returns the created Video and auto-started Job.
 */
export function uploadVideoWithProgress(
  file: File,
  onProgress: (pct: number) => void,
): { promise: Promise<Video>; abort: () => void } {
  const xhr = new XMLHttpRequest();
  const formData = new FormData();
  formData.append('file', file);

  const promise = new Promise<Video>((resolve, reject) => {
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    };

    xhr.open('POST', '/api/videos/upload');

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const raw = JSON.parse(xhr.responseText);
          const video: Video = {
            id: raw.id,
            filename: raw.filename,
            status: raw.status as Video['status'],
            uploadedAt: new Date().toISOString(),
            cardCount: 0,
            frameCount: raw.frame_count ?? undefined,
            fileSize: formatFileSize(raw.file_size_bytes),
            duration: formatDuration(raw.duration_seconds),
          };
          resolve(video);
        } catch {
          reject(new Error('Failed to parse upload response'));
        }
      } else {
        let detail = xhr.statusText;
        try {
          const body = JSON.parse(xhr.responseText);
          detail = body.detail ?? detail;
        } catch { /* ignore */ }
        reject(new ApiError(xhr.status, detail));
      }
    };

    xhr.onerror = () => reject(new Error('Network error during upload'));
    xhr.send(formData);
  });

  return { promise, abort: () => xhr.abort() };
}

export async function fetchJobs(): Promise<Job[]> {
  const raw = await apiFetch<RawJob[]>('/api/jobs');
  return raw.map(mapJob);
}

export async function fetchJob(jobId: string): Promise<Job> {
  const raw = await apiFetch<RawJob>(`/api/jobs/${jobId}`);
  return mapJob(raw);
}

export async function startJob(videoId: string): Promise<Job> {
  const raw = await apiFetch<RawJob>(`/api/jobs/${videoId}/start`, { method: 'POST' });
  return mapJob(raw);
}

export async function retryJob(jobId: string): Promise<Job> {
  const raw = await apiFetch<RawJob>(`/api/jobs/${jobId}/retry`, { method: 'POST' });
  return mapJob(raw);
}

export async function fetchCards(params?: {
  videoId?: string;
  status?: string;
  page?: number;
  perPage?: number;
}): Promise<{ cards: CardWithOCR[]; total: number; page: number; pages: number }> {
  const searchParams = new URLSearchParams();
  if (params?.videoId) searchParams.set('video_id', params.videoId);
  if (params?.status) searchParams.set('status', params.status);
  if (params?.page) searchParams.set('page', String(params.page));
  if (params?.perPage) searchParams.set('per_page', String(params.perPage));

  const qs = searchParams.toString();
  const raw = await apiFetch<RawCardsResponse>(`/api/cards${qs ? `?${qs}` : ''}`);
  return {
    cards: raw.cards.map(mapCardFromList),
    total: raw.total,
    page: raw.page,
    pages: raw.pages,
  };
}

export async function fetchCard(cardId: string): Promise<CardWithOCR> {
  const raw = await apiFetch<RawCardDetail>(`/api/cards/${cardId}`);
  return mapCardFromDetail(raw);
}

export async function deleteCard(cardId: string): Promise<void> {
  await apiFetch(`/api/cards/${cardId}`, { method: 'DELETE' });
}

export async function submitReview(
  cardId: string,
  fields: Partial<OCRResult>,
  status: ReviewStatus,
): Promise<void> {
  // Build the request body with structured fields
  const body: Record<string, unknown> = { status };

  // Map structured fields directly (they're already snake_case)
  const structuredFields = [
    'deceased_name',
    'date_of_death',
    'date_of_burial',
    'description',
    'sex',
    'age',
    'undertaker',
    'svc_no',
  ] as const;

  for (const f of structuredFields) {
    if (f in fields && fields[f] !== undefined) {
      body[f] = fields[f];
    }
  }

  if (fields.rawText !== undefined) {
    body.corrected_text = fields.rawText;
  }

  await apiFetch(`/api/cards/${cardId}/review`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function batchReview(cardIds: string[], status: ReviewStatus): Promise<void> {
  await apiFetch('/api/cards/batch-review', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ card_ids: cardIds, status }),
  });
}

export async function fetchStats(): Promise<Record<string, number>> {
  return apiFetch<Record<string, number>>('/api/stats');
}

export async function downloadExport(
  format: 'csv' | 'json',
  videoId?: string,
  status?: string,
): Promise<Blob> {
  const params = new URLSearchParams({ format });
  if (videoId) params.set('video_id', videoId);
  if (status) params.set('status', status);

  const res = await fetch(`/api/export?${params.toString()}`);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      try {
        detail = await res.text();
      } catch { /* ignore */ }
    }
    throw new ApiError(res.status, detail);
  }
  return res.blob();
}

export async function fetchThresholds(): Promise<{ auto_approve: number; review_threshold: number }> {
  return apiFetch('/api/settings/thresholds');
}

export async function updateThresholds(autoApprove: number, reviewThreshold: number): Promise<void> {
  await apiFetch('/api/settings/thresholds', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ auto_approve: autoApprove, review_threshold: reviewThreshold }),
  });
}

export async function triggerBackup(): Promise<{ status: string; backup_path: string }> {
  return apiFetch('/api/backup', { method: 'POST' });
}

export async function fetchBackups(): Promise<
  Array<{ filename: string; created_at: string; size_bytes: number }>
> {
  return apiFetch('/api/backups');
}

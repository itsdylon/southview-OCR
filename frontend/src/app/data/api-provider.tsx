/**
 * API-backed provider that exposes the exact same hook signatures as MockDbProvider.
 * Drop-in replacement — zero import changes needed across page files.
 */

import { createContext, useContext, useState, useCallback, useMemo, useEffect, useRef } from 'react';
import type { ReactNode } from 'react';
import { toast } from 'sonner';
import type { CardWithOCR, Video, Job, OCRResult, PipelineStats, ReviewStatus, VideoStatus, JobType } from '../types/ocr';
import * as api from './api';

interface MockDb {
  cards: CardWithOCR[];
  videos: Video[];
  jobs: Job[];
  pipelineStats: PipelineStats;
  updateCardFields: (cardId: string, fields: Partial<OCRResult>) => void;
  updateCardStatus: (cardId: string, status: ReviewStatus) => void;
  getCardsByVideoId: (videoId: string) => CardWithOCR[];
  getJobsByVideoId: (videoId: string) => Job[];
  getVideoById: (id: string) => Video | undefined;
  addVideo: (filename: string, fileSize: string, duration?: string) => Video;
  updateVideoStatus: (videoId: string, status: VideoStatus) => void;
  addJob: (videoId: string, videoName: string, jobType: JobType) => Job;
  updateJob: (jobId: string, fields: Partial<Pick<Job, 'status' | 'progress' | 'startedAt' | 'completedAt' | 'errorMessage'>>) => void;
  // New API-specific methods
  loading: boolean;
  error: string | null;
  refreshVideos: () => Promise<void>;
  refreshJobs: () => Promise<void>;
  refreshCards: () => Promise<void>;
  deleteVideo: (videoId: string) => Promise<void>;
  deleteCard: (cardId: string) => Promise<void>;
}

const MockDbContext = createContext<MockDb | null>(null);

export function MockDbProvider({ children }: { children: ReactNode }) {
  const [cards, setCards] = useState<CardWithOCR[]>([]);
  const [videos, setVideos] = useState<Video[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [backendStats, setBackendStats] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // --- Data fetching ---

  const refreshVideos = useCallback(async () => {
    try {
      const data = await api.fetchVideos();
      setVideos(data);
    } catch (e) {
      console.error('Failed to fetch videos:', e);
    }
  }, []);

  const refreshJobs = useCallback(async () => {
    try {
      const data = await api.fetchJobs();
      setJobs(data);
    } catch (e) {
      console.error('Failed to fetch jobs:', e);
    }
  }, []);

  const refreshCards = useCallback(async () => {
    try {
      const result = await api.fetchCards({ perPage: 500 });
      setCards(result.cards);
    } catch (e) {
      console.error('Failed to fetch cards:', e);
    }
  }, []);

  const refreshStats = useCallback(async () => {
    try {
      const data = await api.fetchStats();
      setBackendStats(data);
    } catch (e) {
      console.error('Failed to fetch stats:', e);
    }
  }, []);

  // Initial load
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [vids, jbs, crds, sts] = await Promise.all([
          api.fetchVideos(),
          api.fetchJobs(),
          api.fetchCards({ perPage: 500 }),
          api.fetchStats(),
        ]);
        if (cancelled) return;
        setVideos(vids);
        setJobs(jbs);
        setCards(crds.cards);
        setBackendStats(sts);
      } catch (e: any) {
        if (cancelled) return;
        setError(e.message ?? 'Failed to load data from backend');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  // --- Phase 5: Job polling ---

  useEffect(() => {
    const activeJobs = jobs.filter((j) => j.status === 'queued' || j.status === 'running');

    if (activeJobs.length === 0) {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }

    // Poll every 2 seconds
    pollRef.current = setInterval(async () => {
      let anyCompleted = false;
      const updatedJobs = await Promise.all(
        activeJobs.map(async (j) => {
          try {
            const updated = await api.fetchJob(j.id);
            if (
              (j.status === 'queued' || j.status === 'running') &&
              (updated.status === 'completed' || updated.status === 'failed')
            ) {
              anyCompleted = true;
            }
            return updated;
          } catch {
            return j;
          }
        }),
      );

      // Merge polled updates into jobs state
      setJobs((prev) => {
        const map = new Map(prev.map((j) => [j.id, j]));
        for (const u of updatedJobs) {
          map.set(u.id, u);
        }
        return Array.from(map.values());
      });

      // If any job completed, refresh videos, cards, and stats
      if (anyCompleted) {
        refreshVideos();
        refreshCards();
        refreshStats();
      }
    }, 2000);

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [jobs, refreshVideos, refreshCards, refreshStats]);

  // --- Mutations ---

  const addVideo = useCallback((_filename: string, _fileSize: string, _duration?: string): Video => {
    // No-op locally — upload dialog handles uploads directly via api.ts, then triggers refresh
    const placeholder: Video = {
      id: `temp-${Date.now()}`,
      filename: _filename,
      status: 'uploaded',
      uploadedAt: new Date().toISOString(),
      cardCount: 0,
      fileSize: _fileSize,
      duration: _duration,
    };
    return placeholder;
  }, []);

  const updateVideoStatus = useCallback((_videoId: string, _status: VideoStatus) => {
    // Local-only update for optimistic UI
    setVideos((prev) =>
      prev.map((v) => (v.id === _videoId ? { ...v, status: _status } : v)),
    );
  }, []);

  const addJob = useCallback((videoId: string, videoName: string, jobType: JobType): Job => {
    // Call the real API — but since this is synchronous in the hook signature,
    // we fire-and-forget and do the API call + refresh separately.
    // Return a placeholder for immediate UI use.
    const placeholder: Job = {
      id: `temp-${Date.now()}`,
      videoId,
      videoName,
      jobType,
      status: 'queued',
      progress: 0,
      createdAt: new Date().toISOString(),
    };

    // Fire API call in background
    api.startJob(videoId).then((realJob) => {
      setJobs((prev) => prev.map((j) => (j.id === placeholder.id ? realJob : j)));
    }).catch(console.error);

    setJobs((prev) => [placeholder, ...prev]);
    return placeholder;
  }, []);

  const updateJob = useCallback(
    (_jobId: string, fields: Partial<Pick<Job, 'status' | 'progress' | 'startedAt' | 'completedAt' | 'errorMessage'>>) => {
      // Local-only optimistic update (polling will handle real state)
      setJobs((prev) =>
        prev.map((j) => (j.id === _jobId ? { ...j, ...fields } : j)),
      );
    },
    [],
  );

  const updateCardFields = useCallback((cardId: string, fields: Partial<OCRResult>) => {
    const previousCards = cards;
    const currentCard = previousCards.find((c) => c.id === cardId);
    if (!currentCard) return;
    const reviewVersion = currentCard?.ocrResult.reviewVersion ?? 0;

    // Optimistic local update
    setCards((prev) =>
      prev.map((c) =>
        c.id === cardId
          ? {
              ...c,
              ocrResult: {
                ...c.ocrResult,
                ...fields,
                reviewVersion: c.ocrResult.reviewVersion + 1,
                updatedAt: new Date().toISOString(),
              },
            }
          : c,
      ),
    );

    // Send to backend
    const status = fields.reviewStatus ?? 'approved';
    api.submitReview(cardId, fields, status, reviewVersion).catch(async (error) => {
      console.error(error);
      setCards(previousCards);
      toast.error('Review update failed', {
        description: error instanceof Error ? error.message : 'Could not save changes.',
      });
      await refreshCards();
    });
  }, [cards, refreshCards]);

  const updateCardStatus = useCallback((cardId: string, status: ReviewStatus) => {
    const previousCards = cards;
    const currentCard = previousCards.find((c) => c.id === cardId);
    if (!currentCard) return;
    const reviewVersion = currentCard?.ocrResult.reviewVersion ?? 0;

    // Optimistic local update
    setCards((prev) =>
      prev.map((c) =>
        c.id === cardId
          ? {
              ...c,
              ocrResult: {
                ...c.ocrResult,
                reviewStatus: status,
                reviewVersion: c.ocrResult.reviewVersion + 1,
                updatedAt: new Date().toISOString(),
                reviewedBy: 'admin',
              },
            }
          : c,
      ),
    );

    // Send to backend
    api.submitReview(cardId, {}, status, reviewVersion).catch(async (error) => {
      console.error(error);
      setCards(previousCards);
      toast.error('Review status update failed', {
        description: error instanceof Error ? error.message : 'Could not save status.',
      });
      await refreshCards();
    });
  }, [cards, refreshCards]);

  const deleteVideo = useCallback(async (videoId: string) => {
    await api.deleteVideo(videoId);
    setVideos((prev) => prev.filter((v) => v.id !== videoId));
    setJobs((prev) => prev.filter((j) => j.videoId !== videoId));
    setCards((prev) => prev.filter((c) => c.videoId !== videoId));
    await Promise.all([refreshVideos(), refreshJobs(), refreshCards(), refreshStats()]);
  }, [refreshCards, refreshJobs, refreshStats, refreshVideos]);

  const deleteCard = useCallback(async (cardId: string) => {
    const deletedCard = cards.find((c) => c.id === cardId);
    await api.deleteCard(cardId);
    setCards((prev) => prev.filter((c) => c.id !== cardId));
    if (deletedCard) {
      setVideos((prev) =>
        prev.map((v) =>
          v.id === deletedCard.videoId
            ? { ...v, cardCount: Math.max(0, v.cardCount - 1) }
            : v,
        ),
      );
    }
    await Promise.all([refreshVideos(), refreshCards(), refreshStats()]);
  }, [cards, refreshCards, refreshStats, refreshVideos]);

  // --- Computed stats ---

  const pipelineStats = useMemo<PipelineStats>(() => {
    return {
      videosProcessing: videos.filter((v) => v.status === 'processing').length,
      jobsRunning: jobs.filter((j) => j.status === 'running' || j.status === 'queued').length,
      cardsFlagged: backendStats.flagged ?? cards.filter((c) => c.ocrResult.reviewStatus === 'flagged').length,
      cardsPending: backendStats.pending ?? cards.filter((c) => c.ocrResult.reviewStatus === 'pending').length,
      cardsAutoApproved: backendStats.approved ?? cards.filter((c) => c.ocrResult.reviewStatus === 'approved').length,
      cardsApprovedCorrected:
        (backendStats.approved ?? 0) + (backendStats.corrected ?? 0) ||
        cards.filter((c) => c.ocrResult.reviewStatus === 'approved' || c.ocrResult.reviewStatus === 'corrected').length,
    };
  }, [cards, videos, jobs, backendStats]);

  // --- Lookups ---

  const getCardsByVideoId = useCallback(
    (videoId: string) => cards.filter((c) => c.videoId === videoId),
    [cards],
  );

  const getJobsByVideoId = useCallback(
    (videoId: string) => jobs.filter((j) => j.videoId === videoId),
    [jobs],
  );

  const getVideoById = useCallback(
    (id: string) => videos.find((v) => v.id === id),
    [videos],
  );

  return (
    <MockDbContext.Provider
      value={{
        cards,
        videos,
        jobs,
        pipelineStats,
        updateCardFields,
        updateCardStatus,
        getCardsByVideoId,
        getJobsByVideoId,
        getVideoById,
        addVideo,
        updateVideoStatus,
        addJob,
        updateJob,
        loading,
        error,
        refreshVideos,
        refreshJobs,
        refreshCards,
        deleteVideo,
        deleteCard,
      }}
    >
      {children}
    </MockDbContext.Provider>
  );
}

function useMockDbContext(): MockDb {
  const ctx = useContext(MockDbContext);
  if (!ctx) throw new Error('useMockDb must be used within MockDbProvider');
  return ctx;
}

/** Full store access */
export function useMockDb(): MockDb {
  return useMockDbContext();
}

/** Drop-in replacement for the old useCardStore hook */
export function useCardStore(): Pick<MockDb, 'cards' | 'updateCardFields' | 'updateCardStatus' | 'deleteCard'> {
  const { cards, updateCardFields, updateCardStatus, deleteCard } = useMockDbContext();
  return { cards, updateCardFields, updateCardStatus, deleteCard };
}

/** Videos list */
export function useVideos(): Video[] {
  return useMockDbContext().videos;
}

/** Add a new video */
export function useAddVideo() {
  return useMockDbContext().addVideo;
}

/** Jobs list */
export function useJobs(): Job[] {
  return useMockDbContext().jobs;
}

/** Job mutations */
export function useJobActions() {
  const { addJob, updateJob, updateVideoStatus } = useMockDbContext();
  return { addJob, updateJob, updateVideoStatus };
}

/** Computed pipeline stats */
export function usePipelineStats(): PipelineStats {
  return useMockDbContext().pipelineStats;
}

/** API-specific: loading state and refresh helpers */
export function useApiState() {
  const { loading, error, refreshVideos, refreshJobs, refreshCards } = useMockDbContext();
  return { loading, error, refreshVideos, refreshJobs, refreshCards };
}

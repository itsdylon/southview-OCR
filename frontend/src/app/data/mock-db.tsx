import { createContext, useContext, useState, useCallback, useMemo } from 'react';
import type { ReactNode } from 'react';
import type { CardWithOCR, Video, Job, OCRResult, PipelineStats, ReviewStatus, VideoStatus, JobType, JobStatus } from '../types/ocr';
import { mockCards as seedCards, mockVideos as seedVideos, mockJobs as seedJobs } from './ocrMockData';

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
}

const MockDbContext = createContext<MockDb | null>(null);

export function MockDbProvider({ children }: { children: ReactNode }) {
  const [cards, setCards] = useState<CardWithOCR[]>(() =>
    seedCards.map((c) => ({ ...c, ocrResult: { ...c.ocrResult } }))
  );
  const [videos, setVideos] = useState<Video[]>(() => seedVideos.map((v) => ({ ...v })));
  const [jobs, setJobs] = useState<Job[]>(() => seedJobs.map((j) => ({ ...j })));

  const addVideo = useCallback((filename: string, fileSize: string, duration?: string): Video => {
    const newVideo: Video = {
      id: `vid-${String(Date.now()).slice(-6)}`,
      filename,
      status: 'uploaded',
      uploadedAt: new Date().toISOString(),
      cardCount: 0,
      fileSize,
      duration,
    };
    setVideos((prev) => [newVideo, ...prev]);
    return newVideo;
  }, []);

  const updateVideoStatus = useCallback((videoId: string, status: VideoStatus) => {
    setVideos((prev) =>
      prev.map((v) => (v.id === videoId ? { ...v, status } : v))
    );
  }, []);

  const addJob = useCallback((videoId: string, videoName: string, jobType: JobType): Job => {
    const newJob: Job = {
      id: `job-${String(Date.now()).slice(-6)}`,
      videoId,
      videoName,
      jobType,
      status: 'running',
      progress: 0,
      createdAt: new Date().toISOString(),
      startedAt: new Date().toISOString(),
    };
    setJobs((prev) => [newJob, ...prev]);
    return newJob;
  }, []);

  const updateJob = useCallback(
    (jobId: string, fields: Partial<Pick<Job, 'status' | 'progress' | 'startedAt' | 'completedAt' | 'errorMessage'>>) => {
      setJobs((prev) =>
        prev.map((j) => (j.id === jobId ? { ...j, ...fields } : j))
      );
    },
    []
  );

  const updateCardFields = useCallback((cardId: string, fields: Partial<OCRResult>) => {
    setCards((prev) =>
      prev.map((c) =>
        c.id === cardId
          ? { ...c, ocrResult: { ...c.ocrResult, ...fields, updatedAt: new Date().toISOString() } }
          : c
      )
    );
  }, []);

  const updateCardStatus = useCallback((cardId: string, status: ReviewStatus) => {
    setCards((prev) =>
      prev.map((c) =>
        c.id === cardId
          ? {
              ...c,
              ocrResult: {
                ...c.ocrResult,
                reviewStatus: status,
                updatedAt: new Date().toISOString(),
                reviewedBy: 'admin',
              },
            }
          : c
      )
    );
  }, []);

  const pipelineStats = useMemo<PipelineStats>(() => {
    const cardsFlagged = cards.filter((c) => c.ocrResult.reviewStatus === 'flagged').length;
    const cardsPending = cards.filter((c) => c.ocrResult.reviewStatus === 'pending').length;
    const cardsApproved = cards.filter((c) => c.ocrResult.reviewStatus === 'approved').length;
    const cardsCorrected = cards.filter((c) => c.ocrResult.reviewStatus === 'corrected').length;
    return {
      videosProcessing: videos.filter((v) => v.status === 'processing').length,
      jobsRunning: jobs.filter((j) => j.status === 'running').length,
      cardsFlagged,
      cardsPending,
      cardsAutoApproved: cardsApproved,
      cardsApprovedCorrected: cardsApproved + cardsCorrected,
    };
  }, [cards, videos, jobs]);

  const getCardsByVideoId = useCallback(
    (videoId: string) => cards.filter((c) => c.videoId === videoId),
    [cards]
  );

  const getJobsByVideoId = useCallback(
    (videoId: string) => jobs.filter((j) => j.videoId === videoId),
    [jobs]
  );

  const getVideoById = useCallback(
    (id: string) => videos.find((v) => v.id === id),
    [videos]
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
export function useCardStore(): Pick<MockDb, 'cards' | 'updateCardFields' | 'updateCardStatus'> {
  const { cards, updateCardFields, updateCardStatus } = useMockDbContext();
  return { cards, updateCardFields, updateCardStatus };
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

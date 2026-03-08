/**
 * Re-export barrel — all consumers continue importing from './data/mock-db'.
 * The actual implementation is now backed by the real API.
 */
export {
  MockDbProvider,
  useMockDb,
  useCardStore,
  useVideos,
  useAddVideo,
  useJobs,
  useJobActions,
  usePipelineStats,
  useApiState,
} from './api-provider';

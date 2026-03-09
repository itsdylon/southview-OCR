import { useState } from 'react';
import { X, RefreshCw, FileText, Filter } from 'lucide-react';
import { DashboardLayout } from '../layouts/dashboard-layout';
import { StatusChip } from '../components/status-chip';
import { useJobs } from '../data/mock-db';
import type { Job, JobType, JobStatus } from '../types/ocr';

export default function JobsPage() {
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [statusFilter, setStatusFilter] = useState<JobStatus | 'all'>('all');
  const [typeFilter, setTypeFilter] = useState<JobType | 'all'>('all');
  
  const jobs = useJobs();
  const filteredJobs = jobs.filter((j) => {
    if (statusFilter !== 'all' && j.status !== statusFilter) return false;
    if (typeFilter !== 'all' && j.jobType !== typeFilter) return false;
    return true;
  });
  
  return (
    <DashboardLayout>
      <div className="p-8 max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 mb-2">Processing Jobs</h1>
            <p className="text-gray-600">
              {filteredJobs.length} jobs • Monitor pipeline processing status
            </p>
          </div>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
          >
            <Filter className="w-5 h-5" />
            Filters
          </button>
        </div>
        
        {/* Filters */}
        {showFilters && (
          <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Status
                </label>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value as JobStatus | 'all')}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="all">All Statuses</option>
                  <option value="queued">Queued</option>
                  <option value="running">Running</option>
                  <option value="completed">Completed</option>
                  <option value="failed">Failed</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Job Type
                </label>
                <select
                  value={typeFilter}
                  onChange={(e) => setTypeFilter(e.target.value as JobType | 'all')}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="all">All Types</option>
                  <option value="frame_extraction">Frame Extraction</option>
                  <option value="ocr">OCR</option>
                  <option value="full_pipeline">Full Pipeline</option>
                </select>
              </div>
            </div>
          </div>
        )}
        
        {/* Jobs Table */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Video</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Job Type</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Status</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Progress</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Created</th>
              </tr>
            </thead>
            <tbody>
              {filteredJobs.map((job) => (
                <tr
                  key={job.id}
                  className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer"
                  onClick={() => setSelectedJob(job)}
                >
                  <td className="px-6 py-4">
                    <p className="font-medium text-gray-900 truncate max-w-xs">{job.videoName}</p>
                    <p className="text-sm text-gray-500">ID: {job.id}</p>
                  </td>
                  <td className="px-6 py-4">
                    <span className="text-sm text-gray-900 capitalize">
                      {job.jobType.replace('_', ' ')}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <StatusChip status={job.status} />
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden max-w-[120px]">
                        <div
                          className="h-full bg-indigo-600 rounded-full transition-all"
                          style={{ width: `${job.progress}%` }}
                        />
                      </div>
                      <span className="text-sm font-medium text-gray-700 w-12 text-right">
                        {job.progress}%
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">
                    {new Date(job.createdAt).toLocaleString('en-US', {
                      month: 'short',
                      day: 'numeric',
                      hour: 'numeric',
                      minute: '2-digit',
                    })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      
      {/* Job Details Drawer */}
      {selectedJob && (
        <div className="fixed inset-y-0 right-0 w-[500px] bg-white border-l border-gray-200 shadow-xl z-50 overflow-y-auto">
          <div className="sticky top-0 bg-white border-b border-gray-200 p-6 flex items-start justify-between">
            <div>
              <h2 className="text-xl font-bold text-gray-900">Job Details</h2>
              <p className="text-sm text-gray-500 mt-1 capitalize">
                {selectedJob.jobType.replace('_', ' ')}
              </p>
            </div>
            <button
              onClick={() => setSelectedJob(null)}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
          
          <div className="p-6 space-y-6">
            {/* Status */}
            <div>
              <p className="text-sm font-medium text-gray-500 mb-2">Status</p>
              <StatusChip status={selectedJob.status} size="md" />
            </div>
            
            {/* Progress */}
            <div>
              <p className="text-sm font-medium text-gray-500 mb-2">Progress</p>
              <div className="flex items-center gap-3 mb-2">
                <div className="flex-1 h-3 bg-gray-200 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-indigo-600 rounded-full"
                    style={{ width: `${selectedJob.progress}%` }}
                  />
                </div>
                <span className="text-sm font-semibold text-gray-900">
                  {selectedJob.progress}%
                </span>
              </div>
            </div>
            
            {/* Video */}
            <div>
              <p className="text-sm font-medium text-gray-500 mb-2">Video</p>
              <p className="text-sm text-gray-900">{selectedJob.videoName}</p>
            </div>
            
            {/* Error Message */}
            {selectedJob.errorMessage && (
              <div>
                <p className="text-sm font-medium text-gray-500 mb-2">Error</p>
                <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                  <p className="text-sm text-red-900">{selectedJob.errorMessage}</p>
                </div>
              </div>
            )}
            
            {/* Timeline */}
            <div>
              <p className="text-sm font-medium text-gray-500 mb-3">Timeline</p>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-600">Created:</span>
                  <span className="text-gray-900 font-medium">
                    {new Date(selectedJob.createdAt).toLocaleString()}
                  </span>
                </div>
                {selectedJob.startedAt && (
                  <div className="flex justify-between">
                    <span className="text-gray-600">Started:</span>
                    <span className="text-gray-900 font-medium">
                      {new Date(selectedJob.startedAt).toLocaleString()}
                    </span>
                  </div>
                )}
                {selectedJob.completedAt && (
                  <div className="flex justify-between">
                    <span className="text-gray-600">Completed:</span>
                    <span className="text-gray-900 font-medium">
                      {new Date(selectedJob.completedAt).toLocaleString()}
                    </span>
                  </div>
                )}
              </div>
            </div>
            
            {/* Actions */}
            <div className="space-y-2 pt-4 border-t border-gray-200">
              {selectedJob.status === 'failed' && (
                <button className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium">
                  <RefreshCw className="w-4 h-4" />
                  Retry Job
                </button>
              )}
              <button className="w-full flex items-center justify-center gap-2 px-4 py-3 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors font-medium">
                <FileText className="w-4 h-4" />
                View Full Logs
              </button>
            </div>
          </div>
        </div>
      )}
      
      {/* Backdrop */}
      {selectedJob && (
        <div
          className="fixed inset-0 bg-black bg-opacity-20 z-40"
          onClick={() => setSelectedJob(null)}
        />
      )}
    </DashboardLayout>
  );
}

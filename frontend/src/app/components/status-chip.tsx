import type { BatchStatus, JobStatus, RecordStatus } from '../types/dashboard';

type StatusType = BatchStatus | JobStatus | RecordStatus;

interface StatusChipProps {
  status: StatusType;
  size?: 'sm' | 'md';
}

const statusConfig: Record<string, { label: string; className: string }> = {
  // Batch statuses
  pending: { label: 'Pending', className: 'bg-gray-100 text-gray-700' },
  queued: { label: 'Queued', className: 'bg-blue-100 text-blue-700' },
  processing: { label: 'Processing', className: 'bg-yellow-100 text-yellow-700' },
  running: { label: 'Running', className: 'bg-yellow-100 text-yellow-700' },
  completed: { label: 'Completed', className: 'bg-green-100 text-green-700' },
  failed: { label: 'Failed', className: 'bg-red-100 text-red-700' },
  
  // Record statuses
  needs_review: { label: 'Needs Review', className: 'bg-orange-100 text-orange-700' },
  in_progress: { label: 'In Progress', className: 'bg-blue-100 text-blue-700' },
  approved: { label: 'Approved', className: 'bg-green-100 text-green-700' },
  follow_up: { label: 'Follow-up', className: 'bg-purple-100 text-purple-700' },
  rejected: { label: 'Rejected', className: 'bg-red-100 text-red-700' },
};

export function StatusChip({ status, size = 'sm' }: StatusChipProps) {
  const config = statusConfig[status] || { label: status, className: 'bg-gray-100 text-gray-700' };
  
  return (
    <span
      className={`inline-flex items-center rounded-full font-medium ${
        size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm'
      } ${config.className}`}
    >
      {config.label}
    </span>
  );
}

import type { ConfidenceBand } from '../types/ocr';
import { getConfidenceBandLabel } from '../types/ocr';

interface ConfidenceBadgeProps {
  score: number;
  band: ConfidenceBand;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
}

const bandConfig: Record<ConfidenceBand, { className: string; bgClass: string }> = {
  'auto-approved': {
    className: 'text-green-700 border-green-300',
    bgClass: 'bg-green-50',
  },
  'pending-review': {
    className: 'text-yellow-700 border-yellow-300',
    bgClass: 'bg-yellow-50',
  },
  'flagged': {
    className: 'text-red-700 border-red-300',
    bgClass: 'bg-red-50',
  },
};

export function ConfidenceBadge({ score, band, size = 'sm', showLabel = false }: ConfidenceBadgeProps) {
  const config = bandConfig[band];
  const percentage = (score * 100).toFixed(0);
  
  const sizeClasses = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-3 py-1 text-sm',
    lg: 'px-4 py-1.5 text-base',
  };
  
  return (
    <div className="inline-flex items-center gap-2">
      <span
        className={`inline-flex items-center rounded-full border font-semibold ${config.className} ${config.bgClass} ${sizeClasses[size]}`}
      >
        {percentage}%
      </span>
      {showLabel && (
        <span className="text-sm text-gray-600">{getConfidenceBandLabel(band)}</span>
      )}
    </div>
  );
}

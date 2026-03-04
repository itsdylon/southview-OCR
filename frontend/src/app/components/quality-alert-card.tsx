import { AlertTriangle, AlertCircle, Info } from 'lucide-react';
import type { QualityAlert } from '../types/dashboard';

interface QualityAlertCardProps {
  alert: QualityAlert;
  onViewDetails?: () => void;
}

const severityConfig = {
  high: {
    icon: AlertTriangle,
    bgColor: 'bg-red-50',
    borderColor: 'border-red-200',
    iconColor: 'text-red-600',
    textColor: 'text-red-900',
  },
  medium: {
    icon: AlertCircle,
    bgColor: 'bg-yellow-50',
    borderColor: 'border-yellow-200',
    iconColor: 'text-yellow-600',
    textColor: 'text-yellow-900',
  },
  low: {
    icon: Info,
    bgColor: 'bg-blue-50',
    borderColor: 'border-blue-200',
    iconColor: 'text-blue-600',
    textColor: 'text-blue-900',
  },
};

export function QualityAlertCard({ alert, onViewDetails }: QualityAlertCardProps) {
  const config = severityConfig[alert.severity];
  const Icon = config.icon;
  
  return (
    <div
      className={`flex items-start gap-3 p-4 rounded-lg border ${config.bgColor} ${config.borderColor}`}
    >
      <Icon className={`w-5 h-5 flex-shrink-0 mt-0.5 ${config.iconColor}`} />
      <div className="flex-1 min-w-0">
        <p className={`text-sm font-medium ${config.textColor}`}>{alert.message}</p>
        {onViewDetails && (
          <button
            onClick={onViewDetails}
            className="text-xs text-blue-600 hover:text-blue-800 mt-1"
          >
            View details →
          </button>
        )}
      </div>
      <span className={`text-sm font-semibold ${config.textColor}`}>
        {alert.affectedCount}
      </span>
    </div>
  );
}

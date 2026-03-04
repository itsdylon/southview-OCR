import { Link } from 'react-router';
import { ArrowRight, AlertTriangle, Video as VideoIcon, Cog } from 'lucide-react';
import { DashboardLayout } from '../layouts/dashboard-layout';
import { StatusChip } from '../components/status-chip';
import { useMockDb } from '../data/mock-db';

export default function OverviewPage() {
  const { pipelineStats: stats, jobs, videos } = useMockDb();
  
  // Determine next best action
  const nextAction = stats.cardsFlagged > 0
    ? {
        message: `${stats.cardsFlagged} flagged cards need immediate review`,
        link: '/review-queue?filter=flagged',
        bgColor: 'bg-red-600',
        hoverColor: 'hover:bg-red-700',
      }
    : stats.cardsPending > 0
    ? {
        message: `${stats.cardsPending} cards pending review`,
        link: '/review-queue?filter=pending',
        bgColor: 'bg-yellow-600',
        hoverColor: 'hover:bg-yellow-700',
      }
    : videos.filter((v) => v.status === 'uploaded').length > 0
    ? {
        message: `${videos.filter((v) => v.status === 'uploaded').length} videos uploaded, not processed`,
        link: '/videos',
        bgColor: 'bg-blue-600',
        hoverColor: 'hover:bg-blue-700',
      }
    : null;
  
  return (
    <DashboardLayout>
      <div className="p-8 max-w-7xl mx-auto">
        {/* Next Best Action Banner */}
        {nextAction && (
          <div className={`${nextAction.bgColor} text-white rounded-xl p-6 mb-8 flex items-center justify-between`}>
            <div className="flex items-center gap-4">
              <AlertTriangle className="w-6 h-6" />
              <div>
                <h2 className="text-xl font-semibold mb-1">Next best action</h2>
                <p className="text-white/90">{nextAction.message}</p>
              </div>
            </div>
            <Link
              to={nextAction.link}
              className={`flex items-center gap-2 bg-white/20 backdrop-blur px-6 py-3 rounded-lg font-semibold ${nextAction.hoverColor} transition-colors`}
            >
              Take action
              <ArrowRight className="w-5 h-5" />
            </Link>
          </div>
        )}
        
        {/* Pipeline Stage Summary */}
        <div className="mb-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Pipeline Status</h2>
          <div className="grid grid-cols-3 gap-4 mb-4">
            <MetricCard
              label="Videos Processing"
              value={stats.videosProcessing}
              color="indigo"
              link="/videos"
              icon={VideoIcon}
            />
            <MetricCard
              label="Jobs Running"
              value={stats.jobsRunning}
              color="blue"
              link="/jobs"
              icon={Cog}
            />
            <MetricCard
              label="Cards Flagged"
              value={stats.cardsFlagged}
              color="red"
              link="/review-queue?filter=flagged"
              icon={AlertTriangle}
              badge="Priority"
            />
          </div>
          <div className="grid grid-cols-3 gap-4">
            <MetricCard
              label="Pending Review"
              value={stats.cardsPending}
              color="yellow"
              sublabel="70-84% confidence"
              link="/review-queue?filter=pending"
            />
            <MetricCard
              label="Auto-approved"
              value={stats.cardsAutoApproved}
              color="green"
              sublabel="≥85% confidence"
            />
            <MetricCard
              label="Approved/Corrected"
              value={stats.cardsApprovedCorrected}
              color="emerald"
              sublabel="Ready for export"
              link="/export"
            />
          </div>
        </div>
        
        {/* Recent Jobs */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-gray-900">Recent Jobs</h2>
            <Link to="/jobs" className="text-sm text-blue-600 hover:text-blue-800">
              View all jobs →
            </Link>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200">
                  <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Video</th>
                  <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Job Type</th>
                  <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Status</th>
                  <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Progress</th>
                  <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Created</th>
                  <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Completed</th>
                </tr>
              </thead>
              <tbody>
                {jobs.slice(0, 5).map((job) => (
                  <tr key={job.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="px-6 py-4">
                      <p className="font-medium text-gray-900 truncate max-w-xs">{job.videoName}</p>
                    </td>
                    <td className="px-6 py-4">
                      <span className="text-sm text-gray-600 capitalize">
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
                            className="h-full bg-blue-600 rounded-full transition-all"
                            style={{ width: `${job.progress}%` }}
                          />
                        </div>
                        <span className="text-sm font-medium text-gray-700 w-10 text-right">
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
                    <td className="px-6 py-4 text-sm text-gray-600">
                      {job.completedAt ? (
                        new Date(job.completedAt).toLocaleString('en-US', {
                          month: 'short',
                          day: 'numeric',
                          hour: 'numeric',
                          minute: '2-digit',
                        })
                      ) : job.errorMessage ? (
                        <span className="text-red-600">Failed</span>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

interface MetricCardProps {
  label: string;
  value: number;
  color: 'indigo' | 'blue' | 'red' | 'yellow' | 'green' | 'emerald';
  sublabel?: string;
  link?: string;
  icon?: React.ComponentType<{ className?: string }>;
  badge?: string;
}

function MetricCard({ label, value, color, sublabel, link, icon: Icon, badge }: MetricCardProps) {
  const colorClasses = {
    indigo: 'bg-indigo-50 border-indigo-200 text-indigo-900',
    blue: 'bg-blue-50 border-blue-200 text-blue-900',
    red: 'bg-red-50 border-red-200 text-red-900',
    yellow: 'bg-yellow-50 border-yellow-200 text-yellow-900',
    green: 'bg-green-50 border-green-200 text-green-900',
    emerald: 'bg-emerald-50 border-emerald-200 text-emerald-900',
  };
  
  const content = (
    <div className={`rounded-xl border p-6 ${colorClasses[color]} ${link ? 'hover:shadow-md transition-shadow cursor-pointer' : ''} relative`}>
      {badge && (
        <span className="absolute top-3 right-3 px-2 py-0.5 bg-red-500 text-white text-xs font-semibold rounded-full">
          {badge}
        </span>
      )}
      <div className="flex items-start gap-4">
        {Icon && (
          <div className="w-10 h-10 bg-white/50 rounded-lg flex items-center justify-center flex-shrink-0">
            <Icon className="w-5 h-5" />
          </div>
        )}
        <div className="flex-1">
          <p className="text-sm font-medium mb-2 opacity-75">{label}</p>
          <p className="text-3xl font-bold">{value}</p>
          {sublabel && <p className="text-xs mt-1 opacity-75">{sublabel}</p>}
        </div>
      </div>
    </div>
  );
  
  return link ? <Link to={link}>{content}</Link> : content;
}
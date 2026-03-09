import { useState } from 'react';
import { toast } from 'sonner';
import { DashboardLayout } from '../layouts/dashboard-layout';

export default function OCRSettingsPage() {
  const [autoApproveThreshold, setAutoApproveThreshold] = useState(85);
  const [pendingReviewThreshold, setPendingReviewThreshold] = useState(70);

  const handleSave = () => {
    toast.success('Settings saved successfully');
  };
  
  return (
    <DashboardLayout>
      <div className="p-8 max-w-4xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Settings</h1>
          <p className="text-gray-600">
            Configure OCR processing and confidence thresholds
          </p>
        </div>
        
        {/* Confidence Thresholds */}
        <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-6">Confidence Thresholds</h2>
          
          <div className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Auto-approve Threshold
              </label>
              <div className="flex items-center gap-4">
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={autoApproveThreshold}
                  onChange={(e) => setAutoApproveThreshold(Number(e.target.value))}
                  className="flex-1"
                />
                <span className="text-sm font-medium text-gray-900 w-16 text-right">
                  {autoApproveThreshold}%
                </span>
              </div>
              <p className="text-xs text-gray-500 mt-2">
                Cards with confidence ≥ {autoApproveThreshold}% will be automatically approved
              </p>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Pending Review Threshold
              </label>
              <div className="flex items-center gap-4">
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={pendingReviewThreshold}
                  onChange={(e) => setPendingReviewThreshold(Number(e.target.value))}
                  className="flex-1"
                />
                <span className="text-sm font-medium text-gray-900 w-16 text-right">
                  {pendingReviewThreshold}%
                </span>
              </div>
              <p className="text-xs text-gray-500 mt-2">
                Cards between {pendingReviewThreshold}% and {autoApproveThreshold}% will be marked for review
              </p>
            </div>
            
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
              <h3 className="text-sm font-semibold text-gray-900 mb-2">Current Configuration</h3>
              <div className="space-y-1 text-sm text-gray-600">
                <p>• <span className="font-medium text-green-700">≥{autoApproveThreshold}%</span> → Auto-approved</p>
                <p>• <span className="font-medium text-yellow-700">{pendingReviewThreshold}–{autoApproveThreshold - 1}%</span> → Pending review</p>
                <p>• <span className="font-medium text-red-700">&lt;{pendingReviewThreshold}%</span> → Flagged (priority review)</p>
              </div>
            </div>
          </div>
        </div>
        
        {/* Actions */}
        <div className="flex justify-end gap-3">
          <button className="px-6 py-3 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors font-medium">
            Reset to Defaults
          </button>
          <button
            onClick={handleSave}
            className="px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-semibold"
          >
            Save Changes
          </button>
        </div>
      </div>
    </DashboardLayout>
  );
}

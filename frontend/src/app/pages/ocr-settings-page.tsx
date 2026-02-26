import { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { toast } from 'sonner';
import { DashboardLayout } from '../layouts/dashboard-layout';

export default function OCRSettingsPage() {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [autoApproveThreshold, setAutoApproveThreshold] = useState(85);
  const [pendingReviewThreshold, setPendingReviewThreshold] = useState(70);
  const [ocrEngine, setOcrEngine] = useState('tesseract');

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
        
        {/* OCR Settings */}
        <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-6">OCR Processing</h2>
          
          <div className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                OCR Engine
              </label>
              <select
                value={ocrEngine}
                onChange={(e) => setOcrEngine(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="tesseract">Tesseract OCR v5.3.0</option>
                <option value="google">Google Cloud Vision API</option>
                <option value="azure">Azure Computer Vision</option>
              </select>
              <p className="text-xs text-gray-500 mt-1">
                Default engine for video processing jobs
              </p>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Processing Options
              </label>
              <div className="space-y-3">
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    defaultChecked
                    className="w-4 h-4 text-indigo-600"
                  />
                  <div>
                    <p className="text-sm text-gray-900">Image preprocessing</p>
                    <p className="text-xs text-gray-500">Apply denoising and contrast enhancement</p>
                  </div>
                </label>
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    defaultChecked
                    className="w-4 h-4 text-indigo-600"
                  />
                  <div>
                    <p className="text-sm text-gray-900">Structured field extraction</p>
                    <p className="text-xs text-gray-500">Attempt to parse fields automatically</p>
                  </div>
                </label>
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    className="w-4 h-4 text-indigo-600"
                  />
                  <div>
                    <p className="text-sm text-gray-900">Handwriting detection</p>
                    <p className="text-xs text-gray-500">Flag cards with handwritten annotations</p>
                  </div>
                </label>
              </div>
            </div>
          </div>
        </div>
        
        {/* Advanced Settings */}
        <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center gap-2 font-semibold text-gray-900 hover:text-gray-700 mb-4"
          >
            Advanced Settings
            {showAdvanced ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
          </button>
          
          {showAdvanced && (
            <div className="space-y-6 border-t border-gray-200 pt-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Frame Extraction Rate
                </label>
                <select className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500">
                  <option value="30">30 FPS (High quality)</option>
                  <option value="15" selected>15 FPS (Balanced)</option>
                  <option value="10">10 FPS (Fast)</option>
                </select>
                <p className="text-xs text-gray-500 mt-1">
                  Higher FPS = more frames = better card detection, but slower processing
                </p>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Duplicate Card Threshold
                </label>
                <input
                  type="number"
                  defaultValue="0.95"
                  step="0.05"
                  min="0.7"
                  max="1.0"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Similarity threshold (0.0-1.0) for detecting duplicate frames
                </p>
              </div>
              
              <div className="flex items-center justify-between pt-4 border-t border-gray-200">
                <div>
                  <p className="font-medium text-gray-900">Debug Logging</p>
                  <p className="text-sm text-gray-500">
                    Save detailed processing logs for troubleshooting
                  </p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input type="checkbox" className="sr-only peer" />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-indigo-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-indigo-600"></div>
                </label>
              </div>
            </div>
          )}
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

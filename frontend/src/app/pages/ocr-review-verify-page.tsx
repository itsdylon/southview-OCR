import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router';
import { toast } from 'sonner';
import {
  ZoomIn,
  ZoomOut,
  RotateCw,
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  Save,
  CheckCircle,
  Flag,
  Edit3,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import * as Accordion from '@radix-ui/react-accordion';
import { DashboardLayout } from '../layouts/dashboard-layout';
import { ConfidenceBadge } from '../components/confidence-badge';
import { useCardStore } from '../data/mock-db';
import { getConfidenceBand } from '../types/ocr';
import type { OCRResult } from '../types/ocr';

export default function OCRReviewVerifyPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { cards, updateCardFields, updateCardStatus } = useCardStore();
  const card = cards.find((c) => c.id === id);

  const [zoom, setZoom] = useState(1);
  const [rotation, setRotation] = useState(0);
  const [formData, setFormData] = useState<Partial<OCRResult>>(card?.ocrResult || {});
  const [showRawOCR, setShowRawOCR] = useState(false);

  // Reset form and viewer state when navigating to a different card
  useEffect(() => {
    const current = cards.find((c) => c.id === id);
    setFormData(current?.ocrResult || {});
    setZoom(1);
    setRotation(0);
    setShowRawOCR(false);
  }, [id, cards]);

  // Build a filtered list of cards that still need review (flagged or pending)
  const reviewQueue = cards.filter(
    (c) => c.ocrResult && (c.ocrResult.reviewStatus === 'flagged' || c.ocrResult.reviewStatus === 'pending')
  );

  if (!card || !card.ocrResult) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-full">
          <p className="text-gray-500">Card not found</p>
        </div>
      </DashboardLayout>
    );
  }

  const currentIndex = reviewQueue.findIndex((c) => c.id === id);
  const hasPrev = currentIndex > 0;
  const hasNext = currentIndex < reviewQueue.length - 1;
  const confidenceBand = getConfidenceBand(card.ocrResult.confidenceScore);

  const saveFields = () => {
    updateCardFields(card.id, formData);
  };

  const handleFieldChange = (field: keyof OCRResult, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleSave = () => {
    saveFields();
    toast.success('Changes saved as draft');
  };

  const navigateNext = () => {
    // After an action (approve/correct/flag), the current card leaves the queue.
    // The card that was at currentIndex+1 is now at currentIndex in the
    // *updated* queue, but we haven't re-rendered yet so we use the stale list.
    // Using currentIndex+1 on the stale list gives us the correct next card.
    if (hasNext) {
      navigate(`/review/${reviewQueue[currentIndex + 1].id}`);
    } else if (currentIndex > 0) {
      // We were on the last queue item — go to the previous one
      navigate(`/review/${reviewQueue[currentIndex - 1].id}`);
    } else {
      navigate('/review-queue');
    }
  };

  const handleApprove = () => {
    saveFields();
    updateCardStatus(card.id, 'approved');
    toast.success('Card approved', { description: card.ocrResult.deceased_name || 'Unknown' });
    navigateNext();
  };

  const handleCorrected = () => {
    saveFields();
    updateCardStatus(card.id, 'corrected');
    toast.success('Marked as corrected', { description: card.ocrResult.deceased_name || 'Unknown' });
    navigateNext();
  };

  const handleFlag = () => {
    saveFields();
    updateCardStatus(card.id, 'flagged');
    toast.warning('Card flagged for priority review');
    navigateNext();
  };
  
  return (
    <DashboardLayout>
      <div className="h-screen flex flex-col">
        {/* Header */}
        <div className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/review-queue')}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <h1 className="font-semibold text-gray-900">
                {card.ocrResult.deceased_name || 'Unknown Decedent'}
              </h1>
              <div className="flex items-center gap-3 mt-1">
                <p className="text-sm text-gray-500">
                  {currentIndex >= 0
                    ? `Card ${currentIndex + 1} of ${reviewQueue.length} in queue`
                    : 'Reviewed'} • Frame #{card.frameNumber}
                </p>
                <ConfidenceBadge
                  score={card.ocrResult.confidenceScore}
                  band={confidenceBand}
                  showLabel
                />
              </div>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1 mr-4">
              <button
                onClick={() => hasPrev && navigate(`/review/${reviewQueue[currentIndex - 1].id}`)}
                disabled={!hasPrev}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                title="Previous (J)"
              >
                <ChevronLeft className="w-5 h-5" />
              </button>
              <button
                onClick={() => hasNext && navigate(`/review/${reviewQueue[currentIndex + 1].id}`)}
                disabled={!hasNext}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                title="Next (K)"
              >
                <ChevronRight className="w-5 h-5" />
              </button>
            </div>
            
            <button
              onClick={handleSave}
              className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
            >
              <Save className="w-4 h-4" />
              Save <span className="text-xs text-gray-500">(S)</span>
            </button>
            <button
              onClick={handleApprove}
              className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
            >
              <CheckCircle className="w-4 h-4" />
              Approve <span className="text-xs opacity-75">(A)</span>
            </button>
            <button
              onClick={handleCorrected}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              <Edit3 className="w-4 h-4" />
              Corrected <span className="text-xs opacity-75">(C)</span>
            </button>
            <button
              onClick={handleFlag}
              className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
            >
              <Flag className="w-4 h-4" />
              Flag <span className="text-xs opacity-75">(F)</span>
            </button>
          </div>
        </div>
        
        {/* Main Content */}
        <div className="flex-1 flex overflow-hidden">
          {/* Left: Image Viewer */}
          <div className="w-1/2 p-6 border-r border-gray-200 flex flex-col">
            {/* Image Controls */}
            <div className="flex items-center gap-2 mb-4">
              <button
                onClick={() => setZoom(Math.max(0.5, zoom - 0.25))}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                title="Zoom Out"
              >
                <ZoomOut className="w-5 h-5" />
              </button>
              <button
                onClick={() => setZoom(Math.min(3, zoom + 0.25))}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                title="Zoom In"
              >
                <ZoomIn className="w-5 h-5" />
              </button>
              <button
                onClick={() => setRotation((rotation + 90) % 360)}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                title="Rotate"
              >
                <RotateCw className="w-5 h-5" />
              </button>
              <span className="ml-2 text-sm text-gray-600">{(zoom * 100).toFixed(0)}%</span>
              <button
                onClick={() => setZoom(1)}
                className="ml-auto text-sm text-indigo-600 hover:text-indigo-800"
              >
                Reset
              </button>
            </div>
            
            {/* Image */}
            <div className="flex-1 bg-gray-100 rounded-lg overflow-auto flex items-center justify-center">
              <img
                src={card.imagePath}
                alt="Card scan"
                style={{
                  transform: `scale(${zoom}) rotate(${rotation}deg)`,
                  transition: 'transform 0.2s ease',
                }}
                className="max-w-full h-auto"
              />
            </div>
          </div>
          
          {/* Right: Form */}
          <div className="w-1/2 overflow-y-auto">
            <div className="p-6">
              {/* Form Sections */}
              <Accordion.Root type="multiple" defaultValue={['header', 'ownership', 'dates', 'details']}>
                {/* Header Section */}
                <AccordionSection value="header" title="Header Information">
                  <FormField
                    label="Deceased Name"
                    value={formData.deceased_name || ''}
                    onChange={(v) => handleFieldChange('deceased_name', v)}
                  />
                  <FormField
                    label="Address"
                    value={formData.address || ''}
                    onChange={(v) => handleFieldChange('address', v)}
                  />
                </AccordionSection>
                
                {/* Ownership Section */}
                <AccordionSection value="ownership" title="Ownership Information">
                  <FormField
                    label="Owner"
                    value={formData.owner || ''}
                    onChange={(v) => handleFieldChange('owner', v)}
                  />
                  <FormField
                    label="Relation"
                    value={formData.relation || ''}
                    onChange={(v) => handleFieldChange('relation', v)}
                  />
                  <FormField
                    label="Phone"
                    value={formData.phone || ''}
                    onChange={(v) => handleFieldChange('phone', v)}
                  />
                </AccordionSection>
                
                {/* Dates Section */}
                <AccordionSection value="dates" title="Dates">
                  <FormField
                    label="Date of Death"
                    value={formData.date_of_death || ''}
                    onChange={(v) => handleFieldChange('date_of_death', v)}
                  />
                  <FormField
                    label="Date of Burial"
                    value={formData.date_of_burial || ''}
                    onChange={(v) => handleFieldChange('date_of_burial', v)}
                  />
                </AccordionSection>
                
                {/* Location Section */}
                <AccordionSection value="location" title="Location / Description">
                  <FormField
                    label="Description"
                    value={formData.description || ''}
                    onChange={(v) => handleFieldChange('description', v)}
                    multiline
                    placeholder="e.g., Section A, Block 12, Lot 45, Grave 3"
                  />
                </AccordionSection>
                
                {/* Details Section */}
                <AccordionSection value="details" title="Additional Details">
                  <div className="grid grid-cols-2 gap-4">
                    <FormField
                      label="Sex"
                      value={formData.sex || ''}
                      onChange={(v) => handleFieldChange('sex', v)}
                    />
                    <FormField
                      label="Age"
                      value={formData.age || ''}
                      onChange={(v) => handleFieldChange('age', v)}
                    />
                  </div>
                  <FormField
                    label="Grave Type"
                    value={formData.grave_type || ''}
                    onChange={(v) => handleFieldChange('grave_type', v)}
                  />
                  <FormField
                    label="Grave Fee"
                    value={formData.grave_fee || ''}
                    onChange={(v) => handleFieldChange('grave_fee', v)}
                  />
                  <FormField
                    label="Undertaker"
                    value={formData.undertaker || ''}
                    onChange={(v) => handleFieldChange('undertaker', v)}
                  />
                  <div className="grid grid-cols-2 gap-4">
                    <FormField
                      label="Board of Health No."
                      value={formData.board_of_health_no || ''}
                      onChange={(v) => handleFieldChange('board_of_health_no', v)}
                    />
                    <FormField
                      label="SVC No."
                      value={formData.svc_no || ''}
                      onChange={(v) => handleFieldChange('svc_no', v)}
                    />
                  </div>
                </AccordionSection>
              </Accordion.Root>
              
              {/* Raw OCR Data */}
              <div className="mt-6 border-t border-gray-200 pt-6">
                <button
                  onClick={() => setShowRawOCR(!showRawOCR)}
                  className="flex items-center gap-2 text-sm font-medium text-gray-700 hover:text-gray-900 mb-4"
                >
                  Raw OCR Data (for audit)
                  {showRawOCR ? (
                    <ChevronUp className="w-4 h-4" />
                  ) : (
                    <ChevronDown className="w-4 h-4" />
                  )}
                </button>
                {showRawOCR && (
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Raw Text
                      </label>
                      <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 text-sm font-mono text-gray-700 whitespace-pre-wrap max-h-32 overflow-y-auto">
                        {card.ocrResult.rawText}
                      </div>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Raw Fields JSON
                      </label>
                      <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 text-sm font-mono text-gray-700 whitespace-pre-wrap max-h-32 overflow-y-auto">
                        {card.ocrResult.rawFieldsJson}
                      </div>
                    </div>
                  </div>
                )}
              </div>
              
              {/* Keyboard Shortcuts Hint */}
              <div className="mt-6 bg-gray-50 border border-gray-200 rounded-lg p-4">
                <p className="text-xs font-semibold text-gray-700 mb-2">Keyboard Shortcuts</p>
                <div className="grid grid-cols-2 gap-2 text-xs text-gray-600">
                  <div><kbd className="px-1 py-0.5 bg-gray-200 rounded">A</kbd> Approve</div>
                  <div><kbd className="px-1 py-0.5 bg-gray-200 rounded">C</kbd> Mark Corrected</div>
                  <div><kbd className="px-1 py-0.5 bg-gray-200 rounded">F</kbd> Flag</div>
                  <div><kbd className="px-1 py-0.5 bg-gray-200 rounded">S</kbd> Save</div>
                  <div><kbd className="px-1 py-0.5 bg-gray-200 rounded">J</kbd> Previous</div>
                  <div><kbd className="px-1 py-0.5 bg-gray-200 rounded">K</kbd> Next</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

interface AccordionSectionProps {
  value: string;
  title: string;
  children: React.ReactNode;
}

function AccordionSection({ value, title, children }: AccordionSectionProps) {
  return (
    <Accordion.Item value={value} className="border-b border-gray-200 last:border-0">
      <Accordion.Header>
        <Accordion.Trigger className="w-full flex items-center justify-between py-4 text-left font-semibold text-gray-900 hover:text-gray-700 transition-colors group">
          {title}
          <ChevronDown className="w-5 h-5 transition-transform duration-200 group-data-[state=open]:rotate-180" />
        </Accordion.Trigger>
      </Accordion.Header>
      <Accordion.Content className="pb-6 space-y-4">
        {children}
      </Accordion.Content>
    </Accordion.Item>
  );
}

interface FormFieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  multiline?: boolean;
  placeholder?: string;
}

function FormField({ label, value, onChange, multiline, placeholder }: FormFieldProps) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1.5">
        {label}
      </label>
      {multiline ? (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          rows={3}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
      ) : (
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
      )}
    </div>
  );
}

import { Check } from 'lucide-react';
import type { PipelineStage } from '../types/dashboard';

interface Step {
  id: PipelineStage;
  label: string;
  count?: number;
}

interface PipelineStepperProps {
  currentStage: PipelineStage;
  stats?: {
    upload: number;
    process: number;
    review: number;
    publish: number;
  };
}

const steps: Step[] = [
  { id: 'upload', label: 'Upload' },
  { id: 'process', label: 'Process' },
  { id: 'review', label: 'Review' },
  { id: 'publish', label: 'Publish' },
];

export function PipelineStepper({ currentStage, stats }: PipelineStepperProps) {
  const currentIndex = steps.findIndex((s) => s.id === currentStage);
  
  return (
    <div className="bg-white border-b border-gray-200 px-8 py-6">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between">
          {steps.map((step, index) => {
            const isActive = step.id === currentStage;
            const isCompleted = index < currentIndex;
            const count = stats?.[step.id];
            
            return (
              <div key={step.id} className="flex items-center flex-1">
                {/* Step */}
                <div className="flex flex-col items-center">
                  <div
                    className={`w-10 h-10 rounded-full flex items-center justify-center border-2 transition-all ${
                      isActive
                        ? 'border-blue-600 bg-blue-50'
                        : isCompleted
                        ? 'border-blue-600 bg-blue-600'
                        : 'border-gray-300 bg-white'
                    }`}
                  >
                    {isCompleted ? (
                      <Check className="w-5 h-5 text-white" />
                    ) : (
                      <span
                        className={`text-sm font-semibold ${
                          isActive ? 'text-blue-600' : 'text-gray-400'
                        }`}
                      >
                        {index + 1}
                      </span>
                    )}
                  </div>
                  <div className="mt-2 text-center">
                    <p
                      className={`text-sm font-medium ${
                        isActive ? 'text-gray-900' : 'text-gray-500'
                      }`}
                    >
                      {step.label}
                    </p>
                    {count !== undefined && count > 0 && (
                      <p className="text-xs text-gray-500 mt-0.5">
                        {count} items
                      </p>
                    )}
                  </div>
                </div>
                
                {/* Connector */}
                {index < steps.length - 1 && (
                  <div className="flex-1 h-0.5 mx-4 mb-8">
                    <div
                      className={`h-full ${
                        index < currentIndex ? 'bg-blue-600' : 'bg-gray-300'
                      }`}
                    />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
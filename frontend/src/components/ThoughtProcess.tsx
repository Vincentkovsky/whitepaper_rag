/**
 * Thought Process Component
 * Collapsible display of agent thinking steps with pulsing indicator
 * Requirements: 3.3
 */

import React, { useState } from 'react';
import type { ThoughtStep } from '../types';

export interface ThoughtProcessProps {
  /** Array of thought steps to display */
  steps: ThoughtStep[];
  /** Whether the component is expanded by default */
  defaultExpanded?: boolean;
  /** Whether the agent is currently thinking (shows pulsing indicator) */
  isThinking?: boolean;
  /** Additional CSS class names */
  className?: string;
}

/**
 * Icon components for different actions
 */
const ActionIcon: React.FC<{ action: string }> = ({ action }) => {
  const actionLower = action.toLowerCase();
  
  if (actionLower.includes('search') || actionLower.includes('retrieve')) {
    return (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
    );
  }
  
  if (actionLower.includes('web') || actionLower.includes('browse')) {
    return (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
      </svg>
    );
  }
  
  if (actionLower.includes('calculate') || actionLower.includes('compute')) {
    return (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
      </svg>
    );
  }
  
  // Default thinking icon
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
    </svg>
  );
};

/**
 * Pulsing indicator for active thinking
 */
const PulsingIndicator: React.FC = () => (
  <span className="relative flex h-3 w-3">
    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
    <span className="relative inline-flex rounded-full h-3 w-3 bg-blue-500"></span>
  </span>
);

/**
 * Single thought step display
 */
interface ThoughtStepItemProps {
  step: ThoughtStep;
  index: number;
  isLast: boolean;
}

const ThoughtStepItem: React.FC<ThoughtStepItemProps> = ({ step, index, isLast }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div 
      className={`relative pl-6 ${!isLast ? 'pb-4' : ''}`}
      data-testid={`thought-step-${index}`}
    >
      {/* Timeline connector */}
      {!isLast && (
        <div className="absolute left-[0.4375rem] top-6 bottom-0 w-0.5 bg-gray-200 dark:bg-gray-700" />
      )}
      
      {/* Step indicator */}
      <div className="absolute left-0 top-1 flex items-center justify-center w-4 h-4 rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400">
        <ActionIcon action={step.action} />
      </div>
      
      {/* Step content */}
      <div className="space-y-2">
        {/* Thought */}
        <p className="text-sm text-gray-700 dark:text-gray-300">
          {step.thought}
        </p>
        
        {/* Action */}
        <button
          type="button"
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors"
        >
          <span className="font-medium text-blue-600 dark:text-blue-400">
            {step.action}
          </span>
          <svg 
            className={`w-3 h-3 transition-transform ${isExpanded ? 'rotate-180' : ''}`} 
            fill="none" 
            stroke="currentColor" 
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
        
        {/* Expanded details */}
        {isExpanded && (
          <div className="mt-2 space-y-2 text-xs">
            {/* Action Input */}
            {step.actionInput !== undefined && step.actionInput !== null && (
              <div className="p-2 bg-gray-50 dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700">
                <div className="font-medium text-gray-500 dark:text-gray-400 mb-1">Input:</div>
                <pre className="text-gray-600 dark:text-gray-300 whitespace-pre-wrap overflow-x-auto">
                  {typeof step.actionInput === 'string' 
                    ? step.actionInput 
                    : JSON.stringify(step.actionInput, null, 2)}
                </pre>
              </div>
            )}
            
            {/* Observation */}
            {step.observation && (
              <div className="p-2 bg-green-50 dark:bg-green-900/20 rounded border border-green-200 dark:border-green-800">
                <div className="font-medium text-green-600 dark:text-green-400 mb-1">Result:</div>
                <p className="text-gray-600 dark:text-gray-300 whitespace-pre-wrap">
                  {step.observation.length > 500 
                    ? `${step.observation.slice(0, 500)}...` 
                    : step.observation}
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

/**
 * Thought Process - Collapsible component showing agent's reasoning steps
 */
export const ThoughtProcess: React.FC<ThoughtProcessProps> = ({
  steps,
  defaultExpanded = false,
  isThinking = false,
  className = '',
}) => {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  if (steps.length === 0 && !isThinking) {
    return null;
  }

  return (
    <div 
      className={`rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 ${className}`}
      data-testid="thought-process"
    >
      {/* Header */}
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-3 text-left hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors rounded-lg"
        aria-expanded={isExpanded}
        aria-controls="thought-process-content"
      >
        <div className="flex items-center gap-2">
          {isThinking && <PulsingIndicator />}
          <svg 
            className="w-4 h-4 text-gray-500 dark:text-gray-400" 
            fill="none" 
            stroke="currentColor" 
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
            {isThinking ? 'Thinking...' : `Thought Process (${steps.length} steps)`}
          </span>
        </div>
        <svg 
          className={`w-4 h-4 text-gray-500 dark:text-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`} 
          fill="none" 
          stroke="currentColor" 
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      
      {/* Content */}
      {isExpanded && (
        <div 
          id="thought-process-content"
          className="px-3 pb-3"
        >
          {steps.map((step, index) => (
            <ThoughtStepItem
              key={index}
              step={step}
              index={index}
              isLast={index === steps.length - 1 && !isThinking}
            />
          ))}
          
          {/* Thinking indicator at the end */}
          {isThinking && (
            <div className="relative pl-6 pt-2">
              <div className="absolute left-[0.4375rem] top-0 bottom-4 w-0.5 bg-gray-200 dark:bg-gray-700" />
              <div className="absolute left-0 top-3 flex items-center justify-center">
                <PulsingIndicator />
              </div>
              <p className="text-sm text-gray-500 dark:text-gray-400 italic">
                Processing...
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ThoughtProcess;

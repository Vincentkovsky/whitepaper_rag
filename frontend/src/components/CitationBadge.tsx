/**
 * Citation Badge Component
 * Clickable citation badge with hover preview
 * Requirements: 3.5
 */

import React, { useState, useRef, useEffect } from 'react';
import type { Citation } from '../types';

export interface CitationBadgeProps {
  /** The citation data */
  citation: Citation;
  /** Callback when the badge is clicked */
  onClick?: (citation: Citation) => void;
  /** Additional CSS class names */
  className?: string;
}

/**
 * Tooltip component for citation preview
 */
interface TooltipProps {
  citation: Citation;
  isVisible: boolean;
  anchorRef: React.RefObject<HTMLButtonElement | null>;
}

const Tooltip: React.FC<TooltipProps> = ({ citation, isVisible, anchorRef }) => {
  const [position, setPosition] = useState({ top: 0, left: 0 });
  const tooltipRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isVisible && anchorRef.current && tooltipRef.current) {
      const anchorRect = anchorRef.current.getBoundingClientRect();
      const tooltipRect = tooltipRef.current.getBoundingClientRect();
      
      // Position above the badge by default
      let top = anchorRect.top - tooltipRect.height - 8;
      let left = anchorRect.left + (anchorRect.width / 2) - (tooltipRect.width / 2);
      
      // Adjust if tooltip would go off screen
      if (top < 0) {
        top = anchorRect.bottom + 8; // Position below instead
      }
      if (left < 0) {
        left = 8;
      }
      if (left + tooltipRect.width > window.innerWidth) {
        left = window.innerWidth - tooltipRect.width - 8;
      }
      
      setPosition({ top, left });
    }
  }, [isVisible, anchorRef]);

  if (!isVisible) return null;

  return (
    <div
      ref={tooltipRef}
      className="fixed z-50 max-w-xs p-3 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 text-sm"
      style={{ top: position.top, left: position.left }}
      role="tooltip"
      data-testid={`citation-tooltip-${citation.index}`}
    >
      <div className="font-medium text-gray-900 dark:text-gray-100 mb-1">
        Citation [{citation.index}]
      </div>
      {citation.textSnippet && (
        <p className="text-gray-600 dark:text-gray-400 text-xs line-clamp-3 mb-2">
          "{citation.textSnippet}"
        </p>
      )}
      <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-500">
        <span className={`inline-flex items-center px-1.5 py-0.5 rounded ${
          citation.sourceType === 'pdf' 
            ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' 
            : 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
        }`}>
          {citation.sourceType === 'pdf' ? 'PDF' : 'Web'}
        </span>
        {citation.page && (
          <span>Page {citation.page}</span>
        )}
      </div>
    </div>
  );
};

/**
 * Citation Badge - A clickable badge that displays a citation number
 * with hover preview showing citation details
 */
export const CitationBadge: React.FC<CitationBadgeProps> = ({
  citation,
  onClick,
  className = '',
}) => {
  const [isHovered, setIsHovered] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const hoverTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleMouseEnter = () => {
    // Delay showing tooltip to avoid flickering
    hoverTimeoutRef.current = setTimeout(() => {
      setIsHovered(true);
    }, 200);
  };

  const handleMouseLeave = () => {
    if (hoverTimeoutRef.current) {
      clearTimeout(hoverTimeoutRef.current);
    }
    setIsHovered(false);
  };

  const handleClick = () => {
    if (onClick) {
      onClick(citation);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleClick();
    }
  };

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (hoverTimeoutRef.current) {
        clearTimeout(hoverTimeoutRef.current);
      }
    };
  }, []);

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        onClick={handleClick}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        onKeyDown={handleKeyDown}
        className={`
          inline-flex items-center justify-center
          min-w-[1.5rem] h-5 px-1.5 mx-0.5
          text-xs font-medium
          text-blue-600 bg-blue-100 
          dark:text-blue-400 dark:bg-blue-900/30
          rounded
          hover:bg-blue-200 dark:hover:bg-blue-900/50
          focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1
          transition-colors cursor-pointer
          ${className}
        `}
        title={`View citation ${citation.index}`}
        aria-label={`Citation ${citation.index}${citation.textSnippet ? `: ${citation.textSnippet.slice(0, 50)}...` : ''}`}
        data-testid={`citation-badge-${citation.index}`}
      >
        {citation.index}
      </button>
      <Tooltip
        citation={citation}
        isVisible={isHovered}
        anchorRef={buttonRef}
      />
    </>
  );
};

export default CitationBadge;

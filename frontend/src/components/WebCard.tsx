/**
 * Web Card Component
 * Displays web search result summaries with links to original URLs
 * Requirements: 8.6
 */

import React from 'react';

export interface WebCardProps {
  /** Title of the web page */
  title?: string;
  /** URL of the web page */
  url: string;
  /** Text snippet/summary from the web page */
  snippet: string;
  /** Text to highlight in the snippet */
  highlightText?: string;
  /** Favicon URL */
  favicon?: string;
  /** Additional CSS class names */
  className?: string;
}

/**
 * Extract domain from URL for display
 */
function extractDomain(url: string): string {
  try {
    const urlObj = new URL(url);
    return urlObj.hostname.replace('www.', '');
  } catch {
    return url;
  }
}

/**
 * Highlight text within a string
 */
function highlightTextInSnippet(text: string, highlight?: string): React.ReactNode {
  if (!highlight || !text) {
    return text;
  }

  const lowerText = text.toLowerCase();
  const lowerHighlight = highlight.toLowerCase();
  const index = lowerText.indexOf(lowerHighlight);

  if (index === -1) {
    return text;
  }

  const before = text.slice(0, index);
  const match = text.slice(index, index + highlight.length);
  const after = text.slice(index + highlight.length);

  return (
    <>
      {before}
      <mark 
        className="bg-yellow-200 dark:bg-yellow-800 px-0.5 rounded"
        data-testid="web-card-highlight"
      >
        {match}
      </mark>
      {after}
    </>
  );
}

/**
 * Globe Icon for web sources
 */
const GlobeIcon: React.FC<{ className?: string }> = ({ className = 'w-4 h-4' }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path 
      strokeLinecap="round" 
      strokeLinejoin="round" 
      strokeWidth={2} 
      d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" 
    />
  </svg>
);

/**
 * External Link Icon
 */
const ExternalLinkIcon: React.FC<{ className?: string }> = ({ className = 'w-4 h-4' }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path 
      strokeLinecap="round" 
      strokeLinejoin="round" 
      strokeWidth={2} 
      d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" 
    />
  </svg>
);

/**
 * Web Card - Displays a web search result in a readable card format
 */
export const WebCard: React.FC<WebCardProps> = ({
  title,
  url,
  snippet,
  highlightText,
  favicon,
  className = '',
}) => {
  const domain = extractDomain(url);
  const displayTitle = title || domain;

  return (
    <div 
      className={`bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden ${className}`}
      data-testid="web-card"
    >
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-700">
        <div className="flex items-center gap-2">
          {/* Favicon or Globe Icon */}
          {favicon ? (
            <img 
              src={favicon} 
              alt="" 
              className="w-4 h-4 rounded"
              onError={(e) => {
                // Replace with globe icon on error
                e.currentTarget.style.display = 'none';
                e.currentTarget.nextElementSibling?.classList.remove('hidden');
              }}
            />
          ) : null}
          <GlobeIcon className={`w-4 h-4 text-gray-400 ${favicon ? 'hidden' : ''}`} />
          
          {/* Domain */}
          <span 
            className="text-xs text-gray-500 dark:text-gray-400 truncate"
            data-testid="web-card-domain"
          >
            {domain}
          </span>
        </div>
        
        {/* Title */}
        <h3 
          className="mt-1 font-medium text-gray-900 dark:text-gray-100 line-clamp-2"
          data-testid="web-card-title"
        >
          {displayTitle}
        </h3>
      </div>

      {/* Snippet */}
      <div className="px-4 py-3">
        <p 
          className="text-sm text-gray-600 dark:text-gray-300 line-clamp-4"
          data-testid="web-card-snippet"
        >
          {highlightTextInSnippet(snippet, highlightText)}
        </p>
      </div>

      {/* Footer with Link */}
      <div className="px-4 py-2 bg-gray-50 dark:bg-gray-900/50 border-t border-gray-100 dark:border-gray-700">
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-sm text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 hover:underline"
          data-testid="web-card-link"
        >
          <span>View source</span>
          <ExternalLinkIcon className="w-3.5 h-3.5" />
        </a>
      </div>
    </div>
  );
};

export default WebCard;

/**
 * Markdown Renderer Component
 * Renders markdown content with support for tables, code blocks, LaTeX, and citations
 * Requirements: 3.6
 */

import React, { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import rehypeHighlight from 'rehype-highlight';
import { parseCitations, type ParsedCitation } from '../utils/citationParser';
import type { Citation } from '../types';

export interface MarkdownRendererProps {
  /** The markdown content to render */
  content: string;
  /** Callback when a citation badge is clicked */
  onCitationClick?: (citation: Citation) => void;
  /** Additional CSS class names */
  className?: string;
  /** Citation metadata to merge with parsed citations */
  citationMetadata?: Map<string, Partial<Citation>>;
}

/**
 * Citation Badge component for inline citations with hover tooltip
 */
interface CitationBadgeInlineProps {
  citation: ParsedCitation;
  onClick?: (citation: Citation) => void;
  metadata?: Partial<Citation>;
}

const CitationBadgeInline: React.FC<CitationBadgeInlineProps> = ({
  citation,
  onClick,
  metadata
}) => {
  const [showTooltip, setShowTooltip] = React.useState(false);

  const handleClick = () => {
    // If URL available, open in new tab
    if (metadata?.url) {
      window.open(metadata.url, '_blank', 'noopener,noreferrer');
      return;
    }
    // Otherwise trigger callback
    if (onClick) {
      const fullCitation: Citation = {
        index: citation.index,
        documentId: citation.documentId,
        chunkId: citation.chunkId,
        text: metadata?.text ?? '',
        textSnippet: metadata?.textSnippet ?? '',
        sourceType: metadata?.sourceType ?? 'pdf',
        page: metadata?.page,
        highlightCoords: metadata?.highlightCoords,
        url: metadata?.url,
      };
      onClick(fullCitation);
    }
  };

  return (
    <span className="relative inline-block">
      <button
        type="button"
        onClick={handleClick}
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        className="inline-flex items-center justify-center min-w-[1.5rem] h-5 px-1.5 mx-0.5 text-xs font-medium text-blue-600 bg-blue-100 rounded hover:bg-blue-200 dark:text-blue-400 dark:bg-blue-900/30 dark:hover:bg-blue-900/50 transition-colors cursor-pointer"
        data-testid={`citation-badge-${citation.index}`}
      >
        {citation.index}
      </button>

      {/* Tooltip */}
      {showTooltip && metadata && (
        <div
          className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 w-72 p-3 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 text-left"
          onMouseEnter={() => setShowTooltip(true)}
          onMouseLeave={() => setShowTooltip(false)}
        >
          {/* Arrow */}
          <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-px">
            <div className="border-8 border-transparent border-t-white dark:border-t-gray-800" />
          </div>

          {/* Title */}
          {metadata.title && (
            <p className="text-sm font-medium text-gray-900 dark:text-gray-100 mb-1 line-clamp-2">
              {metadata.title}
            </p>
          )}

          {/* URL */}
          {metadata.url && (
            <a
              href={metadata.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-blue-500 hover:underline mb-2 block truncate"
              onClick={(e) => e.stopPropagation()}
            >
              {metadata.url}
            </a>
          )}

          {/* Snippet */}
          {metadata.textSnippet && (
            <p className="text-xs text-gray-600 dark:text-gray-400 line-clamp-3">
              {metadata.textSnippet}
            </p>
          )}

          {/* Source type indicator */}
          <div className="mt-2 flex items-center gap-1">
            <span className={`text-[10px] px-1.5 py-0.5 rounded ${metadata.sourceType === 'web'
              ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
              : 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400'
              }`}>
              {metadata.sourceType === 'web' ? '🌐 Web' : '📄 PDF'}
            </span>
            {metadata.page && (
              <span className="text-[10px] text-gray-500">Page {metadata.page}</span>
            )}
          </div>
        </div>
      )}
    </span>
  );
};

/**
 * Renders markdown content with citation support
 */
export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({
  content,
  onCitationClick,
  className = '',
  citationMetadata,
}) => {
  // Parse citations and get processed text
  const { processedContent, citations } = useMemo(() => {
    // Pre-process content to escape dollar signs used for currency (e.g., $100)
    // to prevent remark-math from interpreting them as LaTeX delimiters.
    // We only escape $ if it's followed by a digit.
    const escapedContent = content.replace(/\$(\d)/g, '\\$$1');

    const result = parseCitations(escapedContent);
    return {
      processedContent: result.processedText,
      citations: result.citations,
    };
  }, [content]);

  // Create a map of citation index to citation data
  const citationMap = useMemo(() => {
    const map = new Map<number, ParsedCitation>();
    for (const citation of citations) {
      if (!map.has(citation.index)) {
        map.set(citation.index, citation);
      }
    }
    return map;
  }, [citations]);

  // Custom component to render citation badges within text
  const renderWithCitations = useMemo(() => {
    return (text: string): React.ReactNode[] => {
      const parts: React.ReactNode[] = [];
      const badgeRegex = /\[(\d+)\]/g;
      let lastIndex = 0;
      let match: RegExpExecArray | null;

      while ((match = badgeRegex.exec(text)) !== null) {
        // Add text before the badge
        if (match.index > lastIndex) {
          parts.push(text.slice(lastIndex, match.index));
        }

        const badgeIndex = parseInt(match[1], 10);
        const citation = citationMap.get(badgeIndex);

        if (citation) {
          const key = `${citation.documentId}:${citation.chunkId}`;
          const metadata = citationMetadata?.get(key);
          parts.push(
            <CitationBadgeInline
              key={`citation-${match.index}-${badgeIndex}`}
              citation={citation}
              onClick={onCitationClick}
              metadata={metadata}
            />
          );
        } else {
          // Keep original text if no citation found
          parts.push(match[0]);
        }

        lastIndex = match.index + match[0].length;
      }

      // Add remaining text
      if (lastIndex < text.length) {
        parts.push(text.slice(lastIndex));
      }

      return parts;
    };
  }, [citationMap, citationMetadata, onCitationClick]);

  // Custom components for ReactMarkdown
  const components = useMemo(() => ({
    // Render paragraphs with citation support
    p: ({ children }: { children?: React.ReactNode }) => {
      const processedChildren = React.Children.map(children, (child) => {
        if (typeof child === 'string') {
          return renderWithCitations(child);
        }
        return child;
      });
      return <p className="mb-4 last:mb-0">{processedChildren}</p>;
    },
    // Render inline text with citation support
    text: ({ children }: { children?: React.ReactNode }) => {
      if (typeof children === 'string') {
        return <>{renderWithCitations(children)}</>;
      }
      return <>{children}</>;
    },
    // Table styling
    table: ({ children }: { children?: React.ReactNode }) => (
      <div className="overflow-x-auto my-4">
        <table className="min-w-full border-collapse border border-gray-300 dark:border-gray-600">
          {children}
        </table>
      </div>
    ),
    thead: ({ children }: { children?: React.ReactNode }) => (
      <thead className="bg-gray-100 dark:bg-gray-700">{children}</thead>
    ),
    th: ({ children }: { children?: React.ReactNode }) => (
      <th className="border border-gray-300 dark:border-gray-600 px-4 py-2 text-left font-semibold">
        {children}
      </th>
    ),
    td: ({ children }: { children?: React.ReactNode }) => (
      <td className="border border-gray-300 dark:border-gray-600 px-4 py-2">
        {children}
      </td>
    ),
    // Code block styling
    pre: ({ children }: { children?: React.ReactNode }) => (
      <pre className="my-4 p-4 bg-gray-900 dark:bg-gray-950 rounded-lg overflow-x-auto text-sm">
        {children}
      </pre>
    ),
    code: ({ className, children, ...props }: { className?: string; children?: React.ReactNode }) => {
      const isInline = !className;
      if (isInline) {
        return (
          <code className="px-1.5 py-0.5 bg-gray-100 dark:bg-gray-800 rounded text-sm font-mono" {...props}>
            {children}
          </code>
        );
      }
      return (
        <code className={`${className} text-gray-100`} {...props}>
          {children}
        </code>
      );
    },
    // List styling
    ul: ({ children }: { children?: React.ReactNode }) => (
      <ul className="list-disc list-inside mb-4 space-y-1">{children}</ul>
    ),
    ol: ({ children }: { children?: React.ReactNode }) => (
      <ol className="list-decimal list-inside mb-4 space-y-1">{children}</ol>
    ),
    li: ({ children }: { children?: React.ReactNode }) => {
      const processedChildren = React.Children.map(children, (child) => {
        if (typeof child === 'string') {
          return renderWithCitations(child);
        }
        return child;
      });
      return <li className="ml-2">{processedChildren}</li>;
    },
    // Heading styling
    h1: ({ children }: { children?: React.ReactNode }) => (
      <h1 className="text-2xl font-bold mb-4 mt-6 first:mt-0">{children}</h1>
    ),
    h2: ({ children }: { children?: React.ReactNode }) => (
      <h2 className="text-xl font-bold mb-3 mt-5 first:mt-0">{children}</h2>
    ),
    h3: ({ children }: { children?: React.ReactNode }) => (
      <h3 className="text-lg font-semibold mb-2 mt-4 first:mt-0">{children}</h3>
    ),
    // Blockquote styling
    blockquote: ({ children }: { children?: React.ReactNode }) => (
      <blockquote className="border-l-4 border-gray-300 dark:border-gray-600 pl-4 my-4 italic text-gray-600 dark:text-gray-400">
        {children}
      </blockquote>
    ),
    // Link styling
    a: ({ href, children }: { href?: string; children?: React.ReactNode }) => (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="text-blue-600 dark:text-blue-400 hover:underline"
      >
        {children}
      </a>
    ),
    // Horizontal rule
    hr: () => <hr className="my-6 border-gray-300 dark:border-gray-600" />,
  }), [renderWithCitations]);

  return (
    <div
      className={`markdown-content prose prose-sm dark:prose-invert max-w-none ${className}`}
      data-testid="markdown-renderer"
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex, rehypeHighlight]}
        components={components}
      >
        {processedContent}
      </ReactMarkdown>
    </div>
  );
};

export default MarkdownRenderer;

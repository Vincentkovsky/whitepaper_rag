/**
 * PDF Viewer Component
 * Displays PDF documents with page navigation, zoom, and text highlighting
 * Requirements: 8.5
 */

import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as pdfjsLib from 'pdfjs-dist';

// Set up the worker
pdfjsLib.GlobalWorkerOptions.workerSrc = `//cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjsLib.version}/pdf.worker.min.js`;

export interface PDFViewerProps {
  /** URL or base64 data of the PDF document */
  src: string;
  /** Page number to display (1-indexed) */
  page?: number;
  /** Text to highlight on the page */
  highlightText?: string;
  /** Highlight coordinates (quadrilaterals) for precise highlighting */
  highlightCoords?: number[][];
  /** Callback when page changes */
  onPageChange?: (page: number) => void;
  /** Callback when total pages is determined */
  onTotalPagesChange?: (totalPages: number) => void;
  /** Additional CSS class names */
  className?: string;
}

/**
 * Zoom levels available
 */
const ZOOM_LEVELS = [0.5, 0.75, 1, 1.25, 1.5, 2];
const DEFAULT_ZOOM_INDEX = 2; // 100%

/**
 * PDF Viewer - Renders PDF documents with navigation and highlighting
 */
export const PDFViewer: React.FC<PDFViewerProps> = ({
  src,
  page = 1,
  highlightText,
  highlightCoords,
  onPageChange,
  onTotalPagesChange,
  className = '',
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const textLayerRef = useRef<HTMLDivElement>(null);
  const highlightLayerRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const [pdfDoc, setPdfDoc] = useState<pdfjsLib.PDFDocumentProxy | null>(null);
  const [currentPage, setCurrentPage] = useState(page);
  const [totalPages, setTotalPages] = useState(0);
  const [zoomIndex, setZoomIndex] = useState(DEFAULT_ZOOM_INDEX);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewport, setViewport] = useState<pdfjsLib.PageViewport | null>(null);

  const scale = ZOOM_LEVELS[zoomIndex];

  // Load PDF document
  useEffect(() => {
    let cancelled = false;

    const loadPdf = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const loadingTask = pdfjsLib.getDocument(src);
        const pdf = await loadingTask.promise;

        if (cancelled) return;

        setPdfDoc(pdf);
        setTotalPages(pdf.numPages);
        onTotalPagesChange?.(pdf.numPages);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Failed to load PDF');
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    loadPdf();

    return () => {
      cancelled = true;
    };
  }, [src, onTotalPagesChange]);

  // Update current page when prop changes
  useEffect(() => {
    if (page !== currentPage && page >= 1 && page <= totalPages) {
      setCurrentPage(page);
    }
  }, [page, totalPages]);

  // Render current page
  useEffect(() => {
    if (!pdfDoc || !canvasRef.current) return;

    let cancelled = false;

    const renderPage = async () => {
      try {
        const pdfPage = await pdfDoc.getPage(currentPage);

        if (cancelled) return;

        const pageViewport = pdfPage.getViewport({ scale });
        setViewport(pageViewport);

        const canvas = canvasRef.current!;
        const context = canvas.getContext('2d')!;

        canvas.height = pageViewport.height;
        canvas.width = pageViewport.width;

        const renderContext = {
          canvasContext: context,
          viewport: pageViewport,
          canvas,
        };

        await pdfPage.render(renderContext as any).promise;

        // Render text layer for text selection and highlighting
        if (textLayerRef.current) {
          textLayerRef.current.innerHTML = '';
          textLayerRef.current.style.width = `${pageViewport.width}px`;
          textLayerRef.current.style.height = `${pageViewport.height}px`;

          const textContent = await pdfPage.getTextContent();

          if (cancelled) return;

          // Render text items
          for (const item of textContent.items) {
            if ('str' in item && item.str) {
              const textItem = item as any;
              const tx = pdfjsLib.Util.transform(
                pageViewport.transform,
                textItem.transform
              );

              const div = document.createElement('span');
              div.textContent = textItem.str;
              div.style.position = 'absolute';
              div.style.left = `${tx[4]}px`;
              div.style.top = `${pageViewport.height - tx[5]}px`;
              div.style.fontSize = `${Math.abs(tx[0])}px`;
              div.style.fontFamily = 'sans-serif';
              div.style.color = 'transparent';
              div.style.whiteSpace = 'pre';
              div.style.pointerEvents = 'all';
              div.style.userSelect = 'text';

              textLayerRef.current?.appendChild(div);
            }
          }
        }

        // Apply highlights
        applyHighlights(pageViewport);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to render page');
        }
      }
    };

    renderPage();

    return () => {
      cancelled = true;
    };
  }, [pdfDoc, currentPage, scale]);

  // Apply text highlighting
  const applyHighlights = useCallback((pageViewport: pdfjsLib.PageViewport) => {
    if (!highlightLayerRef.current) return;

    highlightLayerRef.current.innerHTML = '';
    highlightLayerRef.current.style.width = `${pageViewport.width}px`;
    highlightLayerRef.current.style.height = `${pageViewport.height}px`;

    // Highlight using coordinates if provided
    if (highlightCoords && highlightCoords.length > 0) {
      for (const coords of highlightCoords) {
        if (coords.length >= 4) {
          const [x1, y1, x2, y2] = coords;
          const highlight = document.createElement('div');
          highlight.className = 'pdf-highlight';
          highlight.style.position = 'absolute';
          highlight.style.left = `${x1 * scale}px`;
          highlight.style.top = `${(pageViewport.height / scale - y2) * scale}px`;
          highlight.style.width = `${(x2 - x1) * scale}px`;
          highlight.style.height = `${(y2 - y1) * scale}px`;
          highlight.style.backgroundColor = 'rgba(255, 255, 0, 0.4)';
          highlight.style.pointerEvents = 'none';
          highlight.setAttribute('data-testid', 'pdf-highlight');
          highlightLayerRef.current.appendChild(highlight);
        }
      }
    }

    // Highlight text if provided (fallback text search)
    if (highlightText && textLayerRef.current) {
      const textSpans = textLayerRef.current.querySelectorAll('span');
      textSpans.forEach((span) => {
        if (span.textContent?.toLowerCase().includes(highlightText.toLowerCase())) {
          const rect = span.getBoundingClientRect();
          const containerRect = highlightLayerRef.current!.getBoundingClientRect();

          const highlight = document.createElement('div');
          highlight.className = 'pdf-highlight pdf-highlight-text';
          highlight.style.position = 'absolute';
          highlight.style.left = `${rect.left - containerRect.left}px`;
          highlight.style.top = `${rect.top - containerRect.top}px`;
          highlight.style.width = `${rect.width}px`;
          highlight.style.height = `${rect.height}px`;
          highlight.style.backgroundColor = 'rgba(255, 255, 0, 0.4)';
          highlight.style.pointerEvents = 'none';
          highlight.setAttribute('data-testid', 'pdf-highlight-text');
          highlightLayerRef.current?.appendChild(highlight);
        }
      });
    }
  }, [highlightCoords, highlightText, scale]);

  // Re-apply highlights when they change
  useEffect(() => {
    if (viewport) {
      applyHighlights(viewport);
    }
  }, [highlightText, highlightCoords, viewport, applyHighlights]);

  // Navigation handlers
  const goToPage = useCallback((pageNum: number) => {
    if (pageNum >= 1 && pageNum <= totalPages) {
      setCurrentPage(pageNum);
      onPageChange?.(pageNum);
    }
  }, [totalPages, onPageChange]);

  const goToPrevPage = useCallback(() => {
    goToPage(currentPage - 1);
  }, [currentPage, goToPage]);

  const goToNextPage = useCallback(() => {
    goToPage(currentPage + 1);
  }, [currentPage, goToPage]);

  // Zoom handlers
  const zoomIn = useCallback(() => {
    if (zoomIndex < ZOOM_LEVELS.length - 1) {
      setZoomIndex(zoomIndex + 1);
    }
  }, [zoomIndex]);

  const zoomOut = useCallback(() => {
    if (zoomIndex > 0) {
      setZoomIndex(zoomIndex - 1);
    }
  }, [zoomIndex]);

  if (error) {
    return (
      <div
        className={`flex items-center justify-center p-8 bg-gray-100 dark:bg-gray-800 rounded-lg ${className}`}
        data-testid="pdf-viewer-error"
      >
        <div className="text-center">
          <svg className="w-12 h-12 mx-auto text-red-500 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <p className="text-red-600 dark:text-red-400">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`flex flex-col bg-gray-100 dark:bg-gray-900 rounded-lg overflow-hidden ${className}`}
      data-testid="pdf-viewer"
    >
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
        {/* Page Navigation */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={goToPrevPage}
            disabled={currentPage <= 1 || isLoading}
            className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
            aria-label="Previous page"
            data-testid="pdf-prev-page"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>

          <span className="text-sm text-gray-600 dark:text-gray-400" data-testid="pdf-page-info">
            {currentPage} / {totalPages}
          </span>

          <button
            type="button"
            onClick={goToNextPage}
            disabled={currentPage >= totalPages || isLoading}
            className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
            aria-label="Next page"
            data-testid="pdf-next-page"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>

        {/* Zoom Controls */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={zoomOut}
            disabled={zoomIndex <= 0 || isLoading}
            className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
            aria-label="Zoom out"
            data-testid="pdf-zoom-out"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM13 10H7" />
            </svg>
          </button>

          <span className="text-sm text-gray-600 dark:text-gray-400 min-w-[4rem] text-center" data-testid="pdf-zoom-level">
            {Math.round(scale * 100)}%
          </span>

          <button
            type="button"
            onClick={zoomIn}
            disabled={zoomIndex >= ZOOM_LEVELS.length - 1 || isLoading}
            className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
            aria-label="Zoom in"
            data-testid="pdf-zoom-in"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v6m3-3H7" />
            </svg>
          </button>
        </div>
      </div>

      {/* PDF Content */}
      <div
        ref={containerRef}
        className="flex-1 overflow-auto p-4 flex justify-center"
        data-testid="pdf-content-container"
      >
        {isLoading ? (
          <div className="flex items-center justify-center h-64" data-testid="pdf-loading">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          </div>
        ) : (
          <div className="relative inline-block shadow-lg">
            <canvas
              ref={canvasRef}
              className="block"
              data-testid="pdf-canvas"
            />
            <div
              ref={textLayerRef}
              className="absolute top-0 left-0 overflow-hidden"
              style={{ mixBlendMode: 'multiply' }}
              data-testid="pdf-text-layer"
            />
            <div
              ref={highlightLayerRef}
              className="absolute top-0 left-0 overflow-hidden pointer-events-none"
              data-testid="pdf-highlight-layer"
            />
          </div>
        )}
      </div>
    </div>
  );
};

export default PDFViewer;

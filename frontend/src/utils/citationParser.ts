/**
 * Citation Parser Utility
 * Parses citation markers from text content
 * Requirements: 3.5
 */

import type { Citation } from '../types';

/**
 * Regular expression to match citation markers in the format:
 * [[citation:doc_id:chunk_id]]
 * 
 * Groups:
 * 1. documentId - the document identifier
 * 2. chunkId - the chunk identifier within the document
 */
const CITATION_REGEX = /\[\[citation:([^:\]]+):([^\]]+)\]\]/g;

/**
 * Represents a parsed citation marker with its position in the text
 */
export interface ParsedCitation {
  /** The full matched string including brackets */
  fullMatch: string;
  /** Document ID extracted from the citation */
  documentId: string;
  /** Chunk ID extracted from the citation */
  chunkId: string;
  /** Start index of the citation in the original text */
  startIndex: number;
  /** End index of the citation in the original text */
  endIndex: number;
  /** The assigned index (1-based) for display */
  index: number;
}

/**
 * Result of parsing citations from text
 */
export interface CitationParseResult {
  /** Array of parsed citations found in the text */
  citations: ParsedCitation[];
  /** Text with citation markers replaced by badge placeholders [1], [2], etc. */
  processedText: string;
}

/**
 * Parses citation markers from text content.
 * 
 * Citation format: [[citation:doc_id:chunk_id]]
 * 
 * @param text - The text content containing citation markers
 * @returns CitationParseResult with parsed citations and processed text
 * 
 * @example
 * const result = parseCitations("See [[citation:doc1:chunk1]] for details.");
 * // result.citations = [{ documentId: 'doc1', chunkId: 'chunk1', index: 1, ... }]
 * // result.processedText = "See [1] for details."
 */
export function parseCitations(text: string): CitationParseResult {
  const citations: ParsedCitation[] = [];
  let processedText = text;
  
  // Track unique citations to assign consistent indices
  const citationMap = new Map<string, number>();
  
  // Find all citation matches
  let match: RegExpExecArray | null;
  const regex = new RegExp(CITATION_REGEX.source, 'g');
  
  while ((match = regex.exec(text)) !== null) {
    const fullMatch = match[0];
    const documentId = match[1];
    const chunkId = match[2];
    const key = `${documentId}:${chunkId}`;
    
    // Assign index - reuse if same citation appears multiple times
    let index: number;
    if (citationMap.has(key)) {
      index = citationMap.get(key)!;
    } else {
      index = citationMap.size + 1;
      citationMap.set(key, index);
    }
    
    citations.push({
      fullMatch,
      documentId,
      chunkId,
      startIndex: match.index,
      endIndex: match.index + fullMatch.length,
      index,
    });
  }
  
  // Replace citation markers with badge placeholders [1], [2], etc.
  // Process in reverse order to maintain correct indices
  const sortedCitations = [...citations].sort((a, b) => b.startIndex - a.startIndex);
  for (const citation of sortedCitations) {
    processedText = 
      processedText.slice(0, citation.startIndex) + 
      `[${citation.index}]` + 
      processedText.slice(citation.endIndex);
  }
  
  return { citations, processedText };
}

/**
 * Converts parsed citations to full Citation objects.
 * This is useful when you need to create Citation objects with additional metadata.
 * 
 * @param parsedCitations - Array of parsed citations from parseCitations()
 * @param metadata - Optional metadata to merge into each citation
 * @returns Array of Citation objects
 */
export function toCitationObjects(
  parsedCitations: ParsedCitation[],
  metadata?: Partial<Omit<Citation, 'index' | 'documentId' | 'chunkId'>>
): Citation[] {
  // Deduplicate by documentId:chunkId, keeping first occurrence
  const seen = new Set<string>();
  const uniqueCitations: ParsedCitation[] = [];
  
  for (const parsed of parsedCitations) {
    const key = `${parsed.documentId}:${parsed.chunkId}`;
    if (!seen.has(key)) {
      seen.add(key);
      uniqueCitations.push(parsed);
    }
  }
  
  return uniqueCitations.map((parsed) => ({
    index: parsed.index,
    documentId: parsed.documentId,
    chunkId: parsed.chunkId,
    text: metadata?.text ?? '',
    textSnippet: metadata?.textSnippet ?? '',
    sourceType: metadata?.sourceType ?? 'pdf',
    page: metadata?.page,
    highlightCoords: metadata?.highlightCoords,
    url: metadata?.url,
  }));
}

/**
 * Checks if a string contains any citation markers.
 * 
 * @param text - The text to check
 * @returns true if the text contains citation markers
 */
export function hasCitations(text: string): boolean {
  return CITATION_REGEX.test(text);
}

/**
 * Counts the number of unique citations in a text.
 * 
 * @param text - The text to analyze
 * @returns Number of unique citations
 */
export function countUniqueCitations(text: string): number {
  const { citations } = parseCitations(text);
  const uniqueKeys = new Set(citations.map(c => `${c.documentId}:${c.chunkId}`));
  return uniqueKeys.size;
}

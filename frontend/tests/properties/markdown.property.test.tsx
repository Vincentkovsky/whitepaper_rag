/**
 * Property-Based Tests for Markdown Rendering
 * **Feature: frontend-redesign, Property 6: Markdown rendering**
 * **Validates: Requirements 3.6**
 *
 * Property: For any markdown string containing tables, code blocks, or LaTeX,
 * the rendered output should contain the corresponding HTML elements.
 */

import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { render, screen } from '@testing-library/react';
import { MarkdownRenderer } from '../../src/components/MarkdownRenderer';

// Generator for table content (simple cells without special characters)
const tableCellArbitrary = fc.stringMatching(/^[a-zA-Z0-9 ]{1,20}$/);

// Generator for markdown tables
const markdownTableArbitrary = fc.tuple(
  fc.array(tableCellArbitrary, { minLength: 2, maxLength: 4 }), // headers
  fc.array(
    fc.array(tableCellArbitrary, { minLength: 2, maxLength: 4 }),
    { minLength: 1, maxLength: 3 }
  ) // rows
).map(([headers, rows]) => {
  const headerRow = `| ${headers.join(' | ')} |`;
  const separator = `| ${headers.map(() => '---').join(' | ')} |`;
  const dataRows = rows.map(row => {
    // Ensure row has same number of cells as headers
    const paddedRow = [...row];
    while (paddedRow.length < headers.length) {
      paddedRow.push('');
    }
    return `| ${paddedRow.slice(0, headers.length).join(' | ')} |`;
  });
  return {
    markdown: [headerRow, separator, ...dataRows].join('\n'),
    headers,
    rowCount: rows.length,
  };
});

// Generator for code blocks
const codeLanguageArbitrary = fc.constantFrom('javascript', 'typescript', 'python', 'json', 'bash');
const codeContentArbitrary = fc.stringMatching(/^[a-zA-Z0-9_\s=(){}[\];:'",.]+$/).filter(s => s.length > 0 && s.length < 100);

const codeBlockArbitrary = fc.tuple(codeLanguageArbitrary, codeContentArbitrary)
  .map(([language, code]) => ({
    markdown: `\`\`\`${language}\n${code}\n\`\`\``,
    language,
    code,
  }));

// Generator for inline code
const inlineCodeArbitrary = fc.stringMatching(/^[a-zA-Z0-9_]+$/).filter(s => s.length > 0 && s.length < 30)
  .map(code => ({
    markdown: `This is \`${code}\` inline code.`,
    code,
  }));

// Generator for LaTeX math (simple expressions)
const latexExpressionArbitrary = fc.constantFrom(
  'x^2',
  'a + b',
  '\\frac{1}{2}',
  '\\sqrt{x}',
  'E = mc^2',
  '\\sum_{i=1}^{n} i',
  '\\int_0^1 x dx'
);

const latexBlockArbitrary = latexExpressionArbitrary.map(expr => ({
  markdown: `$$${expr}$$`,
  expression: expr,
}));

const latexInlineArbitrary = latexExpressionArbitrary.map(expr => ({
  markdown: `The formula is $${expr}$ here.`,
  expression: expr,
}));

// Generator for headings (text without leading/trailing spaces since markdown trims them)
const headingLevelArbitrary = fc.integer({ min: 1, max: 3 });
const headingTextArbitrary = fc.stringMatching(/^[a-zA-Z0-9][a-zA-Z0-9 ]*[a-zA-Z0-9]$/)
  .filter(s => s.length >= 2 && s.length <= 30);

const headingArbitrary = fc.tuple(headingLevelArbitrary, headingTextArbitrary)
  .map(([level, text]) => ({
    markdown: `${'#'.repeat(level)} ${text}`,
    level,
    text: text.trim(), // Markdown trims heading text
  }));

// Generator for lists
const listItemArbitrary = fc.stringMatching(/^[a-zA-Z0-9 ]{1,30}$/);

const unorderedListArbitrary = fc.array(listItemArbitrary, { minLength: 1, maxLength: 5 })
  .map(items => ({
    markdown: items.map(item => `- ${item}`).join('\n'),
    items,
  }));

const orderedListArbitrary = fc.array(listItemArbitrary, { minLength: 1, maxLength: 5 })
  .map(items => ({
    markdown: items.map((item, i) => `${i + 1}. ${item}`).join('\n'),
    items,
  }));

describe('Markdown Rendering Property Tests', () => {
  /**
   * **Feature: frontend-redesign, Property 6: Markdown rendering**
   * **Validates: Requirements 3.6**
   *
   * For any markdown table, the rendered output should contain a table element
   * with the correct number of header cells and rows.
   */
  it('renders tables with correct structure', () => {
    fc.assert(
      fc.property(markdownTableArbitrary, ({ markdown, headers, rowCount }) => {
        const { container } = render(<MarkdownRenderer content={markdown} />);
        
        // Should contain a table element
        const table = container.querySelector('table');
        expect(table).not.toBeNull();
        
        // Should have correct number of header cells
        const headerCells = container.querySelectorAll('th');
        expect(headerCells.length).toBe(headers.length);
        
        // Should have correct number of data rows
        const dataRows = container.querySelectorAll('tbody tr');
        expect(dataRows.length).toBe(rowCount);
      }),
      { numRuns: 50 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 6: Markdown rendering**
   * **Validates: Requirements 3.6**
   *
   * For any code block, the rendered output should contain a pre element
   * with the code content.
   */
  it('renders code blocks with pre element', () => {
    fc.assert(
      fc.property(codeBlockArbitrary, ({ markdown, code }) => {
        const { container } = render(<MarkdownRenderer content={markdown} />);
        
        // Should contain a pre element
        const preElement = container.querySelector('pre');
        expect(preElement).not.toBeNull();
        
        // Should contain a code element
        const codeElement = container.querySelector('code');
        expect(codeElement).not.toBeNull();
        
        // Code content should be present
        expect(preElement?.textContent).toContain(code.trim());
      }),
      { numRuns: 50 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 6: Markdown rendering**
   * **Validates: Requirements 3.6**
   *
   * For any inline code, the rendered output should contain a code element
   * without a pre wrapper.
   */
  it('renders inline code correctly', () => {
    fc.assert(
      fc.property(inlineCodeArbitrary, ({ markdown, code }) => {
        const { container } = render(<MarkdownRenderer content={markdown} />);
        
        // Should contain a code element
        const codeElements = container.querySelectorAll('code');
        expect(codeElements.length).toBeGreaterThan(0);
        
        // At least one code element should contain the code
        const hasCode = Array.from(codeElements).some(el => el.textContent === code);
        expect(hasCode).toBe(true);
        
        // Inline code should not be wrapped in pre
        const inlineCode = Array.from(codeElements).find(el => el.textContent === code);
        expect(inlineCode?.closest('pre')).toBeNull();
      }),
      { numRuns: 50 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 6: Markdown rendering**
   * **Validates: Requirements 3.6**
   *
   * For any LaTeX block, the rendered output should contain KaTeX elements.
   */
  it('renders LaTeX block math', () => {
    fc.assert(
      fc.property(latexBlockArbitrary, ({ markdown }) => {
        const { container } = render(<MarkdownRenderer content={markdown} />);
        
        // KaTeX renders math in elements with class 'katex' or 'katex-display'
        const katexElement = container.querySelector('.katex, .katex-display');
        expect(katexElement).not.toBeNull();
      }),
      { numRuns: 50 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 6: Markdown rendering**
   * **Validates: Requirements 3.6**
   *
   * For any inline LaTeX, the rendered output should contain KaTeX elements.
   */
  it('renders LaTeX inline math', () => {
    fc.assert(
      fc.property(latexInlineArbitrary, ({ markdown }) => {
        const { container } = render(<MarkdownRenderer content={markdown} />);
        
        // KaTeX renders math in elements with class 'katex'
        const katexElement = container.querySelector('.katex');
        expect(katexElement).not.toBeNull();
      }),
      { numRuns: 50 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 6: Markdown rendering**
   * **Validates: Requirements 3.6**
   *
   * For any heading, the rendered output should contain the correct heading element.
   */
  it('renders headings with correct level', () => {
    fc.assert(
      fc.property(headingArbitrary, ({ markdown, level, text }) => {
        const { container } = render(<MarkdownRenderer content={markdown} />);
        
        // Should contain the correct heading element
        const headingElement = container.querySelector(`h${level}`);
        expect(headingElement).not.toBeNull();
        expect(headingElement?.textContent).toBe(text);
      }),
      { numRuns: 50 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 6: Markdown rendering**
   * **Validates: Requirements 3.6**
   *
   * For any unordered list, the rendered output should contain ul with li elements.
   */
  it('renders unordered lists correctly', () => {
    fc.assert(
      fc.property(unorderedListArbitrary, ({ markdown, items }) => {
        const { container } = render(<MarkdownRenderer content={markdown} />);
        
        // Should contain a ul element
        const ulElement = container.querySelector('ul');
        expect(ulElement).not.toBeNull();
        
        // Should have correct number of li elements
        const liElements = ulElement?.querySelectorAll('li');
        expect(liElements?.length).toBe(items.length);
      }),
      { numRuns: 50 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 6: Markdown rendering**
   * **Validates: Requirements 3.6**
   *
   * For any ordered list, the rendered output should contain ol with li elements.
   */
  it('renders ordered lists correctly', () => {
    fc.assert(
      fc.property(orderedListArbitrary, ({ markdown, items }) => {
        const { container } = render(<MarkdownRenderer content={markdown} />);
        
        // Should contain an ol element
        const olElement = container.querySelector('ol');
        expect(olElement).not.toBeNull();
        
        // Should have correct number of li elements
        const liElements = olElement?.querySelectorAll('li');
        expect(liElements?.length).toBe(items.length);
      }),
      { numRuns: 50 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 6: Markdown rendering**
   * **Validates: Requirements 3.6**
   *
   * The markdown renderer should have a data-testid for testing.
   */
  it('renders with correct test id', () => {
    fc.assert(
      fc.property(fc.string({ minLength: 1, maxLength: 100 }), (content) => {
        const { container } = render(<MarkdownRenderer content={content} />);
        
        const renderer = container.querySelector('[data-testid="markdown-renderer"]');
        expect(renderer).not.toBeNull();
      }),
      { numRuns: 50 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 6: Markdown rendering**
   * **Validates: Requirements 3.6**
   *
   * For any blockquote, the rendered output should contain a blockquote element.
   */
  it('renders blockquotes correctly', () => {
    // Use text without leading/trailing spaces since markdown trims them
    const blockquoteArbitrary = fc.stringMatching(/^[a-zA-Z0-9][a-zA-Z0-9 ]*[a-zA-Z0-9]$/)
      .filter(s => s.length >= 2 && s.length <= 50)
      .map(text => ({
        markdown: `> ${text}`,
        text: text.trim(),
      }));

    fc.assert(
      fc.property(blockquoteArbitrary, ({ markdown, text }) => {
        const { container } = render(<MarkdownRenderer content={markdown} />);
        
        // Should contain a blockquote element
        const blockquote = container.querySelector('blockquote');
        expect(blockquote).not.toBeNull();
        expect(blockquote?.textContent).toContain(text);
      }),
      { numRuns: 50 }
    );
  });
});

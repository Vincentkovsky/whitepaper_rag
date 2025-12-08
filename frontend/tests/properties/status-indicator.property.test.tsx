/**
 * Property-Based Tests for Status Indicator
 * **Feature: frontend-redesign, Property 15: Intent status indicator mapping**
 * **Validates: Requirements 9.1, 9.2, 9.3**
 *
 * Property: For any intent type from the router, the correct status indicator
 * text and icon should be displayed.
 */

import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { render } from '@testing-library/react';
import { StatusIndicator, getStatusConfig } from '../../src/components/StatusIndicator';
import type { AgentStatus } from '../../src/types';

// All valid agent statuses
const allStatuses: AgentStatus[] = [
  'idle',
  'thinking',
  'searching_docs',
  'searching_web',
  'analyzing',
  'generating',
];

// Generator for valid agent status
const agentStatusArbitrary = fc.constantFrom(...allStatuses);

// Generator for tool names
const toolNameArbitrary = fc.constantFrom(
  'web_search',
  'document_search',
  'retrieve_documents',
  'calculate',
  'compute_math',
  'browse_web',
  'custom_tool'
);

// Expected text patterns for each status
const expectedTextPatterns: Record<AgentStatus, RegExp> = {
  idle: /ready/i,
  thinking: /thinking/i,
  searching_docs: /searching|using/i,
  searching_web: /searching|web|using/i,
  analyzing: /analyzing|using/i,
  generating: /generating/i,
};

describe('Status Indicator Property Tests', () => {
  /**
   * **Feature: frontend-redesign, Property 15: Intent status indicator mapping**
   * **Validates: Requirements 9.1, 9.2, 9.3**
   *
   * For any valid agent status, the StatusIndicator should render with
   * the correct data-status attribute.
   */
  it('renders with correct status attribute for any valid status', () => {
    fc.assert(
      fc.property(agentStatusArbitrary, (status) => {
        const { container } = render(<StatusIndicator status={status} />);
        
        const indicator = container.querySelector('[data-testid="status-indicator"]');
        expect(indicator).not.toBeNull();
        expect(indicator?.getAttribute('data-status')).toBe(status);
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 15: Intent status indicator mapping**
   * **Validates: Requirements 9.1, 9.2, 9.3**
   *
   * For any valid agent status, the status text should match expected patterns.
   */
  it('displays appropriate text for each status', () => {
    fc.assert(
      fc.property(agentStatusArbitrary, (status) => {
        const config = getStatusConfig(status);
        
        expect(config.text).toMatch(expectedTextPatterns[status]);
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 15: Intent status indicator mapping**
   * **Validates: Requirements 9.1, 9.2, 9.3**
   *
   * For any valid agent status, getStatusConfig should return all required fields.
   */
  it('getStatusConfig returns complete configuration for any status', () => {
    fc.assert(
      fc.property(agentStatusArbitrary, (status) => {
        const config = getStatusConfig(status);
        
        // Should have all required fields
        expect(config).toHaveProperty('text');
        expect(config).toHaveProperty('icon');
        expect(config).toHaveProperty('color');
        expect(config).toHaveProperty('bgColor');
        
        // Text should be non-empty
        expect(config.text.length).toBeGreaterThan(0);
        
        // Color classes should be valid Tailwind patterns
        expect(config.color).toMatch(/^text-\w+-\d+/);
        expect(config.bgColor).toMatch(/^bg-\w+-\d+/);
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 15: Intent status indicator mapping**
   * **Validates: Requirements 9.1, 9.2, 9.3**
   *
   * For any status with a tool name, the text should include the tool name.
   */
  it('includes tool name in text when provided for active statuses', () => {
    const activeStatuses: AgentStatus[] = ['searching_docs', 'searching_web', 'analyzing'];
    const activeStatusArbitrary = fc.constantFrom(...activeStatuses);

    fc.assert(
      fc.property(activeStatusArbitrary, toolNameArbitrary, (status, toolName) => {
        const config = getStatusConfig(status, toolName);
        
        // Text should mention the tool
        expect(config.text.toLowerCase()).toContain('using');
        expect(config.text).toContain(toolName);
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 15: Intent status indicator mapping**
   * **Validates: Requirements 9.1, 9.2, 9.3**
   *
   * The StatusIndicator should have proper accessibility attributes.
   */
  it('has proper accessibility attributes for any status', () => {
    fc.assert(
      fc.property(agentStatusArbitrary, (status) => {
        const { container } = render(<StatusIndicator status={status} />);
        
        const indicator = container.querySelector('[data-testid="status-indicator"]');
        
        // Should have role="status" for screen readers
        expect(indicator?.getAttribute('role')).toBe('status');
        
        // Should have aria-live for dynamic updates
        expect(indicator?.getAttribute('aria-live')).toBe('polite');
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 15: Intent status indicator mapping**
   * **Validates: Requirements 9.1, 9.2, 9.3**
   *
   * For idle status, no pulsing indicator should be shown.
   * For active statuses, a pulsing indicator should be present.
   */
  it('shows pulsing indicator only for active statuses', () => {
    fc.assert(
      fc.property(agentStatusArbitrary, (status) => {
        const { container } = render(<StatusIndicator status={status} />);
        
        // Look for the pulsing animation class
        const pulsingElement = container.querySelector('.animate-ping');
        
        if (status === 'idle') {
          // Idle should not have pulsing indicator
          expect(pulsingElement).toBeNull();
        } else {
          // Active statuses should have pulsing indicator
          expect(pulsingElement).not.toBeNull();
        }
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 15: Intent status indicator mapping**
   * **Validates: Requirements 9.1, 9.2, 9.3**
   *
   * Each status should have a unique color scheme.
   */
  it('different statuses have distinct color schemes', () => {
    // Get configs for all statuses
    const configs = allStatuses.map(status => ({
      status,
      config: getStatusConfig(status),
    }));

    // Check that active statuses have different colors
    const activeConfigs = configs.filter(c => c.status !== 'idle');
    const colorSet = new Set(activeConfigs.map(c => c.config.color));
    
    // Should have multiple distinct colors for different statuses
    expect(colorSet.size).toBeGreaterThan(1);
  });

  /**
   * **Feature: frontend-redesign, Property 15: Intent status indicator mapping**
   * **Validates: Requirements 9.1, 9.2, 9.3**
   *
   * The rendered indicator should contain the status text.
   */
  it('rendered indicator contains status text', () => {
    fc.assert(
      fc.property(agentStatusArbitrary, (status) => {
        const { container } = render(<StatusIndicator status={status} />);
        const config = getStatusConfig(status);
        
        // The indicator should contain the expected text
        expect(container.textContent).toContain(config.text);
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 15: Intent status indicator mapping**
   * **Validates: Requirements 9.1, 9.2, 9.3**
   *
   * Custom className should be applied to the indicator.
   */
  it('applies custom className when provided', () => {
    fc.assert(
      fc.property(
        agentStatusArbitrary,
        fc.stringMatching(/^[a-z-]+$/),
        (status, customClass) => {
          const { container } = render(
            <StatusIndicator status={status} className={customClass} />
          );
          
          const indicator = container.querySelector('[data-testid="status-indicator"]');
          expect(indicator?.className).toContain(customClass);
        }
      ),
      { numRuns: 50 }
    );
  });
});

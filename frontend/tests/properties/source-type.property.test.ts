/**
 * Property-Based Tests for Source Type Component Selection
 * **Feature: frontend-redesign, Property 14: Source type component selection**
 * **Validates: Requirements 8.5, 8.6**
 *
 * Property: For any citation, if sourceType is 'pdf' then PDF viewer is used,
 * if sourceType is 'web' then card component is used.
 */

import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { getSourceTypeComponent } from '../../src/components/EvidenceBoard';

// Generator for source types
const sourceTypeArbitrary: fc.Arbitrary<'pdf' | 'web'> = fc.constantFrom('pdf', 'web');

describe('Source Type Component Selection Property Tests', () => {
  /**
   * **Feature: frontend-redesign, Property 14: Source type component selection**
   * **Validates: Requirements 8.5, 8.6**
   *
   * For any citation with sourceType 'pdf', the PDFViewer component should be selected.
   */
  it('selects PDFViewer for pdf source type', () => {
    fc.assert(
      fc.property(fc.constant('pdf' as const), (sourceType) => {
        const component = getSourceTypeComponent(sourceType);
        expect(component).toBe('PDFViewer');
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 14: Source type component selection**
   * **Validates: Requirements 8.5, 8.6**
   *
   * For any citation with sourceType 'web', the WebCard component should be selected.
   */
  it('selects WebCard for web source type', () => {
    fc.assert(
      fc.property(fc.constant('web' as const), (sourceType) => {
        const component = getSourceTypeComponent(sourceType);
        expect(component).toBe('WebCard');
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 14: Source type component selection**
   * **Validates: Requirements 8.5, 8.6**
   *
   * For any source type, the component selection should be deterministic
   * (same input always produces same output).
   */
  it('component selection is deterministic', () => {
    fc.assert(
      fc.property(sourceTypeArbitrary, (sourceType) => {
        const result1 = getSourceTypeComponent(sourceType);
        const result2 = getSourceTypeComponent(sourceType);
        expect(result1).toBe(result2);
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 14: Source type component selection**
   * **Validates: Requirements 8.5, 8.6**
   *
   * For any source type, the returned component name should be one of the valid options.
   */
  it('returns valid component names', () => {
    fc.assert(
      fc.property(sourceTypeArbitrary, (sourceType) => {
        const component = getSourceTypeComponent(sourceType);
        expect(['PDFViewer', 'WebCard']).toContain(component);
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 14: Source type component selection**
   * **Validates: Requirements 8.5, 8.6**
   *
   * The mapping between source types and components should be bijective
   * (each source type maps to exactly one component, and vice versa).
   */
  it('source type to component mapping is bijective', () => {
    fc.assert(
      fc.property(sourceTypeArbitrary, sourceTypeArbitrary, (type1, type2) => {
        const comp1 = getSourceTypeComponent(type1);
        const comp2 = getSourceTypeComponent(type2);
        
        // If source types are the same, components should be the same
        if (type1 === type2) {
          expect(comp1).toBe(comp2);
        }
        // If source types are different, components should be different
        else {
          expect(comp1).not.toBe(comp2);
        }
      }),
      { numRuns: 100 }
    );
  });
});

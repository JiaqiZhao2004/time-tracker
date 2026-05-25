import { describe, expect, it } from 'vitest'
import { categoryNameValidationError, normalizeCategoryName } from './categoryNames'

describe('Category Names', () => {
  it('normalizes surrounding and repeated whitespace', () => {
    expect(normalizeCategoryName('  Research   &  Writing  ')).toBe('Research & Writing')
  })

  it('accepts letters, numbers, and supported punctuation', () => {
    expect(categoryNameValidationError("Etude - 学習 & Writing 2's", [])).toBe('')
  })

  it('rejects markup and unsupported symbols', () => {
    expect(categoryNameValidationError('<script>alert(1)</script>', [])).toContain('letters')
    expect(categoryNameValidationError('Study!', [])).toContain('letters')
  })

  it('rejects duplicate active or disabled names after normalization', () => {
    expect(categoryNameValidationError(
      ' research   & writing ',
      [{ name: 'Research & Writing' }],
    )).toContain('already exists')
  })
})

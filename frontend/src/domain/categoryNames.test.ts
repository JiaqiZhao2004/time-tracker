import { describe, expect, it } from 'vitest'
import { categoryNameValidationError, normalizeCategoryName } from './categoryNames'

describe('Category Names', () => {
  it('normalizes surrounding and repeated whitespace', () => {
    expect(normalizeCategoryName('  Research   &  Writing  ')).toBe('Research & Writing')
  })

  it('accepts letters, numbers, and supported punctuation', () => {
    expect(categoryNameValidationError("Etude - 学習 & Writing 2's", [])).toBe('')
  })

  it('accepts supported emoji sequences', () => {
    for (const name of ['Study 📚', 'Family 👨‍👩‍👧', 'Exercise 👍🏽', 'Travel 🇯🇵', 'Focus 1️⃣']) {
      expect(categoryNameValidationError(name, [])).toBe('')
    }
  })

  it('rejects markup and unsupported symbols', () => {
    expect(categoryNameValidationError('<script>alert(1)</script>', [])).toContain('letters')
    expect(categoryNameValidationError('Study!', [])).toContain('letters')
    expect(categoryNameValidationError('Study \u200d', [])).toContain('letters')
    expect(categoryNameValidationError('Study \ufe0f', [])).toContain('letters')
    expect(categoryNameValidationError('Study 🏽', [])).toContain('letters')
  })

  it('rejects duplicate active or disabled names after normalization', () => {
    expect(categoryNameValidationError(
      ' research   & writing ',
      [{ name: 'Research & Writing' }],
    )).toContain('already exists')
  })

  it('allows an unchanged name when the edited category is excluded', () => {
    const categories = [{ categoryId: 'work', name: 'Work' }, { categoryId: 'rest', name: 'Rest' }]
    const others = categories.filter((category) => category.categoryId !== 'work')

    expect(categoryNameValidationError(' Work ', others)).toBe('')
  })
})

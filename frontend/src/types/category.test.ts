import { describe, expect, it } from 'vitest'
import { categoryColor, displayCategories } from './category'

const category = (categoryId: string, name: string) => ({
  categoryId,
  name,
  isActive: true,
})

describe('category colors', () => {
  it('keeps named colors higher priority than emoji colors', () => {
    expect(categoryColor(category('work', 'Work'))).toBe('#00b894')
  })

  it('uses the cyan base color for the first flag category', () => {
    const categories = displayCategories([
      category('flag-alpha', 'Alpha 🏁'),
      category('flag-study', 'Study 🏁'),
    ])

    expect(categories.find((item) => item.categoryId === 'flag-alpha')?.color).toBe('#00cec9')
  })

  it('increments flag hues in stable sorted order', () => {
    const categories = displayCategories([
      category('flag-z', 'Later 🏁'),
      category('flag-a', 'Earlier 🏁'),
    ])
    const reordered = displayCategories([...categories].reverse())

    expect(categories.find((item) => item.categoryId === 'flag-a')?.color).toBe('#00cec9')
    expect(categories.find((item) => item.categoryId === 'flag-z')?.color).toBe('hsl(184, 100%, 40%)')
    expect(reordered.find((item) => item.categoryId === 'flag-a')?.color).toBe('#00cec9')
    expect(reordered.find((item) => item.categoryId === 'flag-z')?.color).toBe('hsl(184, 100%, 40%)')
  })

  it('uses the light-purple base color and increments prayer hues', () => {
    const categories = displayCategories([
      category('prayer-b', 'B Evening 🙏'),
      category('prayer-a', 'A Morning 🙏'),
    ])

    expect(categories.find((item) => item.categoryId === 'prayer-a')?.color).toBe('#a29bfe')
    expect(categories.find((item) => item.categoryId === 'prayer-b')?.color).toBe('hsl(249, 98%, 80%)')
  })

  it('uses flag colors first when both emojis are present', () => {
    const categories = displayCategories([category('both', 'Both 🏁 🙏')])

    expect(categories[0]?.color).toBe('#00cec9')
  })

  it('keeps non-emoji categories on stable fallback colors', () => {
    expect(categoryColor(category('custom-id', 'Custom'))).toBe(
      categoryColor(category('custom-id', 'Renamed custom category')),
    )
  })
})

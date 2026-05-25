import type { Category } from '../types/category'

const allowedName = /^[\p{L}\p{N} '&-]+$/u

export const normalizeCategoryName = (name: string): string =>
  name.normalize('NFC').trim().replace(/\s+/gu, ' ')

const comparableCategoryName = (name: string): string =>
  normalizeCategoryName(name).toLowerCase()

export const categoryNameValidationError = (
  name: string,
  categories: readonly Pick<Category, 'name'>[],
): string => {
  const normalized = normalizeCategoryName(name)
  if (!normalized) {
    return 'Enter a category name.'
  }
  if (!allowedName.test(normalized)) {
    return "Use letters, numbers, spaces, hyphens, apostrophes, and ampersands only."
  }
  if (categories.some((category) => comparableCategoryName(category.name) === comparableCategoryName(normalized))) {
    return 'A category with this name already exists.'
  }
  return ''
}

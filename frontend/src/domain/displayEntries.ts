import type { Category } from '../types/category'
import type { DisplayEntry, Entry } from '../types/entry'

export const resolveDisplayEntries = (entries: Entry[], categories: Category[]): DisplayEntry[] => {
  const categoryNames = new Map(categories.map((category) => [category.categoryId, category.name]))

  return entries.map((entry) => ({
    ...entry,
    categoryName: categoryNames.get(entry.categoryId) ?? entry.categoryId,
  }))
}

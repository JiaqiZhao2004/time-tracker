export type Category = {
  categoryId: string
  name: string
  isActive: boolean
}

export type DisplayCategory = Category & {
  color: string
}

const namedColors: Record<string, string> = {
  coursework: '#6c63ff',
  work: '#00b894',
  prayer: '#fdcb6e',
  rest: '#0984e3',
  social: '#e17055',
  family: '#d63031',
  'self-study': '#a29bfe',
  chores: '#fd79a8',
  exercise: '#00cec9',
}

const fallbackColors = [
  '#6c63ff',
  '#00b894',
  '#0984e3',
  '#e17055',
  '#fd79a8',
  '#00cec9',
  '#a29bfe',
]

const normalizedName = (name: string): string =>
  name.trim().toLowerCase().replace(/\s+/g, '-')

const stableIndex = (value: string): number => {
  let hash = 0
  for (const char of value) {
    hash = (hash * 31 + char.charCodeAt(0)) >>> 0
  }
  return hash % fallbackColors.length
}

export const categoryColor = (category: Pick<Category, 'categoryId' | 'name'>): string =>
  namedColors[normalizedName(category.name)] ??
  fallbackColors[stableIndex(category.categoryId)]!

export const displayCategory = (category: Category): DisplayCategory => ({
  ...category,
  color: categoryColor(category),
})

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

const FLAG_EMOJI = '🏁'
const PRAYER_EMOJI = '🙏'
const EMOJI_HUE_INCREMENT = 15

const normalizedName = (name: string): string =>
  name.trim().toLowerCase().replace(/\s+/g, '-')

const stableIndex = (value: string): number => {
  let hash = 0
  for (const char of value) {
    hash = (hash * 31 + char.charCodeAt(0)) >>> 0
  }
  return hash % fallbackColors.length
}

const categorySort = (
  left: Pick<Category, 'categoryId' | 'name'>,
  right: Pick<Category, 'categoryId' | 'name'>,
): number =>
  normalizedName(left.name).localeCompare(normalizedName(right.name)) ||
  left.categoryId.localeCompare(right.categoryId)

const hexToHsl = (hex: string): [number, number, number] => {
  const red = Number.parseInt(hex.slice(1, 3), 16) / 255
  const green = Number.parseInt(hex.slice(3, 5), 16) / 255
  const blue = Number.parseInt(hex.slice(5, 7), 16) / 255
  const max = Math.max(red, green, blue)
  const min = Math.min(red, green, blue)
  const lightness = (max + min) / 2

  if (max === min) {
    return [0, 0, lightness * 100]
  }

  const delta = max - min
  const saturation = lightness > 0.5 ? delta / (2 - max - min) : delta / (max + min)
  let hue: number

  if (max === red) {
    hue = (green - blue) / delta + (green < blue ? 6 : 0)
  } else if (max === green) {
    hue = (blue - red) / delta + 2
  } else {
    hue = (red - green) / delta + 4
  }

  return [(hue * 60) % 360, saturation * 100, lightness * 100]
}

const hueShiftedColor = (baseColor: string, offset: number): string => {
  if (offset === 0) {
    return baseColor
  }

  const [hue, saturation, lightness] = hexToHsl(baseColor)
  const shiftedHue = Math.round((hue + offset * EMOJI_HUE_INCREMENT) % 360)
  return `hsl(${shiftedHue}, ${Math.round(saturation)}%, ${Math.round(lightness)}%)`
}

const emojiColor = (
  category: Pick<Category, 'categoryId' | 'name'>,
  categories: ReadonlyArray<Pick<Category, 'categoryId' | 'name'>>,
  emoji: string,
  baseColor: string,
): string | undefined => {
  if (!category.name.includes(emoji)) {
    return undefined
  }

  const matchingCategories = categories
    .filter((candidate) => candidate.name.includes(emoji))
    .sort(categorySort)
  const categoryIndex = matchingCategories.findIndex(
    (candidate) => candidate.categoryId === category.categoryId,
  )

  return hueShiftedColor(baseColor, Math.max(0, categoryIndex))
}

export const categoryColor = (
  category: Pick<Category, 'categoryId' | 'name'>,
  categories: ReadonlyArray<Pick<Category, 'categoryId' | 'name'>> = [category],
): string => {
  const namedColor = namedColors[normalizedName(category.name)]
  if (namedColor) {
    return namedColor
  }

  return (
    emojiColor(category, categories, FLAG_EMOJI, '#00cec9') ??
    emojiColor(category, categories, PRAYER_EMOJI, '#a29bfe') ??
    fallbackColors[stableIndex(category.categoryId)]!
  )
}

export const displayCategory = (
  category: Category,
  categories: ReadonlyArray<Pick<Category, 'categoryId' | 'name'>> = [category],
): DisplayCategory => ({
  ...category,
  color: categoryColor(category, categories),
})

export const displayCategories = (categories: Category[]): DisplayCategory[] =>
  categories.map((category) => displayCategory(category, categories))

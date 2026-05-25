import type { Category } from '../types/category'

const pictographicEmoji = String.raw`\p{Extended_Pictographic}\uFE0F?(?:\p{Emoji_Modifier})?`
const emojiSequence = String.raw`(?:${pictographicEmoji}(?:\u200D${pictographicEmoji})*|\p{Regional_Indicator}{2}|[0-9#*]\uFE0F?\u20E3)`
const allowedName = new RegExp(String.raw`^(?:[\p{L}\p{N} '&-]+|${emojiSequence})+$`, 'u')

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
    return "Use letters, numbers, spaces, hyphens, apostrophes, ampersands, and emoji only."
  }
  if (categories.some((category) => comparableCategoryName(category.name) === comparableCategoryName(normalized))) {
    return 'A category with this name already exists.'
  }
  return ''
}

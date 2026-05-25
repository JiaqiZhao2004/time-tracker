import { describe, expect, it } from 'vitest'
import type { Category } from '../types/category'
import type { Entry } from '../types/entry'
import { resolveDisplayEntries } from './displayEntries'

const entry: Entry = {
  id: 'entry-1',
  categoryId: 'work',
  timestamp: '2026-05-25T12:00:00.000Z',
}

describe('Display Entries', () => {
  it('resolves names from fetched categories', () => {
    expect(resolveDisplayEntries([entry], [{ categoryId: 'work', name: 'Work', isActive: true }]))
      .toEqual([{ ...entry, categoryName: 'Work' }])
  })

  it('uses the current fetched name after a category is renamed', () => {
    expect(resolveDisplayEntries([entry], [{ categoryId: 'work', name: 'Client Work', isActive: true }])[0]?.categoryName)
      .toBe('Client Work')
  })

  it('resolves names for inactive fetched categories', () => {
    const categories: Category[] = [{ categoryId: 'work', name: 'Archived Work', isActive: false }]

    expect(resolveDisplayEntries([entry], categories)[0]?.categoryName).toBe('Archived Work')
  })

  it('uses the category id when a category is absent', () => {
    expect(resolveDisplayEntries([entry], [])[0]?.categoryName).toBe('work')
  })
})

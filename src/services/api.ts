/**
 * API service functions for fetching and posting time tracker entries
 */
import type { Category } from '../types/category'

export type Entry = {
  id: number
  category: Category
  timestamp: string
}

export type EntriesLocalResponse = {
  prevEntryCategory: Category | null
  entries: Entry[]
}

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

/**
 * Posts a new category entry to the API
 */
export const postEntry = async (category: Category, timestamp: string): Promise<Entry> => {
  const response = await fetch(`${API_BASE}/entries`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ category, timestamp }),
  })
  
  if (!response.ok) {
    throw new Error('Failed to save entry')
  }
  
  return response.json()
}

/**
 * Fetches entries for a specific local day with timezone
 */
export const fetchEntriesLocal = async (timezone: string, date: string): Promise<EntriesLocalResponse> => {
  const params = new URLSearchParams({ timezone, date })
  const response = await fetch(`${API_BASE}/entries-local?${params.toString()}`)
  
  if (!response.ok) {
    throw new Error('Failed to load entries')
  }
  
  return await response.json()
}

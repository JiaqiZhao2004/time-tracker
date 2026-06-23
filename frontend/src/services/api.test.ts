import { afterEach, describe, expect, it, vi } from 'vitest'
import { createCategory, fetchCategories, fetchEntriesLocalWeek, postEntry } from './api'

vi.mock('./auth', () => ({
  getAuthorizationHeader: vi.fn(async () => ({ Authorization: 'Bearer test-token' })),
  signIn: vi.fn(async () => undefined),
}))

const auth = await import('./auth')

const dates = [
  '2026-05-25',
  '2026-05-26',
  '2026-05-27',
  '2026-05-28',
  '2026-05-29',
  '2026-05-30',
  '2026-05-31',
]

const response = (body: unknown): Response =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })

afterEach(() => {
  vi.unstubAllGlobals()
  vi.mocked(auth.signIn).mockClear()
})

describe('fetchEntriesLocalWeek', () => {
  it('uses one request when the backend identifies a weekly response', async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) =>
      response({ period: 'week', prevEntryCategoryId: 'work', entries: [] }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const result = await fetchEntriesLocalWeek('America/Chicago', dates)

    expect(result.period).toBe('week')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('period=week')
    expect(String(fetchMock.mock.calls[0]?.[0])).not.toContain('user_id')
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({
      headers: { Authorization: 'Bearer test-token' },
    })
  })

  it('combines seven daily responses when a legacy backend ignores period', async () => {
    const fetchMock = vi.fn(async (url: string) => {
      const date = new URL(url).searchParams.get('date')!
      return response({
        prevEntryCategoryId: date === dates[0] ? 'rest' : null,
        entries: [{ id: date, categoryId: 'work', timestamp: `${date}T12:00:00Z` }],
      })
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await fetchEntriesLocalWeek('America/Chicago', dates)

    expect(fetchMock).toHaveBeenCalledTimes(7)
    expect(result.prevEntryCategoryId).toBe('rest')
    expect(result.entries.map((entry) => entry.id)).toEqual(dates)
  })
})

describe('authenticated API requests', () => {
  it('adds bearer auth when loading categories', async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => response([]))
    vi.stubGlobal('fetch', fetchMock)

    await fetchCategories()

    expect(fetchMock).toHaveBeenCalledWith('http://localhost:8000/categories', {
      headers: { Authorization: 'Bearer test-token' },
    })
  })

  it('starts sign-in redirect when the backend says the session is unauthorized', async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) =>
      new Response(JSON.stringify({ detail: 'Missing authenticated user' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await expect(fetchCategories()).rejects.toThrow('Missing authenticated user')

    expect(auth.signIn).toHaveBeenCalledTimes(1)
  })

  it('does not send user_id in mutation bodies', async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) =>
      response({ categoryId: 'study', name: 'Study', isActive: true }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await createCategory('Study')

    const body = JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))
    expect(body).toEqual({ name: 'Study' })
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({
      headers: {
        Authorization: 'Bearer test-token',
        'Content-Type': 'application/json',
      },
    })
  })

  it('omits timestamp when posting a quick entry', async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) =>
      response({ id: 'entry-1', categoryId: 'study', timestamp: '2026-05-31T21:46:40Z' }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await postEntry('study')

    const body = JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))
    expect(body).toEqual({ categoryId: 'study' })
  })

  it('includes timestamp when posting a manual entry', async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) =>
      response({ id: 'entry-1', categoryId: 'study', timestamp: '2026-05-31T21:46:40Z' }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await postEntry('study', '2026-05-31T21:46:40.000Z')

    const body = JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))
    expect(body).toEqual({
      categoryId: 'study',
      timestamp: '2026-05-31T21:46:40.000Z',
    })
  })
})

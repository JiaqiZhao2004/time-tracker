import { afterEach, describe, expect, it, vi } from 'vitest'

type StoredUser = {
  expired: boolean
  id_token?: string
}

type UserManagerInstance = {
  getUser: ReturnType<typeof vi.fn<() => Promise<StoredUser | null>>>
  signinSilent: ReturnType<typeof vi.fn<() => Promise<StoredUser | null>>>
  settings: Record<string, unknown>
}

const authMocks = vi.hoisted(() => {
  const instances: UserManagerInstance[] = []

  return {
    instances,
    UserManager: vi.fn((settings: Record<string, unknown>) => {
      const instance: UserManagerInstance = {
        getUser: vi.fn(async () => null),
        signinSilent: vi.fn(async () => null),
        settings,
      }
      instances.push(instance)
      return instance
    }),
    WebStorageStateStore: vi.fn((settings: Record<string, unknown>) => ({ settings })),
  }
})

vi.mock('oidc-client-ts', () => authMocks)

const importConfiguredAuth = async () => {
  vi.stubEnv('VITE_COGNITO_AUTHORITY', 'https://cognito-idp.us-east-2.amazonaws.com/pool')
  vi.stubEnv('VITE_COGNITO_CLIENT_ID', 'client-id')
  vi.stubEnv('VITE_AUTH_REDIRECT_URI', 'https://app.example.com')
  vi.stubEnv('VITE_AUTH_LOGOUT_URI', 'https://app.example.com')

  const auth = await import('./auth')
  const manager = authMocks.instances[0]
  if (!manager) {
    throw new Error('Expected auth module to create a UserManager')
  }

  return { auth, manager }
}

afterEach(() => {
  vi.resetModules()
  vi.unstubAllEnvs()
  authMocks.instances.length = 0
  authMocks.UserManager.mockClear()
  authMocks.WebStorageStateStore.mockClear()
})

describe('auth token refresh', () => {
  it('enables automatic silent renew for active browser sessions', async () => {
    const { manager } = await importConfiguredAuth()

    expect(manager.settings).toMatchObject({
      automaticSilentRenew: true,
    })
  })

  it('returns the stored user while the ID token is still valid', async () => {
    const { auth, manager } = await importConfiguredAuth()
    const currentUser = { expired: false, id_token: 'current-id-token' }
    manager.getUser.mockResolvedValue(currentUser)

    await expect(auth.getSignedInUser()).resolves.toBe(currentUser)
    expect(manager.signinSilent).not.toHaveBeenCalled()
  })

  it('uses the refresh token through silent sign-in when the ID token expired', async () => {
    const { auth, manager } = await importConfiguredAuth()
    const refreshedUser = { expired: false, id_token: 'refreshed-id-token' }
    manager.getUser.mockResolvedValue({ expired: true, id_token: 'expired-id-token' })
    manager.signinSilent.mockResolvedValue(refreshedUser)

    await expect(auth.getSignedInUser()).resolves.toBe(refreshedUser)
    await expect(auth.getAuthorizationHeader()).resolves.toEqual({
      Authorization: 'Bearer refreshed-id-token',
    })
  })

  it('treats the user as signed out when refresh fails', async () => {
    const { auth, manager } = await importConfiguredAuth()
    manager.getUser.mockResolvedValue({ expired: true, id_token: 'expired-id-token' })
    manager.signinSilent.mockRejectedValue(new Error('refresh token expired'))

    await expect(auth.getSignedInUser()).resolves.toBeNull()
  })
})

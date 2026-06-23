import { UserManager, WebStorageStateStore, type User } from 'oidc-client-ts'

const authority = import.meta.env.VITE_COGNITO_AUTHORITY
const clientId = import.meta.env.VITE_COGNITO_CLIENT_ID
const cognitoDomain = import.meta.env.VITE_COGNITO_DOMAIN
const redirectUri = import.meta.env.VITE_AUTH_REDIRECT_URI ?? window.location.origin
const logoutUri = import.meta.env.VITE_AUTH_LOGOUT_URI ?? window.location.origin
const SIGNED_OUT_KEY = 'traceSignedOut'

export const isAuthConfigured = Boolean(authority && clientId)

const userManager = isAuthConfigured
  ? new UserManager({
      authority,
      client_id: clientId,
      redirect_uri: redirectUri,
      post_logout_redirect_uri: logoutUri,
      response_type: 'code',
      scope: 'openid email profile',
      loadUserInfo: false,
      automaticSilentRenew: true,
      ...(typeof window !== 'undefined'
        ? { userStore: new WebStorageStateStore({ store: window.localStorage }) }
        : {}),
    })
  : null

const isExplicitlySignedOut = (): boolean =>
  typeof window !== 'undefined' && window.localStorage.getItem(SIGNED_OUT_KEY) === 'true'

const markExplicitlySignedOut = (): void => {
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(SIGNED_OUT_KEY, 'true')
  }
}

const clearExplicitSignOut = (): void => {
  if (typeof window !== 'undefined') {
    window.localStorage.removeItem(SIGNED_OUT_KEY)
  }
}

export const signIn = async (): Promise<void> => {
  if (!userManager) {
    throw new Error('Authentication is not configured')
  }

  clearExplicitSignOut()
  await userManager.signinRedirect({
    extraQueryParams: { identity_provider: 'Google' },
  })
}

export const completeSignIn = async (): Promise<User> => {
  if (!userManager) {
    throw new Error('Authentication is not configured')
  }

  const user = await userManager.signinRedirectCallback()
  clearExplicitSignOut()
  return user
}

export const getSignedInUser = async (): Promise<User | null> => {
  if (!userManager) {
    return null
  }

  if (isExplicitlySignedOut()) {
    await userManager.removeUser()
    return null
  }

  const user = await userManager.getUser()
  if (!user) {
    return null
  }

  if (!user.expired) {
    return user
  }

  try {
    return await userManager.signinSilent()
  } catch {
    return null
  }
}

export const getAuthorizationHeader = async (): Promise<Record<string, string>> => {
  const user = await getSignedInUser()
  if (!user?.id_token) {
    return {}
  }

  return { Authorization: `Bearer ${user.id_token}` }
}

export const signOut = async (): Promise<void> => {
  if (!userManager) {
    return
  }

  markExplicitlySignedOut()
  await userManager.removeUser()
  if (cognitoDomain) {
    const params = new URLSearchParams({
      client_id: clientId,
      logout_uri: logoutUri,
    })
    window.location.assign(`${cognitoDomain}/logout?${params.toString()}`)
    return
  }

  await userManager.signoutRedirect()
}

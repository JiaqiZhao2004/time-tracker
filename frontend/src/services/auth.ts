import { UserManager, type User } from 'oidc-client-ts'

const authority = import.meta.env.VITE_COGNITO_AUTHORITY
const clientId = import.meta.env.VITE_COGNITO_CLIENT_ID
const cognitoDomain = import.meta.env.VITE_COGNITO_DOMAIN
const redirectUri = import.meta.env.VITE_AUTH_REDIRECT_URI ?? window.location.origin
const logoutUri = import.meta.env.VITE_AUTH_LOGOUT_URI ?? window.location.origin

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
      automaticSilentRenew: false,
    })
  : null

export const signIn = async (): Promise<void> => {
  if (!userManager) {
    throw new Error('Authentication is not configured')
  }

  await userManager.signinRedirect({
    extraQueryParams: { identity_provider: 'Google' },
  })
}

export const completeSignIn = async (): Promise<User> => {
  if (!userManager) {
    throw new Error('Authentication is not configured')
  }

  return userManager.signinRedirectCallback()
}

export const getSignedInUser = async (): Promise<User | null> => {
  if (!userManager) {
    return null
  }

  const user = await userManager.getUser()
  if (!user || user.expired) {
    return null
  }
  return user
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

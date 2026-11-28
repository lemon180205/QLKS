export async function login(username, password) {
  const response = await fetch('/api/auth/token/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify({ username, password }),
  })

  if (!response.ok) {
    if (response.status === 401 || response.status === 400) {
      throw new Error('Tên đăng nhập hoặc mật khẩu không hợp lệ.')
    }

    throw new Error(`Không thể đăng nhập (${response.status}).`)
  }

  const tokens = await response.json()

  const profileResponse = await fetch('/api/auth/me/', {
    headers: {
      Accept: 'application/json',
      Authorization: `Bearer ${tokens.access}`,
    },
  })

  if (!profileResponse.ok) {
    throw new Error(
      `Không lấy được thông tin tài khoản (${profileResponse.status}).`
    )
  }

  const user = await profileResponse.json()

  return {
    user,
    accessToken: tokens.access,
    refreshToken: tokens.refresh,
  }
}
export async function refreshAuth(auth) {
  const response = await fetch('/api/auth/token/refresh/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify({
      refresh: auth.refreshToken,
    }),
  })

  if (!response.ok) {
    throw new Error('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.')
  }

  const data = await response.json()

  if (typeof data.access !== 'string' || !data.access) {
    throw new Error('Không nhận được token đăng nhập mới.')
  }

  return {
    ...auth,
    accessToken: data.access,
    refreshToken: data.refresh || auth.refreshToken,
  }
}
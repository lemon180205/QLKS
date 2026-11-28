import { useState } from 'react'
import { login } from './auth'

export default function LoginForm({ onLogin }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(event) {
    event.preventDefault()

    if (loading) return

    setLoading(true)
    setError('')

    try {
      const result = await login(username.trim(), password)

      setPassword('')
      onLogin(result)
    } catch (err) {
      setError(
        err instanceof TypeError
          ? 'Không kết nối được máy chủ. Kiểm tra Django đang chạy.'
          : err.message
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="section" aria-labelledby="login-title">
      <div className="container">
        <h2 id="login-title">Đăng nhập</h2>

        <form
          className="stacked-form"
          onSubmit={handleSubmit}
          style={{ maxWidth: '440px' }}
        >
          <div className="form-field">
            <label htmlFor="login-username">Tên đăng nhập</label>

            <input
              id="login-username"
              type="text"
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              disabled={loading}
              required
            />
          </div>

          <div className="form-field">
            <label htmlFor="login-password">Mật khẩu</label>

            <input
              id="login-password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              disabled={loading}
              required
            />
          </div>

          {error && (
            <p className="form-errors" role="alert">
              {error}
            </p>
          )}

          <button
            className="button"
            type="submit"
            disabled={loading}
          >
            {loading ? 'Đang đăng nhập...' : 'Đăng nhập'}
          </button>
        </form>
      </div>
    </section>
  )
}
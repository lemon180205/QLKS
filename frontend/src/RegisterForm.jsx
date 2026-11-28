import { useState } from 'react'

export default function RegisterForm({ onRegistered }) {
  const [values, setValues] = useState({
    username: '',
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
    password1: '',
    password2: '',
  })

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  function handleChange(event) {
    setValues((previous) => ({
      ...previous,
      [event.target.name]: event.target.value,
    }))
  }

  async function handleSubmit(event) {
    event.preventDefault()

    if (loading) return

    if (values.password1 !== values.password2) {
      setError('Hai mật khẩu chưa giống nhau.')
      return
    }

    setLoading(true)
    setError('')

    try {
      const response = await fetch('/api/auth/register/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        body: JSON.stringify(values),
      })

      const data = await response.json()

      if (!response.ok) {
        const message = Object.values(data).flat().join(' ')
        throw new Error(message || 'Không đăng ký được tài khoản.')
      }

      setValues((previous) => ({
        ...previous,
        password1: '',
        password2: '',
      }))

      onRegistered(data)
    } catch (err) {
      setError(
        err instanceof TypeError
          ? 'Không kết nối được máy chủ.'
          : err.message
      )
    } finally {
      setLoading(false)
    }
  }

  const fields = [
    {
      name: 'username',
      label: 'Tên đăng nhập',
      type: 'text',
      autoComplete: 'username',
      required: true,
    },
    {
      name: 'first_name',
      label: 'Tên',
      type: 'text',
      autoComplete: 'given-name',
    },
    {
      name: 'last_name',
      label: 'Họ',
      type: 'text',
      autoComplete: 'family-name',
    },
    {
      name: 'email',
      label: 'Email',
      type: 'email',
      autoComplete: 'email',
      required: true,
    },
    {
      name: 'phone',
      label: 'Số điện thoại',
      type: 'tel',
      autoComplete: 'tel',
    },
    {
      name: 'password1',
      label: 'Mật khẩu',
      type: 'password',
      autoComplete: 'new-password',
      required: true,
    },
    {
      name: 'password2',
      label: 'Nhập lại mật khẩu',
      type: 'password',
      autoComplete: 'new-password',
      required: true,
    },
  ]

  return (
    <section className="section" aria-labelledby="register-title">
      <div className="container">
        <h2 id="register-title">Đăng ký tài khoản</h2>

        <form
          className="stacked-form"
          onSubmit={handleSubmit}
          style={{ maxWidth: '440px' }}
        >
          {fields.map((field) => (
            <div className="form-field" key={field.name}>
              <label htmlFor={`register-${field.name}`}>
                {field.label}
              </label>

              <input
                id={`register-${field.name}`}
                name={field.name}
                type={field.type}
                autoComplete={field.autoComplete}
                value={values[field.name]}
                onChange={handleChange}
                required={Boolean(field.required)}
                disabled={loading}
              />
            </div>
          ))}

          <p className="muted">
            Chọn mật khẩu đủ mạnh, không dùng lại mật khẩu
            của tài khoản khác.
          </p>

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
            {loading ? 'Đang đăng ký...' : 'Tạo tài khoản'}
          </button>
        </form>
      </div>
    </section>
  )
}
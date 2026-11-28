import { useState } from 'react'

export default function BookingForm({
  room,
  auth,
  criteria = {},
  onBooked,
  onCancel,
}) {
  const [values, setValues] = useState({
    guest_name:
      [auth.user.first_name, auth.user.last_name]
        .filter(Boolean)
        .join(' ') || auth.user.username,
    email: auth.user.email || '',
    phone: auth.user.phone || '',
    check_in: criteria.check_in || '',
    check_out: criteria.check_out || '',
    guest_count: criteria.guest_count || '1',
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

    if (values.check_out <= values.check_in) {
      setError('Ngày trả phòng phải sau ngày nhận phòng.')
      return
    }

    setLoading(true)
    setError('')

    try {
      const response = await fetch('/api/bookings/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
          Authorization: `Bearer ${auth.accessToken}`,
        },
        body: JSON.stringify({
          ...values,
          room_type: room.id,
          guest_count: Number(values.guest_count),
        }),
      })

      if (response.status === 401) {
        throw new Error(
          'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.'
        )
      }

      const data = await response.json()

      if (!response.ok) {
        const message = Object.values(data).flat().join(' ')
        throw new Error(message || 'Chưa gửi được yêu cầu đặt phòng.')
      }

      onBooked(data)
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

  const fields = [
    { name: 'guest_name', label: 'Tên khách', type: 'text' },
    { name: 'email', label: 'Email', type: 'email' },
    { name: 'phone', label: 'Số điện thoại', type: 'tel' },
    { name: 'check_in', label: 'Ngày nhận phòng', type: 'date' },
    { name: 'check_out', label: 'Ngày trả phòng', type: 'date' },
    { name: 'guest_count', label: 'Số khách', type: 'number' },
  ]

  return (
    <section className="section" id="booking-form">
      <div className="container">
        <h2>Đặt {room.name}</h2>

        <p className="muted">
          Yêu cầu sẽ chờ khách sạn xác nhận.
          Gửi form chưa phải thanh toán hoặc xác nhận giữ phòng.
        </p>

        <form className="stacked-form" onSubmit={handleSubmit}>
          {fields.map((field) => (
            <div className="form-field" key={field.name}>
              <label htmlFor={`booking-${field.name}`}>
                {field.label}
              </label>

              <input
                id={`booking-${field.name}`}
                name={field.name}
                type={field.type}
                value={values[field.name]}
                onChange={handleChange}
                min={field.type === 'number' ? 1 : undefined}
                max={
                  field.type === 'number'
                    ? room.capacity
                    : undefined
                }
                disabled={loading}
                required
              />
            </div>
          ))}

          {error && (
            <p className="form-errors" role="alert">
              {error}
            </p>
          )}

          <div className="room-actions">
            <button
              className="button"
              type="submit"
              disabled={loading}
            >
              {loading ? 'Đang gửi...' : 'Gửi yêu cầu đặt phòng'}
            </button>

            <button
              className="button button-secondary"
              type="button"
              onClick={onCancel}
              disabled={loading}
            >
              Hủy thao tác
            </button>
          </div>
        </form>
      </div>
    </section>
  )
}
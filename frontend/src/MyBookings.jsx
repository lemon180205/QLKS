import { useEffect, useState } from 'react'

const formatPrice = (value) =>
  new Intl.NumberFormat('vi-VN', {
    style: 'currency',
    currency: 'VND',
  }).format(Number(value))

const formatDate = (value) => {
  if (!value) return '—'
  const [year, month, day] = value.split('-')
  return `${day}/${month}/${year}`
}

export default function MyBookings({ accessToken, refreshKey = 0 }) {
  const [bookings, setBookings] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [cancelingId, setCancelingId] = useState(null)

  useEffect(() => {
    const controller = new AbortController()

    async function loadBookings() {
      setLoading(true)
      setError('')

      try {
        const response = await fetch('/api/bookings/mine/', {
          headers: {
            Accept: 'application/json',
            Authorization: `Bearer ${accessToken}`,
          },
          signal: controller.signal,
        })

        if (response.status === 401) {
          throw new Error(
            'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.'
          )
        }

        if (!response.ok) {
          throw new Error(
            `Không tải được lịch đặt phòng (${response.status}).`
          )
        }

        const data = await response.json()

        if (!Array.isArray(data)) {
          throw new Error('Dữ liệu lịch đặt phòng không hợp lệ.')
        }

        setBookings(data)
      } catch (err) {
        if (err.name !== 'AbortError') {
          setError(
            err instanceof TypeError
              ? 'Không kết nối được máy chủ.'
              : err.message
          )
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false)
        }
      }
    }

    loadBookings()

    return () => controller.abort()
  }, [accessToken, refreshKey])

    async function handleCancel(booking) {
    if (cancelingId !== null) return

    if (!window.confirm(`Hủy yêu cầu ${booking.code}?`)) return

    setCancelingId(booking.id)
    setError('')

    try {
      const response = await fetch(
        `/api/bookings/${booking.id}/cancel/`,
        {
          method: 'POST',
          headers: {
            Accept: 'application/json',
            Authorization: `Bearer ${accessToken}`,
          },
        }
      )

      if (response.status === 401) {
        throw new Error('Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.')
      }

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || 'Không hủy được yêu cầu.')
      }

      setBookings((previous) =>
        previous.map((item) => item.id === data.id ? data : item)
      )
    } catch (err) {
      setError(
        err instanceof TypeError
          ? 'Không kết nối được máy chủ.'
          : err.message
      )
    } finally {
      setCancelingId(null)
    }
  }

  return (
    <section className="section" id="my-bookings">
      <div className="container">
        <h2>Đặt phòng của tôi</h2>

        {loading && <p role="status">Đang tải lịch đặt phòng...</p>}

        {error && (
          <p className="form-errors" role="alert">
            {error}
          </p>
        )}

        {!loading && !error && bookings.length === 0 && (
          <p>Bạn chưa có yêu cầu đặt phòng nào.</p>
        )}

        {!loading && !error && (
          <div className="booking-list">
            {bookings.map((booking) => (
              <article className="booking-card" key={booking.id}>
                <div className="booking-card-header">
                  <div>
                    <p className="eyebrow">
                      MÃ ĐẶT PHÒNG {booking.code}
                    </p>
                    <h3>{booking.room_type_name}</h3>
                  </div>

                  <span className={`status-pill status-${booking.status}`}>
                    {booking.status_display}
                  </span>
                </div>

                <div className="booking-details">
                  <p>
                    <span>Nhận phòng</span>
                    <strong>{formatDate(booking.check_in)}</strong>
                  </p>

                  <p>
                    <span>Trả phòng</span>
                    <strong>{formatDate(booking.check_out)}</strong>
                  </p>

                  <p>
                    <span>Số khách</span>
                    <strong>{booking.guest_count}</strong>
                  </p>

                  <p>
                    <span>Thanh toán</span>
                    <strong>{booking.payment_status_display}</strong>
                  </p>

                  <p>
                    <span>Tổng tiền dự kiến</span>
                    <strong>{formatPrice(booking.total_price)}</strong>
                  </p>
                </div>
                {['pending', 'confirmed'].includes(booking.status) &&
                  !['paid', 'pending'].includes(booking.payment_status) && (
                    <button
                      className="button button-danger"
                      type="button"
                      disabled={cancelingId !== null}
                      onClick={() => handleCancel(booking)}
                    >
                      {cancelingId === booking.id
                        ? 'Đang hủy...'
                        : 'Hủy yêu cầu'}
                    </button>
                  )}
              </article>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}
import { useEffect, useState } from 'react'
import LoginForm from './LoginForm'
import RoomSearchForm from './RoomSearchForm'
import BookingForm from './BookingForm'
import MyBookings from './MyBookings'
import RegisterForm from './RegisterForm'
import { refreshAuth } from './auth'
import RoomDetail from './RoomDetail'



const formatPrice = (value) =>
  new Intl.NumberFormat('vi-VN', {
    style: 'currency',
    currency: 'VND',
  }).format(Number(value))

export default function App() {
  const [rooms, setRooms] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [auth, setAuth] = useState(null)
  const [authMode, setAuthMode] = useState('login')
  const [authNotice, setAuthNotice] = useState('')
  const [selectedRoom, setSelectedRoom] = useState(null)
  const [detailRoomId, setDetailRoomId] = useState(null)
  const [bookingResult, setBookingResult] = useState(null)
  const [searchCriteria, setSearchCriteria] = useState({})
  async function handleSearch(criteria) {
    if (loading) return

    setLoading(true)
    setError('')

    try {
      const query = new URLSearchParams(criteria)

      const response = await fetch(`/api/room-types/?${query}`, {
        headers: {
          Accept: 'application/json',
        },
      })

      const data = await response.json()

      if (!response.ok) {
        const message =
          data && typeof data === 'object'
            ? Object.values(data).flat().join(' ')
            : ''

        throw new Error(message || 'Không tìm được phòng. Vui lòng thử lại.')
      }

      if (!Array.isArray(data)) {
        throw new Error('Dữ liệu danh sách phòng không hợp lệ.')
      }

      setRooms(data)
      setSearchCriteria(criteria)
      setSelectedRoom(null)
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

  useEffect(() => {
    const controller = new AbortController()

    async function loadRooms() {
      try {
        const response = await fetch('/api/room-types/', {
          headers: { Accept: 'application/json' },
          signal: controller.signal,
        })

        if (!response.ok) {
          throw new Error(
            `Không tải được danh sách phòng (${response.status}).`
          )
        }

        const data = await response.json()

        if (!Array.isArray(data)) {
          throw new Error('Dữ liệu API chưa đúng định dạng danh sách.')
        }

        setRooms(data)
      } catch (err) {
        if (err.name !== 'AbortError') {
          setError(err.message)
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false)
        }
      }
    }

    loadRooms()

    return () => controller.abort()
  }, [])
  useEffect(() => {
    if (!auth) return

    let canceled = false
    let refreshing = false
    let timer
    let expiresAt = 0

    function endSession(message) {
      if (canceled) return

      setAuth(null)
      setSelectedRoom(null)
      setBookingResult(null)
      setAuthMode('login')
      setAuthNotice(message)
    }

    async function renew() {
      if (canceled || refreshing) return

      refreshing = true

      try {
        const updatedAuth = await refreshAuth(auth)

        if (!canceled) {
          setAuth(updatedAuth)
        }
      } catch {
        endSession(
          'Không làm mới được phiên đăng nhập. Vui lòng đăng nhập lại.'
        )
      } finally {
        refreshing = false
      }
    }

    function handleVisibilityChange() {
      if (
        document.visibilityState === 'visible' &&
        Date.now() >= expiresAt - 60_000
      ) {
        renew()
      }
    }

    try {
      const encoded = auth.accessToken
        .split('.')[1]
        .replace(/-/g, '+')
        .replace(/_/g, '/')

      const padded = encoded.padEnd(
        Math.ceil(encoded.length / 4) * 4,
        '='
      )

      const payload = JSON.parse(atob(padded))

      if (!Number.isFinite(payload.exp)) {
        throw new Error('Token không có thời hạn hợp lệ.')
      }

      expiresAt = payload.exp * 1000

      // Xin token mới trước khi token hiện tại hết hạn 1 phút.
      const delay = Math.max(0, expiresAt - Date.now() - 60_000)

      timer = window.setTimeout(renew, delay)

      document.addEventListener(
        'visibilitychange',
        handleVisibilityChange
      )
    } catch {
      timer = window.setTimeout(() => {
        endSession('Phiên đăng nhập không hợp lệ. Vui lòng đăng nhập lại.')
      }, 0)
    }

    return () => {
      canceled = true
      window.clearTimeout(timer)

      document.removeEventListener(
        'visibilitychange',
        handleVisibilityChange
      )
    }
  }, [auth])
  return (
    <>
      <header className="header">
        <div className="container header-inner">
          <a className="brand" href="/">
            <span className="brand-mark" aria-hidden="true">A</span>
            <span>
              An Nhiên
              <small>HOTEL &amp; RETREAT</small>
            </span>
          </a>

          <nav className="nav-links" aria-label="Điều hướng chính">
            <a className="nav-link" href="#rooms">
              Phòng nghỉ
            </a>
          </nav>
        </div>
      </header>

      <main>
                {auth ? (
          <section className="section">
            <div className="container">
              <p role="status">
                Xin chào, {auth.user.first_name || auth.user.username}!
                Bạn đã đăng nhập bằng JWT.
              </p>

              <button
                className="button"
                type="button"
                onClick={() => {
                  setAuth(null)
                  setSelectedRoom(null)
                  setBookingResult(null)
                }}
              >
                Đăng xuất
              </button>
            </div>
          </section>
        ) : (
          <>
            <div className="container">
              <div className="room-actions">
                <button
                  className="button button-secondary"
                  type="button"
                  onClick={() => {
                    setAuthMode('login')
                    setAuthNotice('')
                  }}
                >
                  Đăng nhập
                </button>

                <button
                  className="button button-secondary"
                  type="button"
                  onClick={() => {
                    setAuthMode('register')
                    setAuthNotice('')
                  }}
                >
                  Đăng ký
                </button>
              </div>

              {authNotice && (
                <p className="message message-success" role="status">
                  {authNotice}
                </p>
              )}
            </div>

            {authMode === 'login' ? (
              <LoginForm
                onLogin={(result) => {
                  setAuth(result)
                  setAuthNotice('')
                }}
              />
            ) : (
              <RegisterForm
                onRegistered={(user) => {
                  setAuthMode('login')
                  setAuthNotice(
                    `Đã tạo tài khoản ${user.username}. Bạn có thể đăng nhập.`
                  )
                }}
              />
            )}
          </>
        )}
        {auth && selectedRoom && (
          <BookingForm
            key={selectedRoom.id}
            room={selectedRoom}
            auth={auth}
            criteria={searchCriteria}
            onBooked={(booking) => {
              setBookingResult(booking)
              setSelectedRoom(null)
              window.scrollTo({ top: 0, behavior: 'smooth' })
            }}
            onCancel={() => setSelectedRoom(null)}
          />
        )}

        {auth && bookingResult && (
          <section className="section">
            <div className="container">
              <div className="message message-success" role="status">
                <h2>Đã gửi yêu cầu đặt phòng</h2>
                <p>
                  Mã đặt phòng: <strong>{bookingResult.code}</strong>
                </p>
                <p>Loại phòng: {bookingResult.room_type_name}</p>
                <p>
                  Tổng tiền dự kiến:{' '}
                  {formatPrice(bookingResult.total_price)}
                </p>
                <p>
                  Trạng thái: {bookingResult.status_display}.
                  Yêu cầu chưa phải xác nhận giữ phòng hoặc thanh toán.
                </p>
              </div>
            </div>
          </section>
        )}
        {auth && (
          <MyBookings
            key={auth.user.id}
            accessToken={auth.accessToken}
            refreshKey={bookingResult?.id ?? 0}
          />
        )}
        {detailRoomId !== null ? (
          <RoomDetail
            key={detailRoomId}
            roomId={detailRoomId}
            canBook={Boolean(auth)}
            onBack={() => setDetailRoomId(null)}
            onBook={(room) => {
              setSelectedRoom(room)
              setBookingResult(null)
              setDetailRoomId(null)
              window.scrollTo({ top: 0, behavior: 'smooth' })
            }}
          />
        ) : (
          <>
            <section className="hero">
          <div className="container">
            <p className="eyebrow">CHÀO MỪNG ĐẾN VỚI AN NHIÊN</p>
            <h1>
              Một nơi dừng chân,
              <br />
              một khoảng trời bình yên.
            </h1>
            <p className="hero-copy">
              Khám phá các loại phòng và lựa chọn không gian
              phù hợp cho kỳ nghỉ của bạn.
            </p>
            <a className="button" href="#rooms">
              Khám phá phòng nghỉ
            </a>
            <RoomSearchForm
              onSearch={handleSearch}
              loading={loading}
            />
          </div>
        </section>

        <section className="section" id="rooms">
          <div className="container">
            <div className="section-heading">
              <div>
                <p className="eyebrow">KHÔNG GIAN NGHỈ NGƠI</p>
                <h2>Chọn phòng cho kỳ nghỉ của bạn</h2>
                <p className="muted">
                  Giá tham khảo mỗi đêm. Tình trạng phòng cần
                  được kiểm tra theo ngày lưu trú.
                </p>
              </div>
            </div>

            {loading && <p role="status">Đang tải phòng...</p>}

            {error && (
              <p className="form-errors" role="alert">
                {error}
              </p>
            )}

            {!loading && !error && rooms.length === 0 && (
              <p>Thông tin phòng sẽ sớm được cập nhật.</p>
            )}

            {!loading && !error && (
              <div className="room-grid">
                {rooms.map((room) => (
                  <article className="room-card" key={room.id}>
                    {room.image ? (
                      <img
                        className="room-image"
                        src={room.image}
                        alt={`Không gian ${room.name}`}
                        loading="lazy"
                      />
                    ) : (
                      <div className="room-placeholder">
                        Ảnh phòng đang được cập nhật
                      </div>
                    )}

                    <div className="room-content">
                      <h3>{room.name}</h3>

                      <p className="room-meta">
                        {room.tier_display}
                        {' · '}
                        Tối đa {room.capacity} khách
                      </p>

                      <p className="price">
                        {formatPrice(room.price_per_night)}
                        {' '}
                        <span>/ đêm</span>
                      </p>

                      <p className="muted">
                        {room.description ||
                          'Thông tin phòng đang được cập nhật.'}
                      </p>
                      <div
                        className="room-actions"
                        style={{ display: 'flex', gap: '10px' }}
                      >
                        <button
                          className="button button-secondary"
                          type="button"
                          style={{ flex: 1 }}
                          onClick={() => {
                            setDetailRoomId(room.id)
                            setSelectedRoom(null)
                            setBookingResult(null)
                            window.scrollTo({
                              top: 0,
                              behavior: 'smooth',
                            })
                          }}
                        >
                          Xem chi tiết
                        </button>

                        <button
                          className="button"
                          type="button"
                          style={{ flex: 1 }}
                          disabled={!auth}
                          onClick={() => {
                            setSelectedRoom(room)
                            setDetailRoomId(null)
                            setBookingResult(null)
                            window.scrollTo({
                              top: 0,
                              behavior: 'smooth',
                            })
                          }}
                        >
                          {auth ? 'Chọn phòng' : 'Đăng nhập để đặt'}
                        </button>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </div>
        </section>
          </>
        )}
      </main>

      <footer className="footer">
        <div className="container footer-inner">
          <span className="footer-brand">An Nhiên Hotel</span>
          <p>Không gian nghỉ dưỡng dành cho những ngày thật an nhiên.</p>
          <span>© {new Date().getFullYear()} An Nhiên Hotel</span>
        </div>
      </footer>
    </>
  )
}
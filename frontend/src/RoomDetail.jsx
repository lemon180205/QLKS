import { useEffect, useState } from 'react'

const formatPrice = (value) =>
  new Intl.NumberFormat('vi-VN', {
    style: 'currency',
    currency: 'VND',
  }).format(Number(value))

export default function RoomDetail({
  roomId,
  canBook,
  onBack,
  onBook,
}) {
  const [room, setRoom] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const controller = new AbortController()

    async function loadRoom() {
      setLoading(true)
      setError('')

      try {
        const response = await fetch(`/api/room-types/${roomId}/`, {
          headers: { Accept: 'application/json' },
          signal: controller.signal,
        })

        if (response.status === 404) {
          throw new Error('Loại phòng không còn tồn tại.')
        }

        if (!response.ok) {
          throw new Error('Không tải được thông tin phòng.')
        }

        const data = await response.json()
        setRoom(data)
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

    loadRoom()

    return () => controller.abort()
  }, [roomId])

  return (
    <section className="section">
      <div className="container">
        <button
          className="button button-secondary"
          type="button"
          onClick={onBack}
        >
          ← Quay lại danh sách
        </button>

        {loading && <p role="status">Đang tải thông tin phòng...</p>}

        {error && (
          <p className="form-errors" role="alert">
            {error}
          </p>
        )}

        {!loading && !error && room && (
          <article>
            <p className="eyebrow">NGHỈ NGƠI TẠI AN NHIÊN</p>
            <h1>{room.name}</h1>

            {room.image ? (
              <img
                className="detail-image"
                src={room.image}
                alt={`Không gian ${room.name}`}
              />
            ) : (
              <div className="room-placeholder">
                Ảnh phòng đang được cập nhật
              </div>
            )}

            <p className="room-meta">
              {room.tier_display} · Tối đa {room.capacity} khách
            </p>

            <p className="price">
              {formatPrice(room.price_per_night)} <span>/ đêm</span>
            </p>

            <h2>Thông tin loại phòng</h2>

            <p style={{ whiteSpace: 'pre-line' }}>
              {room.description || 'Thông tin đang được cập nhật.'}
            </p>

            <p className="muted">
              Giá tham khảo mỗi đêm. Khi gửi yêu cầu, hệ thống
              sẽ kiểm tra lại phòng trống theo ngày lưu trú.
            </p>

            <button
              className="button"
              type="button"
              disabled={!canBook}
              onClick={() => onBook(room)}
            >
              {canBook ? 'Chọn phòng này' : 'Đăng nhập để đặt phòng'}
            </button>
          </article>
        )}
      </div>
    </section>
  )
}
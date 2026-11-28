import { useState } from 'react'

export default function RoomSearchForm({ onSearch, loading = false }) {
  const [checkIn, setCheckIn] = useState('')
  const [checkOut, setCheckOut] = useState('')
  const [guestCount, setGuestCount] = useState('2')
  const [error, setError] = useState('')

  function handleSubmit(event) {
    event.preventDefault()
    setError('')

    if (checkOut <= checkIn) {
      setError('Ngày trả phòng phải sau ngày nhận phòng.')
      return
    }

    onSearch({
      check_in: checkIn,
      check_out: checkOut,
      guest_count: guestCount,
    })
  }

  return (
    <form className="booking-search" onSubmit={handleSubmit}>
      <div className="search-panel-heading">
        <div>
          <span className="search-tab">Tìm phòng trống</span>
          <p>Chọn ngày lưu trú và số khách</p>
        </div>
      </div>

      <div className="search-fields">
        <div className="form-field">
          <label htmlFor="search-check-in">Ngày nhận phòng</label>
          <input
            id="search-check-in"
            type="date"
            value={checkIn}
            onChange={(event) => setCheckIn(event.target.value)}
            required
          />
        </div>

        <div className="form-field">
          <label htmlFor="search-check-out">Ngày trả phòng</label>
          <input
            id="search-check-out"
            type="date"
            value={checkOut}
            onChange={(event) => setCheckOut(event.target.value)}
            required
          />
        </div>

        <div className="form-field">
          <label htmlFor="search-guests">Số khách</label>
          <input
            id="search-guests"
            type="number"
            min="1"
            step="1"
            value={guestCount}
            onChange={(event) => setGuestCount(event.target.value)}
            required
          />
        </div>

        <button className="button" type="submit" disabled={loading}>
          {loading ? 'Đang tìm...' : 'Tìm phòng'}
        </button>
      </div>

      {error && (
        <p className="form-errors" role="alert">
          {error}
        </p>
      )}
    </form>
  )
}
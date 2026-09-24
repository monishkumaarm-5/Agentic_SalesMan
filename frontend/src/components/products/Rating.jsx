import { StarIcon } from '../layout/Icons.jsx'

export default function Rating({ value }) {
  if (!value) return null
  return (
    <span className="rating" aria-label={`Rated ${value} out of 5`}>
      <StarIcon width={13} height={13} className="rating-star" />
      {Number(value).toFixed(1)}
    </span>
  )
}

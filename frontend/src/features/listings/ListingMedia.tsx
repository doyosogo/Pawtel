import { mediaFor } from './media';
/** Replace src with real Listing image URLs when storage is implemented. */
export function ListingMedia({
  id,
  className = '',
  src,
  eager = false,
}: {
  id: string;
  className?: string;
  src?: string;
  eager?: boolean;
}) {
  return (
    <div className={`listing-media ${className}`}>
      <img
        src={src ?? mediaFor(id)}
        alt=""
        loading={eager ? 'eager' : 'lazy'}
      />
      <span className="media-label">Demo illustration</span>
    </div>
  );
}

import { useState } from 'react';
import { mediaFor } from './media';
export function ListingMedia({
  id,
  className = '',
  src,
  alt = '',
  eager = false,
}: {
  id: string;
  className?: string;
  src?: string;
  alt?: string;
  eager?: boolean;
}) {
  const [failed, setFailed] = useState<string>();
  const real = !!src && failed !== src;
  return (
    <div className={`listing-media ${className}`}>
      <img
        src={real ? src : mediaFor(id)}
        alt={real ? alt : ''}
        loading={eager ? 'eager' : 'lazy'}
        onError={() => {
          if (real) setFailed(src);
        }}
      />
      {!real && <span className="media-label">Demo illustration</span>}
    </div>
  );
}

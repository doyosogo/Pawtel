import type { Listing } from './api';
import { ListingMedia } from './ListingMedia';
export function ListingGallery({ listing }: { listing: Listing }) {
  const images = listing.images ?? [];
  if (!images.length)
    return (
      <div className="detail-gallery">
        <ListingMedia id={listing.id} eager />
        <ListingMedia id={listing.id + 'second'} eager />
      </div>
    );
  return (
    <div className="uploaded-gallery" aria-label="Listing photos">
      {images.map((image, index) => (
        <ListingMedia
          key={image.id}
          id={listing.id}
          src={image.url}
          alt={image.alt_text || `Accommodation photo ${index + 1}`}
          eager={index === 0}
        />
      ))}
    </div>
  );
}

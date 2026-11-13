import { SHOWCASE } from '../../showcase/mode';
import { useEffect, useRef, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { uploadImage, write } from '../../lib/api';
import { RequestError } from '../account/RequestError';
import { imageOrder, useRefreshHost, type HostListing } from './api';
export function ImageManager({ listing }: { listing: HostListing }) {
  const images = listing.images ?? [];
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState('');
  const input = useRef<HTMLInputElement>(null);
  useEffect(
    () => () => {
      if (preview) URL.revokeObjectURL(preview);
    },
    [preview],
  );
  const [validation, setValidation] = useState('');
  const [message, setMessage] = useState('');
  const refresh = useRefreshHost();
  const mutation = useMutation({
    gcTime: 0,
    mutationFn: async (action: {
      file?: File;
      alt?: string;
      remove?: string;
      move?: number;
      direction?: number;
    }) => {
      if (action.file)
        await uploadImage(listing.id, action.file, action.alt ?? '');
      else if (action.remove) {
        const result = await write<{ cleanup_pending: boolean }>(
          `/host/listings/${listing.id}/images/${action.remove}`,
          {},
          'DELETE',
        );
        if (result.cleanup_pending)
          setMessage(
            'Photo removed from the Listing. Storage cleanup is pending and can be retried by maintenance.',
          );
      } else if (action.move !== undefined) {
        const next = [...images];
        const target = action.move + (action.direction ?? 0);
        [next[action.move], next[target]] = [next[target], next[action.move]];
        await imageOrder(listing.id, next);
      }
    },
    onSuccess: async (_data, action) => {
      if (action.file) {
        setFile(null);
        setPreview('');
        if (input.current) input.current.value = '';
      }
      await refresh();
    },
    onError: refresh,
  });
  return (
    <section className="workspace-panel" aria-labelledby="photos-title">
      <h2 id="photos-title">Listing photos</h2>
      <p>
        Up to six JPEG, PNG or WebP photos, 5 MiB each, 200–6000 pixels per side
        and at most 24 megapixels. Animated images are not supported. First
        photo is the cover.
      </p>
      {SHOWCASE && (
        <p className="notice">
          Cloud upload is available in the full-stack implementation. These
          bundled illustrations can be reordered or removed locally.
        </p>
      )}
      <form
        className="stack"
        onSubmit={(e) => {
          e.preventDefault();
          const form = new FormData(e.currentTarget);
          if (
            !file?.size ||
            !['image/jpeg', 'image/png', 'image/webp'].includes(file.type)
          ) {
            setValidation('Choose a JPEG, PNG or WebP image.');
            return;
          }
          if (file.size > 5 * 1024 * 1024) {
            setValidation('Photo must be at most 5 MiB.');
            return;
          }
          setValidation('');
          setMessage('');
          mutation.mutate({ file, alt: String(form.get('alt')).trim() });
        }}
      >
        <label className="field">
          Choose photo
          <input
            name="photo"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            required
            ref={input}
            onChange={(e) => {
              const next = e.currentTarget.files?.[0] ?? null;
              setFile(next);
              setPreview(
                next &&
                  ['image/jpeg', 'image/png', 'image/webp'].includes(
                    next.type,
                  ) &&
                  next.size <= 5 * 1024 * 1024 &&
                  URL.createObjectURL
                  ? URL.createObjectURL(next)
                  : '',
              );
            }}
            disabled={SHOWCASE || mutation.isPending || images.length >= 6}
          />
        </label>
        <label className="field">
          Photo description (optional)
          <input name="alt" maxLength={160} />
        </label>
        <button
          className="button"
          disabled={SHOWCASE || mutation.isPending || images.length >= 6}
        >
          {mutation.isPending ? 'Updating photos…' : 'Upload photo'}
        </button>
      </form>
      {preview && (
        <img
          className="upload-preview"
          src={preview}
          alt="Selected photo preview"
        />
      )}
      {validation && (
        <p className="error-text" role="alert">
          {validation}
        </p>
      )}
      {mutation.isError && <RequestError error={mutation.error} />}
      <p role="status">
        {message || (mutation.isSuccess ? 'Photos updated.' : '')}
      </p>
      <div className="workspace-grid photo-manager">
        {images.map((image, index) => (
          <article key={image.id}>
            <img src={image.url} alt={image.alt_text || 'Listing photo'} />
            <p>{index === 0 ? 'Cover photo' : `Photo ${index + 1}`}</p>
            <div className="action-row">
              <button
                className="button secondary small"
                disabled={mutation.isPending || index === 0}
                aria-label={`Move photo ${index + 1} earlier`}
                onClick={() => mutation.mutate({ move: index, direction: -1 })}
              >
                Move earlier
              </button>
              <button
                className="button secondary small"
                disabled={mutation.isPending || index === images.length - 1}
                aria-label={`Move photo ${index + 1} later`}
                onClick={() => mutation.mutate({ move: index, direction: 1 })}
              >
                Move later
              </button>
              <button
                className="button secondary small"
                disabled={mutation.isPending}
                aria-label={`Remove photo ${index + 1}`}
                onClick={() => mutation.mutate({ remove: image.id })}
              >
                Remove
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

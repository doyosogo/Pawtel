import { useMutation } from '@tanstack/react-query';
import { write } from '../../lib/api';
import { useRefreshHost } from './api';
import { RequestError } from '../account/RequestError';
export function HostProfileForm({
  bio,
  onboard = false,
}: {
  bio?: string | null;
  onboard?: boolean;
}) {
  const refresh = useRefreshHost();
  const mutation = useMutation({
    mutationFn: (bio: string | null) =>
      write('/host/profile', { bio }, onboard ? 'POST' : 'PATCH'),
    onSuccess: refresh,
    onError: refresh,
  });
  return (
    <section className="workspace-panel">
      <h2>{onboard ? 'Become a Host' : 'Your Host profile'}</h2>
      {onboard && (
        <p>
          You do not have a Host profile yet. Welcome pets with the same PAWTEL
          account you use to book stays.
        </p>
      )}
      <form
        className="stack"
        onSubmit={(e) => {
          e.preventDefault();
          const form = new FormData(e.currentTarget);
          mutation.mutate(String(form.get('bio')).trim() || null);
        }}
      >
        <label className="field">
          Host bio (optional)
          <textarea
            name="bio"
            maxLength={2000}
            rows={5}
            defaultValue={bio ?? ''}
          />
        </label>
        <button className="button" disabled={mutation.isPending}>
          {mutation.isPending
            ? 'Saving…'
            : onboard
              ? 'Become a Host'
              : 'Save bio'}
        </button>
        {mutation.isError && <RequestError error={mutation.error} />}
        {mutation.isSuccess && <p role="status">Host profile saved.</p>}
      </form>
    </section>
  );
}

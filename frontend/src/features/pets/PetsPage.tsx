import { useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { archivePet, savePet, usePets, type Pet, type PetInput } from './api';
import { RequestError } from '../account/RequestError';

function PetForm({
  pet,
  done,
}: {
  pet?: Pet;
  done: (saved?: boolean) => void;
}) {
  const client = useQueryClient();
  const [validation, setValidation] = useState('');
  const mutation = useMutation({
    mutationFn: (data: PetInput) => savePet(data, pet?.id),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['pets'] });
      done(true);
    },
  });
  function submit(event: React.SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if (mutation.isPending) return;
    const form = new FormData(event.currentTarget);
    const name = String(form.get('name')).trim();
    const birth = String(form.get('date_of_birth'));
    if (!name || (birth && birth > new Date().toISOString().slice(0, 10))) {
      setValidation(
        'Enter a name and a date of birth that is not in the future.',
      );
      return;
    }
    setValidation('');
    mutation.mutate({
      name,
      species: form.get('species') as PetInput['species'],
      breed: String(form.get('breed')).trim() || null,
      date_of_birth: birth || null,
    });
  }
  return (
    <section className="workspace-panel" aria-labelledby="pet-form-title">
      <h2 id="pet-form-title">{pet ? `Edit ${pet.name}` : 'Add a pet'}</h2>
      <form className="stack" onSubmit={submit}>
        <label className="field">
          Pet name
          <input
            name="name"
            required
            maxLength={80}
            defaultValue={pet?.name}
            autoFocus
          />
        </label>
        <label className="field">
          Species
          <select name="species" defaultValue={pet?.species ?? 'DOG'}>
            <option value="DOG">Dog</option>
            <option value="CAT">Cat</option>
          </select>
        </label>
        <label className="field">
          Breed (optional)
          <input name="breed" maxLength={100} defaultValue={pet?.breed ?? ''} />
        </label>
        <label className="field">
          Date of birth (optional)
          <input
            name="date_of_birth"
            type="date"
            max={new Date().toISOString().slice(0, 10)}
            defaultValue={pet?.date_of_birth ?? ''}
          />
        </label>
        {validation && (
          <p role="alert" className="error-text">
            {validation}
          </p>
        )}
        {mutation.isError && <RequestError error={mutation.error} />}
        <div className="action-row">
          <button className="button" disabled={mutation.isPending}>
            {mutation.isPending ? 'Saving…' : 'Save pet'}
          </button>
          <button
            type="button"
            className="button secondary"
            onClick={() => done()}
            disabled={mutation.isPending}
          >
            Close form
          </button>
        </div>
      </form>
    </section>
  );
}
export function PetsPage() {
  const [params] = useSearchParams();
  const next = params.get('next');
  const safeNext =
    next?.startsWith('/stays/') && !next.includes('\\') ? next : null;
  const [archived, setArchived] = useState(false);
  const query = usePets(archived);
  const [editing, setEditing] = useState<Pet | 'new' | null>(null);
  const [confirm, setConfirm] = useState<Pet | null>(null);
  const [notice, setNotice] = useState('');
  const add = useRef<HTMLButtonElement>(null);
  const client = useQueryClient();
  const archive = useMutation({
    mutationFn: archivePet,
    onSuccess: async () => {
      setConfirm(null);
      setNotice('Pet archived. Existing booking history is preserved.');
      await client.invalidateQueries({ queryKey: ['pets'] });
      await client.invalidateQueries({ queryKey: ['bookings'] });
      add.current?.focus();
    },
  });
  function close(saved = false) {
    setEditing(null);
    setNotice(saved ? 'Pet details updated.' : '');
    add.current?.focus();
  }
  return (
    <>
      <p className="eyebrow">YOUR COMPANIONS</p>
      <h1>My Pets</h1>
      <p>
        Keep their details ready for their next stay. Archived pets cannot be
        selected for new bookings.
      </p>
      {safeNext && (
        <Link className="text-link" to={safeNext}>
          Return to your stay →
        </Link>
      )}
      <div className="action-row">
        <button
          ref={add}
          className="button"
          onClick={() => {
            setEditing('new');
            setNotice('');
          }}
        >
          Add a pet
        </button>
        <label>
          <input
            type="checkbox"
            checked={archived}
            onChange={(e) => setArchived(e.target.checked)}
          />{' '}
          Show archived pets
        </label>
      </div>
      {notice && <p role="status">{notice}</p>}
      {editing && (
        <PetForm
          key={editing === 'new' ? 'new' : editing.id}
          pet={editing === 'new' ? undefined : editing}
          done={close}
        />
      )}
      {query.isPending ? (
        <p role="status">Loading pets…</p>
      ) : query.isError ? (
        <RequestError error={query.error} retry={() => void query.refetch()} />
      ) : !query.data.length ? (
        <p className="notice">
          No pets yet. Add your dog or cat to request a stay.
        </p>
      ) : (
        <div className="workspace-grid">
          {query.data.map((pet) => (
            <article className="workspace-panel" key={pet.id}>
              <h2>{pet.name}</h2>
              <p>
                {pet.species === 'DOG' ? 'Dog' : 'Cat'}
                {pet.breed ? ` · ${pet.breed}` : ''}
              </p>
              {pet.date_of_birth && <p>Born {pet.date_of_birth}</p>}
              <p>{pet.is_active ? 'Active' : 'Archived'}</p>
              {pet.is_active && (
                <div className="action-row">
                  <button
                    className="button secondary small"
                    onClick={() => {
                      setEditing(pet);
                      setNotice('');
                    }}
                  >
                    Edit {pet.name}
                  </button>
                  <button
                    className="button secondary small"
                    onClick={() => {
                      setConfirm(pet);
                      archive.reset();
                    }}
                  >
                    Archive {pet.name}
                  </button>
                </div>
              )}
              {confirm?.id === pet.id && (
                <div className="notice">
                  <p>
                    Archive {pet.name}? This removes them from future booking
                    selection and may prevent a pending request from being
                    accepted. Booking history remains.
                  </p>
                  <div className="action-row">
                    <button
                      className="button small"
                      disabled={archive.isPending}
                      onClick={() => archive.mutate(pet.id)}
                    >
                      Confirm archive
                    </button>
                    <button
                      className="button secondary small"
                      disabled={archive.isPending}
                      onClick={() => setConfirm(null)}
                    >
                      Keep pet
                    </button>
                  </div>
                  {archive.isError && <RequestError error={archive.error} />}
                </div>
              )}
            </article>
          ))}
        </div>
      )}
    </>
  );
}

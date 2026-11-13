// Two explicit public build inputs; ordinary dev/production stays connected to FastAPI.
export const SHOWCASE =
  import.meta.env.MODE === 'showcase' &&
  import.meta.env.VITE_PAWTEL_SHOWCASE === 'true';

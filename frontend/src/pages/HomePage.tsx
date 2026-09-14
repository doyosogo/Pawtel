export function HomePage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-6 py-12 text-slate-900">
      <section className="w-full max-w-2xl rounded-2xl border border-slate-200 bg-white p-8 sm:p-12">
        <p className="mb-4 text-sm font-medium text-teal-700">
          Foundation milestone
        </p>
        <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
          PAWTEL
        </h1>
        <p className="mt-5 text-xl">Pet boarding across Australia.</p>
        <p className="mt-4 leading-relaxed text-slate-600">
          A new home for trusted stays for dogs and cats. We are building the
          foundations; marketplace features are coming in later milestones.
        </p>
      </section>
    </main>
  );
}

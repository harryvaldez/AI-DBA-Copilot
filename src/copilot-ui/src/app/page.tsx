export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center px-6 py-16">
      <p className="font-[family-name:var(--font-plex-mono)] text-sm tracking-[0.2em] text-sky-400 uppercase">
        Operations platform
      </p>
      <h1 className="mt-4 font-[family-name:var(--font-plex-sans)] text-5xl font-semibold tracking-tight text-slate-50">
        AI DBA Copilot
      </h1>
      <p className="mt-4 max-w-xl text-lg text-slate-300">
        Detect anomalies, generate RCA recommendations, and manage incidents with institutional
        memory across your SQL Server estate.
      </p>
      <div className="mt-10 flex gap-4">
        <a
          href="/health"
          className="rounded bg-sky-500 px-5 py-2.5 text-sm font-medium text-slate-950 transition hover:bg-sky-400"
        >
          Health check
        </a>
      </div>
    </main>
  );
}

"use client";

interface Props {
  canGenerate: boolean;
  busy: boolean;
  progress: number;
  nameCount: number;
  readyCount: number | null;
  error: string | null;
  onGenerate: () => void;
  onDownload: () => void;
}

export default function GeneratePanel({
  canGenerate,
  busy,
  progress,
  nameCount,
  readyCount,
  error,
  onGenerate,
  onDownload,
}: Props) {
  const percent = Math.round(progress * 100);
  const ready = readyCount !== null && !busy;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-center gap-3">
        <button
          type="button"
          onClick={onGenerate}
          disabled={!canGenerate || busy}
          className="rounded-xl bg-accent-600 px-8 py-3 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-accent-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {busy ? "Generating…" : "Generate Certificates"}
        </button>

        {ready ? (
          <button
            type="button"
            onClick={onDownload}
            className="rounded-xl border border-accent-600 bg-white px-8 py-3 text-sm font-semibold text-accent-700 shadow-sm transition-colors hover:bg-accent-50"
          >
            Download ZIP ({readyCount})
          </button>
        ) : null}
      </div>

      {busy ? (
        <div className="mx-auto max-w-md space-y-2">
          <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-200">
            <div
              className="h-full rounded-full bg-accent-600 transition-[width] duration-200"
              style={{ width: `${percent}%` }}
            />
          </div>
          <p className="text-center text-xs tabular-nums text-slate-600">
            Generating certificates… (estimate) {percent}% ·{" "}
            {Math.min(Math.round(progress * nameCount), nameCount)} / {nameCount}
          </p>

        </div>
      ) : null}

      {!busy && ready ? (
        <p className="text-center text-sm text-emerald-700">
          {readyCount} certificate{readyCount === 1 ? "" : "s"} generated and
          packed into certificates.zip.
        </p>
      ) : null}

      {error ? (
        <p className="mx-auto max-w-md text-center text-sm text-red-600">
          {error}
        </p>
      ) : null}
    </div>
  );
}

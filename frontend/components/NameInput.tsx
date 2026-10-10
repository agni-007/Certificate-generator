"use client";

import { useRef, useState } from "react";

interface Props {
  value: string;
  maxNames: number;
  busy: boolean;
  error: string | null;
  onChange: (value: string) => void;
  onFile: (file: File) => void;
}

export default function NameInput({
  value,
  maxNames,
  busy,
  error,
  onChange,
  onFile,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const lines = value.split("\n").map((line) => line.trim()).filter(Boolean);
  const overLimit = count > maxNames;
  return (
    <div className="space-y-3">
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        rows={7}
        spellCheck={false}
        placeholder={"Agnivesh S\nRahul Kumar\nAnanya Menon\nArjun Raj"}
        className="w-full resize-y rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-accent-600 focus:outline-none focus:ring-2 focus:ring-accent-100"
      />

      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs text-slate-500">
          One name per line ·{" "}
          {count > 0 ? `${count} of ${maxNames} names` : `max ${maxNames} names`}
        </span>

        <div
          role="button"
          tabIndex={0}
          onClick={() => inputRef.current?.click()}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              inputRef.current?.click();
            }
          }}
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            const file = event.dataTransfer.files?.[0];
            if (file) onFile(file);
          }}
          className={`cursor-pointer rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
            dragging
              ? "border-accent-600 bg-accent-50 text-accent-700"
              : "border-slate-300 bg-white text-slate-700 hover:border-slate-400"
          }`}
        >
          {busy ? "Reading file…" : "Upload Excel / CSV"}
        </div>
        <input
          ref={inputRef}
          type="file"
          accept=".xlsx,.csv"
          className="hidden"
          onClick={(event) => event.stopPropagation()}
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) onFile(file);
            event.target.value = "";
          }}
        />
      </div>

      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {overLimit ? (
        <p className="text-sm text-red-600">
          Too many names. Please keep to {maxNames} names or fewer.
        </p>
      ) : null}
    </div>
  );
}

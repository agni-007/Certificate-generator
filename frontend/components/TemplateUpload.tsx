"use client";

import { useRef, useState } from "react";

interface Props {
  file: File | null;
  previewUrl: string | null;
  busy: boolean;
  error: string | null;
  maxTemplateSizeMb: number;
  onSelect: (file: File) => void;
  onClear: () => void;
}

export default function TemplateUpload({
  file,
  previewUrl,
  busy,
  error,
  maxTemplateSizeMb,
  onSelect,
  onClear,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const accept = (files: FileList | null) => {
    const picked = files?.[0];
    if (picked) onSelect(picked);
  };

  if (previewUrl && file) {
    return (
      <div>
        <div className="relative overflow-hidden rounded-xl border border-slate-200 bg-white">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={previewUrl}
            alt={file.name}
            className="certificate-surface mx-auto max-h-72 w-auto max-w-full"
          />
          <div className="absolute inset-x-0 bottom-0 flex items-center justify-between gap-3 bg-gradient-to-t from-slate-900/80 to-transparent px-3 pb-2 pt-6">
            <span className="truncate text-xs text-white">{file.name}</span>
            <div className="flex shrink-0 gap-2">
              <button
                type="button"
                onClick={() => inputRef.current?.click()}
                className="rounded-md bg-white/95 px-2.5 py-1 text-xs font-medium text-slate-900 hover:bg-white"
              >
                Replace
              </button>
              <button
                type="button"
                onClick={onClear}
                className="rounded-md bg-white/20 px-2.5 py-1 text-xs font-medium text-white hover:bg-white/30"
              >
                Remove
              </button>
            </div>
          </div>
        </div>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.png,.jpg,.jpeg"
          className="hidden"
          onChange={(event) => {
            accept(event.target.files);
            event.target.value = "";
          }}
        />
      </div>
    );
  }

  return (
    <div>
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
          accept(event.dataTransfer.files);
        }}
        className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors ${
          dragging
            ? "border-accent-600 bg-accent-50"
            : "border-slate-300 bg-white hover:border-slate-400"
        }`}
      >
        <span className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-100 text-lg text-slate-500">
          {busy ? "…" : "↑"}
        </span>
        <span className="text-sm font-medium text-slate-700">
          {busy ? "Loading template…" : "Upload certificate template"}
        </span>
        <span className="text-xs text-slate-500">
          Drag and drop or click · PDF, PNG, JPG, JPEG · up to{" "}
          {maxTemplateSizeMb} MB
        </span>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.png,.jpg,.jpeg"
          className="hidden"
          onClick={(event) => event.stopPropagation()}
          onChange={(event) => {
            accept(event.target.files);
            event.target.value = "";
          }}
        />
      </div>
      {error ? <p className="mt-2 text-sm text-red-600">{error}</p> : null}
    </div>
  );
}

"use client";

import type { ApiOptions, TextStyle } from "@/lib/api";

interface Props {
  style: TextStyle;
  options: ApiOptions | null;
  onChange: (patch: Partial<TextStyle>) => void;
}

const PRESET_COLORS = ["#ffffff", "#111827", "#b91c1c", "#1d4ed8", "#b45309"];

export default function TextSettings({ style, options, onChange }: Props) {
  const fonts = options?.fonts ?? [
    { value: style.font, label: style.font },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <label className="block space-y-1.5">
        <span className="text-xs font-medium text-slate-600">Font</span>
        <select
          value={style.font}
          onChange={(event) => onChange({ font: event.target.value })}
          className="w-full rounded-lg border border-slate-300 bg-white px-2.5 py-2 text-sm focus:border-accent-600 focus:outline-none focus:ring-2 focus:ring-accent-100"
        >
          {fonts.map((font) => (
            <option key={font.value} value={font.value}>
              {font.label}
            </option>
          ))}
        </select>
      </label>

      <label className="block space-y-1.5">
        <span className="text-xs font-medium text-slate-600">Font size</span>
        <div className="flex items-center gap-2">
          <input
            type="number"
            min={6}
            max={200}
            value={style.fontSize}
            onChange={(event) => {
              const size = Number(event.target.value);
              if (!Number.isNaN(size)) onChange({ fontSize: size });
            }}
            className="w-20 rounded-lg border border-slate-300 bg-white px-2.5 py-2 text-sm focus:border-accent-600 focus:outline-none focus:ring-2 focus:ring-accent-100"
          />
          <input
            type="range"
            min={6}
            max={200}
            value={style.fontSize}
            onChange={(event) => onChange({ fontSize: Number(event.target.value) })}
            className="w-full accent-indigo-600"
          />
        </div>
      </label>

      <div className="space-y-1.5">
        <span className="text-xs font-medium text-slate-600">Colour</span>
        <div className="flex items-center gap-2">
          <input
            type="color"
            value={style.color}
            onChange={(event) => onChange({ color: event.target.value })}
            className="h-9 w-10 cursor-pointer rounded-lg border border-slate-300 bg-white p-1"
            aria-label="Text colour"
          />
          <div className="flex gap-1.5">
            {PRESET_COLORS.map((color) => (
              <button
                key={color}
                type="button"
                aria-label={`Use colour ${color}`}
                onClick={() => onChange({ color })}
                className={`h-6 w-6 rounded-full border ${
                  style.color.toLowerCase() === color
                    ? "ring-2 ring-accent-600 ring-offset-1"
                    : "border-slate-300"
                }`}
                style={{ backgroundColor: color }}
              />
            ))}
          </div>
        </div>
      </div>

      <div className="space-y-1.5">
        <span className="text-xs font-medium text-slate-600">Alignment</span>
        <div className="inline-flex w-full overflow-hidden rounded-lg border border-slate-300 bg-white">
          {(options?.alignments ?? ["left", "center", "right"]).map(
            (alignment) => (
              <button
                key={alignment}
                type="button"
                onClick={() =>
                  onChange({ alignment: alignment as TextStyle["alignment"] })
                }
                className={`flex-1 px-2 py-2 text-sm capitalize transition-colors ${
                  style.alignment === alignment
                    ? "bg-accent-600 text-white"
                    : "text-slate-600 hover:bg-slate-50"
                }`}
              >
                {alignment}
              </button>
            ),
          )}
        </div>
      </div>
    </div>
  );
}

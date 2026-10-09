"use client";

import type { ApiOptions, TextStyle } from "@/lib/api";

interface Props {
  style: TextStyle;
  options: ApiOptions | null;
  onChange: (patch: Partial<TextStyle>) => void;
}

const PRESET_COLORS = ["#ffffff", "#111827", "#b91c1c", "#1d4ed8", "#b45309"];

const ALIGN_ICONS: Record<string, string> = {
  left: "⬤◯◯",
  center: "◯⬤◯",
  right: "◯◯⬤",
};

export default function TextSettings({ style, options, onChange }: Props) {
  const fonts = options?.fonts ?? [{ value: style.font, label: style.font }];

  return (
    <div className="space-y-4">
      {/* Row 1: Font + Font Size */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {/* Font selector */}
        <label className="block space-y-1.5">
          <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">
            Font
          </span>
          <select
            value={style.font}
            onChange={(event) => onChange({ font: event.target.value })}
            className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-100"
          >
            {fonts.map((font) => (
              <option key={font.value} value={font.value}>
                {font.label}
              </option>
            ))}
          </select>
        </label>

        {/* Font size stepper */}
        <div className="space-y-1.5">
          <span className="block text-xs font-medium text-slate-500 uppercase tracking-wider">
            Font Size
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              aria-label="Decrease font size"
              onClick={() =>
                onChange({ fontSize: Math.max(6, style.fontSize - 1) })
              }
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-slate-200 bg-white text-lg font-semibold text-slate-600 shadow-sm transition hover:bg-slate-50 active:scale-95"
            >
              −
            </button>
            <input
              type="number"
              min={6}
              max={200}
              value={style.fontSize}
              onChange={(event) => {
                const size = Number(event.target.value);
                if (!Number.isNaN(size) && size >= 6 && size <= 200)
                  onChange({ fontSize: size });
              }}
              className="w-16 rounded-lg border border-slate-200 bg-white py-2 text-center text-sm font-semibold text-slate-800 shadow-sm focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-100"
            />
            <button
              type="button"
              aria-label="Increase font size"
              onClick={() =>
                onChange({ fontSize: Math.min(200, style.fontSize + 1) })
              }
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-slate-200 bg-white text-lg font-semibold text-slate-600 shadow-sm transition hover:bg-slate-50 active:scale-95"
            >
              +
            </button>
            <input
              type="range"
              min={6}
              max={200}
              value={style.fontSize}
              onChange={(event) =>
                onChange({ fontSize: Number(event.target.value) })
              }
              className="flex-1 accent-indigo-600"
            />
          </div>
        </div>
      </div>

      {/* Row 2: Colour + Alignment */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {/* Colour picker */}
        <div className="space-y-1.5">
          <span className="block text-xs font-medium text-slate-500 uppercase tracking-wider">
            Colour
          </span>
          <div className="flex items-center gap-3">
            <input
              type="color"
              value={style.color}
              onChange={(event) => onChange({ color: event.target.value })}
              className="h-9 w-10 shrink-0 cursor-pointer rounded-lg border border-slate-200 bg-white p-1 shadow-sm"
              aria-label="Pick text colour"
            />
            <div className="flex flex-wrap gap-1.5">
              {PRESET_COLORS.map((color) => (
                <button
                  key={color}
                  type="button"
                  aria-label={`Use colour ${color}`}
                  onClick={() => onChange({ color })}
                  className={`h-7 w-7 rounded-full border-2 transition ${
                    style.color.toLowerCase() === color
                      ? "border-indigo-500 ring-2 ring-indigo-300 ring-offset-1 scale-110"
                      : "border-slate-200 hover:scale-105"
                  }`}
                  style={{ backgroundColor: color }}
                />
              ))}
            </div>
          </div>
        </div>

        {/* Alignment */}
        <div className="space-y-1.5">
          <span className="block text-xs font-medium text-slate-500 uppercase tracking-wider">
            Alignment
          </span>
          <div className="grid grid-cols-3 divide-x divide-slate-200 overflow-hidden rounded-lg border border-slate-200 shadow-sm">
            {(["left", "center", "right"] as const).map((alignment) => (
              <button
                key={alignment}
                type="button"
                onClick={() => onChange({ alignment })}
                title={`Align ${alignment}`}
                className={`flex flex-col items-center gap-0.5 py-2 px-1 text-[11px] font-semibold capitalize transition-colors ${
                  style.alignment === alignment
                    ? "bg-indigo-600 text-white"
                    : "bg-white text-slate-500 hover:bg-slate-50"
                }`}
              >
                <span className="text-base leading-none">
                  {ALIGN_ICONS[alignment]}
                </span>
                {alignment}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

"use client";

import { useEffect, useRef, useState } from "react";
import type { TextStyle } from "@/lib/api";

const FONT_STACKS: Record<string, string> = {
  times: '"Times New Roman", Times, serif',
  "times-italic": 'italic "Times New Roman", Times, serif',
  "times-bold": 'bold "Times New Roman", Times, serif',
  "times-bolditalic": 'bold italic "Times New Roman", Times, serif',
  helvetica: "Helvetica, Arial, sans-serif",
  "helvetica-bold": "bold Helvetica, Arial, sans-serif",
  "helvetica-oblique": "oblique Helvetica, Arial, sans-serif",
  "helvetica-boldoblique": "bold oblique Helvetica, Arial, sans-serif",
  courier: '"Courier New", Courier, monospace',
  "courier-bold": 'bold "Courier New", Courier, monospace',
  "courier-oblique": 'oblique "Courier New", Courier, monospace',
  "courier-boldoblique": 'bold oblique "Courier New", Courier, monospace',
};

export function fontStack(font: string): string {
  return FONT_STACKS[font] ?? FONT_STACKS["times-italic"];
}

interface Props {
  url: string | null;
  pageWidth: number;
  pageHeight: number;
  sampleName: string;
  style: TextStyle;
  onPosition: (x: number, y: number) => void;
}

const clamp = (value: number, low: number, high: number) =>
  Math.max(low, Math.min(high, value));

const STEP = 0.5;

export default function CertificatePreview({
  url,
  pageWidth,
  pageHeight,
  sampleName,
  style,
  onPosition,
}: Props) {
  const surfaceRef = useRef<HTMLDivElement>(null);
  const draggingRef = useRef(false);
  const [canvasWidth, setCanvasWidth] = useState(0);

  useEffect(() => {
    const element = surfaceRef.current;
    if (!element) return;
    const observer = new ResizeObserver((entries) => {
      setCanvasWidth(entries[0].contentRect.width);
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [url]);

  if (!url) {
    return (
      <div className="flex aspect-[4/3] items-center justify-center rounded-xl border-2 border-dashed border-slate-200 bg-slate-50 px-6 text-center">
        <div className="space-y-1">
          <p className="text-sm font-medium text-slate-500">
            Certificate preview
          </p>
          <p className="text-xs text-slate-400">
            Upload a template to see it here, then drag or nudge the name into
            position.
          </p>
        </div>
      </div>
    );
  }

  const scale = canvasWidth > 0 && pageWidth > 0 ? canvasWidth / pageWidth : 1;
  const fontSizePx = Math.max(1, style.fontSize * scale);

  // Mirror the backend's per-name centering:
  // X is always the ANCHOR. For "center", the text element itself is centred on
  // that anchor. Because CSS text-align doesn't help here (it aligns inside the
  // container, not the anchor), we use transform translateX to shift the element
  // so its own centre / left-edge / right-edge sits exactly on the anchor point.
  const translateX =
    style.alignment === "center"
      ? "-50%"
      : style.alignment === "right"
        ? "-100%"
        : "0%";

  const moveFromPointer = (clientX: number, clientY: number) => {
    const surface = surfaceRef.current;
    if (!surface) return;
    const rect = surface.getBoundingClientRect();
    onPosition(
      clamp(((clientX - rect.left) / rect.width) * 100, 0, 100),
      clamp(((clientY - rect.top) / rect.height) * 100, 0, 100),
    );
  };

  return (
    <div className="space-y-3">
      {/* ─── Canvas ─── */}
      <div
        ref={surfaceRef}
        className="relative overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm"
        style={{ aspectRatio: `${pageWidth} / ${pageHeight || 1}` }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={url}
          alt="Certificate template preview"
          draggable={false}
          className="absolute inset-0 h-full w-full object-contain"
        />

        {/* Draggable name label — exactly mirrors how the backend places it */}
        <div
          role="slider"
          tabIndex={0}
          aria-label="Name position"
          aria-valuenow={Math.round(style.y)}
          onPointerDown={(event) => {
            event.preventDefault();
            draggingRef.current = true;
            (event.currentTarget as HTMLElement).setPointerCapture(
              event.pointerId,
            );
          }}
          onPointerMove={(event) => {
            if (draggingRef.current)
              moveFromPointer(event.clientX, event.clientY);
          }}
          onPointerUp={(event) => {
            draggingRef.current = false;
            (event.currentTarget as HTMLElement).releasePointerCapture(
              event.pointerId,
            );
          }}
          onPointerCancel={() => {
            draggingRef.current = false;
          }}
          onKeyDown={(event) => {
            const step = event.shiftKey ? 2 : STEP;
            const map: Record<string, [number, number]> = {
              ArrowLeft: [-step, 0],
              ArrowRight: [step, 0],
              ArrowUp: [0, -step],
              ArrowDown: [0, step],
            };
            const delta = map[event.key];
            if (!delta) return;
            event.preventDefault();
            onPosition(
              clamp(style.x + delta[0], 0, 100),
              clamp(style.y + delta[1], 0, 100),
            );
          }}
          className="absolute cursor-move outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
          style={{
            left: `${style.x}%`,
            top: `${style.y}%`,
            transform: `translate(${translateX}, -50%)`,
            touchAction: "none",
            userSelect: "none",
            // Subtle drop-shadow so text is visible on any background
            filter: "drop-shadow(0 1px 2px rgba(0,0,0,0.45))",
          }}
        >
          <span
            className="block whitespace-nowrap"
            style={{
              fontFamily: fontStack(style.font),
              fontSize: `${fontSizePx}px`,
              color: style.color,
              textAlign: style.alignment,
            }}
          >
            {sampleName}
          </span>
        </div>
      </div>

      {/* ─── Info bar ─── */}
      <div className="flex items-center justify-between gap-2 text-xs text-slate-400">
        <span>Drag the name or use the controls below · arrow keys to nudge</span>
        <span className="shrink-0 font-mono text-slate-600">
          X {style.x.toFixed(1)}% · Y {style.y.toFixed(1)}%
        </span>
      </div>

      {/* ─── D-Pad controls ─── */}
      <div className="rounded-xl border border-slate-100 bg-slate-50 p-3">
        <p className="mb-2 text-center text-[10px] font-semibold uppercase tracking-widest text-slate-400">
          Position
        </p>

        {/* Top row: Up button centred */}
        <div className="flex justify-center">
          <NudgeButton
            label="Move up"
            icon="▲"
            onClick={() => onPosition(style.x, clamp(style.y - STEP, 0, 100))}
          />
        </div>

        {/* Middle row: Left · Center · Right */}
        <div className="my-1.5 flex items-center justify-center gap-2">
          <NudgeButton
            label="Move left"
            icon="◀"
            onClick={() => onPosition(clamp(style.x - STEP, 0, 100), style.y)}
          />

          {/* Center button — snaps to horizontal & vertical center */}
          <button
            type="button"
            aria-label="Snap to centre"
            title="Snap to centre (X 50%, Y 52%)"
            onClick={() => onPosition(50, 52)}
            className="h-9 rounded-lg border border-indigo-200 bg-indigo-50 px-3 text-xs font-semibold text-indigo-700 shadow-sm transition hover:bg-indigo-100 active:scale-95"
          >
            ⊕ Center
          </button>

          <NudgeButton
            label="Move right"
            icon="▶"
            onClick={() => onPosition(clamp(style.x + STEP, 0, 100), style.y)}
          />
        </div>

        {/* Bottom row: Down button centred */}
        <div className="flex justify-center">
          <NudgeButton
            label="Move down"
            icon="▼"
            onClick={() => onPosition(style.x, clamp(style.y + STEP, 0, 100))}
          />
        </div>

        <p className="mt-2 text-center text-[10px] text-slate-400">
          Each click moves 0.5% · Hold Shift + arrow key for 2%
        </p>
      </div>
    </div>
  );
}

function NudgeButton({
  label,
  icon,
  onClick,
}: {
  label: string;
  icon: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-sm text-slate-600 shadow-sm transition hover:bg-slate-100 active:scale-95"
    >
      {icon}
    </button>
  );
}

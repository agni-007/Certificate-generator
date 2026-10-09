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
  "helvetica-boldoblique":
    "bold oblique Helvetica, Arial, sans-serif",
  courier: '"Courier New", Courier, monospace',
  "courier-bold": 'bold "Courier New", Courier, monospace',
  "courier-oblique": 'oblique "Courier New", Courier, monospace',
  "courier-boldoblique":
    'bold oblique "Courier New", Courier, monospace',
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
  const [width, setWidth] = useState(0);

  useEffect(() => {
    const element = surfaceRef.current;
    if (!element) return;
    const observer = new ResizeObserver((entries) => {
      setWidth(entries[0].contentRect.width);
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [url]);

  if (!url) {
    return (
      <div className="flex aspect-[4/3] items-center justify-center rounded-xl border-2 border-dashed border-slate-300 bg-white px-6 text-center">
        <div className="space-y-1">
          <p className="text-sm font-medium text-slate-600">
            Certificate preview
          </p>
          <p className="text-xs text-slate-500">
            Upload a template to see it here, then drag the name into place.
          </p>
        </div>
      </div>
    );
  }

  const scale = width > 0 && pageWidth > 0 ? width / pageWidth : 1;
  const fontSizePx = Math.max(1, style.fontSize * scale);
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
    <div className="space-y-2">
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
          className="certificate-surface absolute inset-0 h-full w-full object-contain"
        />

        <div
          role="slider"
          tabIndex={0}
          aria-label="Name position"
          aria-valuenow={Math.round(style.y)}
          onPointerDown={(event) => {
            event.preventDefault();
            event.stopPropagation();
            draggingRef.current = true;
            (event.currentTarget as HTMLElement).setPointerCapture(
              event.pointerId,
            );
          }}
          onPointerMove={(event) => {
            if (draggingRef.current) {
              moveFromPointer(event.clientX, event.clientY);
            }
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
            const step = event.shiftKey ? 2 : 0.5;
            const keys: Record<string, [number, number]> = {
              ArrowLeft: [-step, 0],
              ArrowRight: [step, 0],
              ArrowUp: [0, -step],
              ArrowDown: [0, step],
            };
            const delta = keys[event.key];
            if (!delta) return;
            event.preventDefault();
            onPosition(
              clamp(style.x + delta[0], 0, 100),
              clamp(style.y + delta[1], 0, 100),
            );
          }}
          className="absolute cursor-move rounded px-1 py-0.5 outline-none ring-accent-600 focus-visible:ring-2"
          style={{
            left: `${style.x}%`,
            top: `${style.y}%`,
            transform: `translate(${translateX}, -50%)`,
            touchAction: "none",
            userSelect: "none",
          }}
        >
          <span
            className="certificate-name block"
            style={{
              fontFamily: fontStack(style.font),
              fontSize: `${fontSizePx}px`,
              color: style.color,
            }}
          >
            {sampleName}
          </span>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
        <span>Drag the name to position it · arrow keys to nudge</span>
        <span className="tabular-nums">
          x {style.x.toFixed(1)}% · y {style.y.toFixed(1)}%
        </span>
      </div>
    </div>
  );
}

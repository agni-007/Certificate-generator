"use client";

import { useEffect, useRef, useState } from "react";
import { fetchCertificatePreview, type TextStyle } from "@/lib/api";

interface FontStyle {
  fontFamily: string;
  fontStyle: "normal" | "italic" | "oblique";
  fontWeight: "normal" | "bold";
}

const FONT_STYLES: Record<string, FontStyle> = {
  times: {
    fontFamily: '"Times New Roman", Times, serif',
    fontStyle: "normal",
    fontWeight: "normal",
  },
  "times-italic": {
    fontFamily: '"Times New Roman", Times, serif',
    fontStyle: "italic",
    fontWeight: "normal",
  },
  "times-bold": {
    fontFamily: '"Times New Roman", Times, serif',
    fontStyle: "normal",
    fontWeight: "bold",
  },
  "times-bolditalic": {
    fontFamily: '"Times New Roman", Times, serif',
    fontStyle: "italic",
    fontWeight: "bold",
  },
  helvetica: {
    fontFamily: "Helvetica, Arial, sans-serif",
    fontStyle: "normal",
    fontWeight: "normal",
  },
  "helvetica-bold": {
    fontFamily: "Helvetica, Arial, sans-serif",
    fontStyle: "normal",
    fontWeight: "bold",
  },
  "helvetica-oblique": {
    fontFamily: "Helvetica, Arial, sans-serif",
    fontStyle: "oblique",
    fontWeight: "normal",
  },
  "helvetica-boldoblique": {
    fontFamily: "Helvetica, Arial, sans-serif",
    fontStyle: "oblique",
    fontWeight: "bold",
  },
  courier: {
    fontFamily: '"Courier New", Courier, monospace',
    fontStyle: "normal",
    fontWeight: "normal",
  },
  "courier-bold": {
    fontFamily: '"Courier New", Courier, monospace',
    fontStyle: "normal",
    fontWeight: "bold",
  },
  "courier-oblique": {
    fontFamily: '"Courier New", Courier, monospace',
    fontStyle: "oblique",
    fontWeight: "normal",
  },
  "courier-boldoblique": {
    fontFamily: '"Courier New", Courier, monospace',
    fontStyle: "oblique",
    fontWeight: "bold",
  },
};

/** Split a PDF font key into the three independent CSS properties. */
export function fontStyle(font: string): FontStyle {
  return FONT_STYLES[font] ?? FONT_STYLES["times-italic"];
}

/** Backwards-compatible helper returning only the CSS font-family. */
export function fontStack(font: string): string {
  return fontStyle(font).fontFamily;
}

interface Props {
  file: File | null;
  templateUrl: string | null;
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
  file,
  templateUrl,
  pageWidth,
  pageHeight,
  sampleName,
  style,
  onPosition,
}: Props) {
  const surfaceRef = useRef<HTMLDivElement>(null);
  const draggingRef = useRef(false);
  const [isDragging, setIsDragging] = useState(false);

  const [renderedUrl, setRenderedUrl] = useState<string | null>(null);
  const [isRendering, setIsRendering] = useState(false);
  const renderedUrlRef = useRef<string | null>(null);
  const [canvasWidth, setCanvasWidth] = useState(0);

  // Track the exact style payload of the currently loaded renderedUrl
  const loadedRenderKeyRef = useRef<string>("");
  const currentRenderKey = JSON.stringify({
    font: style.font,
    fontSize: style.fontSize,
    color: style.color,
    alignment: style.alignment,
    x: style.x,
    y: style.y,
    sampleName,
  });

  // ResizeObserver for canvas width
  useEffect(() => {
    const element = surfaceRef.current;
    if (!element) return;
    const observer = new ResizeObserver((entries) => {
      setCanvasWidth(entries[0].contentRect.width);
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [templateUrl]);

  // Clean up Object URL on unmount
  useEffect(() => {
    return () => {
      if (renderedUrlRef.current) {
        URL.revokeObjectURL(renderedUrlRef.current);
      }
    };
  }, []);

  // Background pixel-exact PyMuPDF rendering with 400ms debounce and AbortController cancellation
  useEffect(() => {
    if (!file) {
      if (renderedUrlRef.current) {
        URL.revokeObjectURL(renderedUrlRef.current);
        renderedUrlRef.current = null;
      }
      setRenderedUrl(null);
      loadedRenderKeyRef.current = "";
      return;
    }

    const controller = new AbortController();
    setIsRendering(true);

    const requestKey = currentRenderKey;
    const timer = setTimeout(async () => {
      try {
        const result = await fetchCertificatePreview(
          file,
          sampleName,
          style,
          controller.signal,
        );
        if (controller.signal.aborted) return;

        if (renderedUrlRef.current) {
          URL.revokeObjectURL(renderedUrlRef.current);
        }
        renderedUrlRef.current = result.url;
        loadedRenderKeyRef.current = requestKey;
        setRenderedUrl(result.url);
      } catch (err: unknown) {
        if (
          err instanceof Error &&
          (err.name === "AbortError" || controller.signal.aborted)
        ) {
          return;
        }
        console.warn("Failed to render exact preview:", err);
      } finally {
        if (!controller.signal.aborted) {
          setIsRendering(false);
        }
      }
    }, 400);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [file, sampleName, style, currentRenderKey]);

  if (!templateUrl) {
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

  // Check if loaded PyMuPDF image is 100% up to date with current parameters
  const isUpToDate =
    Boolean(renderedUrl) && loadedRenderKeyRef.current === currentRenderKey;
  const activeImageUrl = renderedUrl || templateUrl;

  const scale = canvasWidth > 0 && pageWidth > 0 ? canvasWidth / pageWidth : 1;
  const fontSizePx = Math.max(1, style.fontSize * scale);
  const activeFont = fontStyle(style.font);

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
        onPointerDown={(event) => {
          event.preventDefault();
          draggingRef.current = true;
          setIsDragging(true);
          moveFromPointer(event.clientX, event.clientY);
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
          setIsDragging(false);
          try {
            (event.currentTarget as HTMLElement).releasePointerCapture(
              event.pointerId,
            );
          } catch {}
        }}
        onPointerCancel={() => {
          draggingRef.current = false;
          setIsDragging(false);
        }}
      >
        {/* Background image: template or PyMuPDF render */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={activeImageUrl}
          alt="Certificate preview"
          draggable={false}
          className="absolute inset-0 h-full w-full object-contain select-none"
        />

        {/* 
          Live text overlay vs. Exact render overlay:
          - If NOT up to date (e.g. user is dragging slider, changing font, position, color) OR dragging on canvas:
            Render live 60fps CSS text element. It updates on EVERY FRAME immediately with 0ms delay!
          - If UP TO DATE with PyMuPDF exact render:
            Show subtle target boundary so text is from PyMuPDF, with hover target.
        */}
        <div
          role="slider"
          tabIndex={0}
          aria-label="Name position"
          aria-valuenow={Math.round(style.y)}
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
          className="absolute cursor-move outline-none group"
          style={{
            left: `${style.x}%`,
            top: `${style.y}%`,
            transform: `translate(${translateX}, -50%)`,
            touchAction: "none",
            userSelect: "none",
          }}
        >
          {isDragging || !isUpToDate ? (
            /* Instant 60fps live CSS text element — updates 0ms as slider moves */
            <span
              className="block whitespace-nowrap rounded px-1 transition-none"
              style={{
                fontFamily: activeFont.fontFamily,
                fontStyle: activeFont.fontStyle,
                fontWeight: activeFont.fontWeight,
                fontSize: `${fontSizePx}px`,
                color: style.color,
                textAlign: style.alignment,
                filter: "drop-shadow(0 1px 3px rgba(0,0,0,0.6))",
                outline: "2px dashed #6366f1",
                backgroundColor: "rgba(99, 102, 241, 0.15)",
              }}
            >
              {sampleName}
            </span>
          ) : (
            /* Exact PyMuPDF render is active — show subtle position outline */
            <div className="relative rounded border border-indigo-400/50 bg-indigo-500/10 px-2 py-1 transition-all group-hover:border-indigo-600 group-hover:bg-indigo-500/20 group-focus-visible:ring-2 group-focus-visible:ring-indigo-500">
              <span className="sr-only">{sampleName}</span>
              <span className="pointer-events-none absolute -top-5 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-slate-900/80 px-1.5 py-0.5 text-[9px] font-mono text-white opacity-0 transition-opacity group-hover:opacity-100">
                X {style.x.toFixed(1)}% · Y {style.y.toFixed(1)}%
              </span>
            </div>
          )}
        </div>
      </div>

      {/* ─── Info bar ─── */}
      <div className="flex items-center justify-between gap-2 text-xs text-slate-400">
        <span>Click or drag anywhere to position · arrow keys to nudge</span>
        <div className="flex items-center gap-2">
          {isRendering && (
            <span className="flex items-center gap-1.5 text-[11px] font-medium text-indigo-600">
              <span className="h-1.5 w-1.5 rounded-full bg-indigo-600 animate-ping" />
              Updating preview…
            </span>
          )}
          <span className="shrink-0 font-mono text-slate-600">
            X {style.x.toFixed(1)}% · Y {style.y.toFixed(1)}%
          </span>
        </div>
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

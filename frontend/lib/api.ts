const RAW_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const API_URL = RAW_URL.replace(/\/+$/, "");

export interface FontOption {
  value: string;
  label: string;
}

export interface ApiOptions {
  fonts: FontOption[];
  defaultFont: string;
  alignments: string[];
  defaultAlignment: string;
  maxNames: number;
  maxTemplateSizeMb: number;
  maxSpreadsheetSizeMb: number;
  templateExtensions: string[];
  spreadsheetExtensions: string[];
}

export interface TextStyle {
  x: number;
  y: number;
  font: string;
  fontSize: number;
  color: string;
  alignment: "left" | "center" | "right";
}

export interface PreviewResult {
  url: string;
  width: number;
  height: number;
}

export interface GenerateResult {
  blob: Blob;
  count: number;
}

const GENERIC_ERROR =
  "Something went wrong. Please check your connection and try again.";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status = 0) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (body && typeof body.detail === "string" && body.detail.trim()) {
      return body.detail;
    }
  } catch {
    // fall through to the generic message
  }
  return GENERIC_ERROR;
}

async function request(input: string, init?: RequestInit): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${input}`, init);
  } catch {
    throw new ApiError(
      "Could not reach the certificate service. Please try again.",
    );
  }
  if (!response.ok) {
    throw new ApiError(await errorMessage(response), response.status);
  }
  return response;
}

export async function fetchOptions(): Promise<ApiOptions> {
  const response = await request("/api/options");
  return (await response.json()) as ApiOptions;
}

export async function extractNames(file: File): Promise<string[]> {
  const form = new FormData();
  form.append("file", file);
  const response = await request("/api/names", { method: "POST", body: form });
  const body = (await response.json()) as { names?: unknown };
  return Array.isArray(body.names) ? (body.names as string[]) : [];
}

export async function fetchPreview(file: File): Promise<PreviewResult> {
  const form = new FormData();
  form.append("template", file);
  const response = await request("/api/preview", { method: "POST", body: form });
  const blob = await response.blob();
  const width = Number(response.headers.get("X-Page-Width")) || 595;
  const height = Number(response.headers.get("X-Page-Height")) || 842;
  return { url: URL.createObjectURL(blob), width, height };
}

/** Render a single certificate with the exact font/position/colour settings
 *  and return a pixel-accurate PNG preview — what the downloaded PDF will look like. */
export async function fetchCertificatePreview(
  file: File,
  name: string,
  style: TextStyle,
): Promise<PreviewResult> {
  const form = new FormData();
  form.append("template", file);
  form.append("name", name || "Sample Name");
  form.append("x", String(style.x));
  form.append("y", String(style.y));
  form.append("font", style.font);
  form.append("fontSize", String(style.fontSize));
  form.append("color", style.color);
  form.append("alignment", style.alignment);
  const response = await request("/api/preview-certificate", {
    method: "POST",
    body: form,
  });
  const blob = await response.blob();
  const width = Number(response.headers.get("X-Page-Width")) || 595;
  const height = Number(response.headers.get("X-Page-Height")) || 842;
  return { url: URL.createObjectURL(blob), width, height };
}

export async function generateCertificates(
  file: File,
  names: string[],
  style: TextStyle,
  onProgress?: (fraction: number) => void,
): Promise<GenerateResult> {
  const form = new FormData();
  form.append("template", file);
  form.append("names", JSON.stringify(names));
  form.append("x", String(style.x));
  form.append("y", String(style.y));
  form.append("font", style.font);
  form.append("fontSize", String(style.fontSize));
  form.append("color", style.color);
  form.append("alignment", style.alignment);

  // A single POST cannot report real progress, so advance a bar while waiting.
  let fraction = 0.04;
  const timer = window.setInterval(() => {
    fraction = Math.min(0.92, fraction + (0.92 - fraction) * 0.06);
    onProgress?.(fraction);
  }, 120);
  onProgress?.(fraction);

  try {
    const response = await request("/api/generate", {
      method: "POST",
      body: form,
    });
    const blob = await response.blob();
    const count = Number(response.headers.get("X-Certificate-Count")) || names.length;
    onProgress?.(1);
    return { blob, count };
  } finally {
    window.clearInterval(timer);
  }
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 4000);
}

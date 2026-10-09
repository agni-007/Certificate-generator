"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import CertificatePreview from "@/components/CertificatePreview";
import GeneratePanel from "@/components/GeneratePanel";
import NameInput from "@/components/NameInput";
import TemplateUpload from "@/components/TemplateUpload";
import TextSettings from "@/components/TextSettings";
import {
  ApiError,
  downloadBlob,
  extractNames,
  fetchOptions,
  fetchPreview,
  generateCertificates,
  type ApiOptions,
  type TextStyle,
} from "@/lib/api";

const TEMPLATE_EXTENSIONS = ["pdf", "png", "jpg", "jpeg"];
const SHEET_EXTENSIONS = ["xlsx", "csv"];

const DEFAULT_STYLE: TextStyle = {
  x: 50,
  y: 52,
  font: "times-italic",
  fontSize: 37,
  color: "#ffffff",
  alignment: "center",
};

interface TemplateState {
  file: File;
  url: string;
  width: number;
  height: number;
}

function Section({
  step,
  title,
  hint,
  children,
}: {
  step: number;
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-baseline gap-2">
        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-accent-600 text-[11px] font-bold text-white">
          {step}
        </span>
        <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
        {hint ? <span className="text-xs text-slate-500">{hint}</span> : null}
      </div>
      {children}
    </section>
  );
}

function extensionOf(filename: string): string {
  const index = filename.lastIndexOf(".");
  return index === -1 ? "" : filename.slice(index + 1).toLowerCase();
}

export default function Home() {
  const [options, setOptions] = useState<ApiOptions | null>(null);
  const [template, setTemplate] = useState<TemplateState | null>(null);
  const [templateBusy, setTemplateBusy] = useState(false);
  const [templateError, setTemplateError] = useState<string | null>(null);
  const [namesText, setNamesText] = useState("");
  const [namesBusy, setNamesBusy] = useState(false);
  const [namesError, setNamesError] = useState<string | null>(null);
  const [style, setStyle] = useState<TextStyle>(DEFAULT_STYLE);
  const [generating, setGenerating] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<{ blob: Blob; count: number } | null>(
    null,
  );
  const [generateError, setGenerateError] = useState<string | null>(null);
  const templateUrlRef = useRef<string | null>(null);

  useEffect(() => {
    fetchOptions()
      .then(setOptions)
      .catch((error: unknown) => {
        // The UI still works with sensible defaults if this fails.
        console.warn("Could not load API options", error);
      });
  }, []);

  useEffect(
    () => () => {
      if (templateUrlRef.current) URL.revokeObjectURL(templateUrlRef.current);
    },
    [],
  );

  const names = useMemo(
    () =>
      namesText
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean),
    [namesText],
  );

  const maxNames = options?.maxNames ?? 2000;
  const maxTemplateMb = options?.maxTemplateSizeMb ?? 25;

  const handleTemplate = useCallback(
    async (file: File) => {
      setTemplateError(null);
      const extension = extensionOf(file.name);
      if (!TEMPLATE_EXTENSIONS.includes(extension)) {
        setTemplateError(
          "Unsupported template format. Please upload PDF, PNG, JPG, or JPEG.",
        );
        return;
      }
      if (file.size > maxTemplateMb * 1024 * 1024) {
        setTemplateError("The certificate template is too large.");
        return;
      }
      setTemplateBusy(true);
      try {
        const preview = await fetchPreview(file);
        if (templateUrlRef.current) URL.revokeObjectURL(templateUrlRef.current);
        templateUrlRef.current = preview.url;
        setTemplate({
          file,
          url: preview.url,
          width: preview.width,
          height: preview.height,
        });
        setProgress(0);
        setResult(null);
      } catch (error) {
        setTemplateError(
          error instanceof ApiError
            ? error.message
            : "Something went wrong while reading the template. Please try again.",
        );
      } finally {
        setTemplateBusy(false);
      }
    },
    [maxTemplateMb],
  );

  const handleClearTemplate = useCallback(() => {
    if (templateUrlRef.current) URL.revokeObjectURL(templateUrlRef.current);
    templateUrlRef.current = null;
    setTemplate(null);
    setTemplateError(null);
    setResult(null);
    setProgress(0);
  }, []);

  const handleNamesFile = useCallback(
    async (file: File) => {
      setNamesError(null);
      if (!SHEET_EXTENSIONS.includes(extensionOf(file.name))) {
        setNamesError(
          "Unsupported file format. Please upload an .xlsx or .csv file.",
        );
        return;
      }
      setNamesBusy(true);
      try {
        const extracted = await extractNames(file);
        if (extracted.length === 0) {
          setNamesError("No valid names were found in the uploaded file.");
          return;
        }
        setNamesText(extracted.join("\n"));
        setResult(null);
        setGenerateError(null);
      } catch (error) {
        setNamesError(
          error instanceof ApiError
            ? error.message
            : "Unable to read the uploaded Excel file. Please check the file and try again.",
        );
      } finally {
        setNamesBusy(false);
      }
    },
    [],
  );

  const handleGenerate = useCallback(async () => {
    if (!template) return;
    setGenerating(true);
    setGenerateError(null);
    setProgress(0.04);
    setResult(null);
    try {
      const generated = await generateCertificates(
        template.file,
        names,
        style,
        setProgress,
      );
      setResult(generated);
      setProgress(1);
    } catch (error) {
      setGenerateError(
        error instanceof ApiError
          ? error.message
          : "Something went wrong while generating the certificates. Please try again.",
      );
      setProgress(0);
    } finally {
      setGenerating(false);
    }
  }, [template, names, style]);

  const sampleName = names[0] ?? "Sample Name";
  const canGenerate = Boolean(template) && names.length > 0 && !generating;

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
            Certificate Generator
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Upload a template, add names, position the text, and download the
            finished certificates.
          </p>
        </div>
      </header>

      <main className="mx-auto grid max-w-6xl gap-6 px-4 py-8 sm:px-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]">
        <div className="space-y-6">
          <Section step={1} title="Certificate Template">
            <TemplateUpload
              file={template?.file ?? null}
              previewUrl={template?.url ?? null}
              busy={templateBusy}
              error={templateError}
              maxTemplateSizeMb={maxTemplateMb}
              onSelect={handleTemplate}
              onClear={handleClearTemplate}
            />
          </Section>

          <Section step={2} title="Names" hint={`${names.length} added`}>
            <NameInput
              value={namesText}
              maxNames={maxNames}
              busy={namesBusy}
              error={namesError}
              onChange={(value) => {
                setNamesText(value);
                setNamesError(null);
              }}
              onFile={handleNamesFile}
            />
          </Section>

          <Section step={3} title="Text Settings">
            <TextSettings
              style={style}
              options={options}
              onChange={(patch) => {
                setStyle((current) => ({ ...current, ...patch }));
                setResult(null);
              }}
            />
          </Section>

          <GeneratePanel
            canGenerate={canGenerate}
            busy={generating}
            progress={progress}
            nameCount={names.length}
            readyCount={result?.count ?? null}
            error={generateError}
            onGenerate={handleGenerate}
            onDownload={() =>
              result && downloadBlob(result.blob, "certificates.zip")
            }
          />
        </div>

        <div className="lg:sticky lg:top-6 lg:h-fit">
          <Section step={4} title="Preview" hint={sampleName}>
            <CertificatePreview
              url={template?.url ?? null}
              pageWidth={template?.width ?? 595}
              pageHeight={template?.height ?? 842}
              sampleName={sampleName}
              style={style}
              onPosition={(x, y) =>
                setStyle((current) => ({ ...current, x, y }))
              }
            />
          </Section>
        </div>
      </main>

      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto max-w-6xl px-4 py-5 text-xs text-slate-500 sm:px-6">
          Files are processed temporarily and never stored.
        </div>
      </footer>
    </div>
  );
}

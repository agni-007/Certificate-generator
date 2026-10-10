import { describe, expect, it } from "vitest";
import { fontStack, fontStyle } from "./CertificatePreview";

describe("fontStyle", () => {
  it("returns family, style and weight as separate properties", () => {
    expect(fontStyle("times-bolditalic")).toEqual({
      fontFamily: '"Times New Roman", Times, serif',
      fontStyle: "italic",
      fontWeight: "bold",
    });
  });

  it("does not put the style keyword inside font-family", () => {
    const style = fontStyle("helvetica-boldoblique");
    expect(style.fontFamily).toBe("Helvetica, Arial, sans-serif");
    expect(style.fontFamily).not.toContain("bold");
    expect(style.fontFamily).not.toContain("oblique");
    expect(style.fontStyle).toBe("oblique");
    expect(style.fontWeight).toBe("bold");
  });

  it("maps italic fonts", () => {
    expect(fontStyle("times-italic").fontStyle).toBe("italic");
    expect(fontStyle("courier-oblique").fontStyle).toBe("oblique");
  });

  it("maps bold fonts", () => {
    expect(fontStyle("times-bold").fontWeight).toBe("bold");
    expect(fontStyle("helvetica").fontWeight).toBe("normal");
  });

  it("falls back to the default times-italic", () => {
    expect(fontStyle("comic-sans")).toEqual(fontStyle("times-italic"));
  });

  it("keeps fontStack returning only the family (backwards compatible)", () => {
    expect(fontStack("courier-bold")).toBe('"Courier New", Courier, monospace');
  });
});

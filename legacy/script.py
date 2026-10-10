import pandas as pd
import fitz  # PyMuPDF
import os

# ---------- CONFIG ----------
# Default template file name (fallback to existing files in workspace if default not found)
PDF_TEMPLATE = "A4 - 4-1.pdf" if os.path.exists("A4 - 4-1.pdf") else "template.pdf"
EXCEL_FILE = "names.xlsx" if os.path.exists("names.xlsx") else "v.xlsx"
OUTPUT_FOLDER = "certificates_output"  # where generated certificates are saved
PLACEHOLDER_TEXT = "Arjun Harid as"     # text in the PDF that gets replaced by each name
FONT_NAME = "Times-Italic"
TEXT_SIZE = 37
TEXT_COLOR = (1, 1, 1)                 # RGB white for dark template background
# -----------------------------


def add_names_to_certificates(pdf_template_path, excel_path, output_folder,
                              placeholder_text=None, font_name=FONT_NAME, text_size=TEXT_SIZE,
                              text_color=TEXT_COLOR):

    # Load names from Excel/CSV
    if str(excel_path).endswith(".csv"):
        df = pd.read_csv(excel_path)
    else:
        df = pd.read_excel(excel_path)

    if df.empty:
        raise ValueError("The names file is empty.")

    # Find the "name" column (case-insensitive), fallback to first column
    name_col = next((c for c in df.columns if str(c).strip().lower() == "name"), df.columns[0])

    os.makedirs(output_folder, exist_ok=True)

    pdf_template = fitz.open(pdf_template_path)
    page = pdf_template[0]

    # Search for placeholder text (try configured placeholder, then known fallbacks)
    rects = []
    placeholders_to_try = [placeholder_text, "Arjun Harid as", "Arjun Harid", "NAME_PLACEHOLDER"]
    for p in placeholders_to_try:
        if p:
            found = page.search_for(p)
            if found:
                rects = found
                break

    center_x = (page.rect.x0 + page.rect.x1) / 2
    if rects:
        placeholder_rect = rects[0]
        baseline_y = (placeholder_rect.y0 + placeholder_rect.y1) / 2 + (text_size / 3)
    else:
        baseline_y = 285.0

    generated_files = []

    for index, row in df.iterrows():
        name = str(row[name_col]).strip()
        if not name or name.lower() == "nan":
            continue

        new_pdf = fitz.open()
        new_pdf.insert_pdf(pdf_template)
        new_page = new_pdf[0]

        # Redact placeholder text if present so old name is cleanly removed without a white box
        if rects:
            for r in rects:
                new_page.add_redact_annot(r, fill=False)
            new_page.apply_redactions(images=0)

        text_width = fitz.get_text_length(name, fontname=font_name, fontsize=text_size)
        start_x = center_x - (text_width / 2)
        new_page.insert_text((start_x, baseline_y), name, fontsize=text_size, fontname=font_name, color=text_color)

        safe_name = "".join(c for c in name if c.isalnum() or c in (" ", "_")).replace(" ", "_")
        output_path = os.path.join(output_folder, f"certificate_{safe_name}.pdf")
        new_pdf.save(output_path)
        new_pdf.close()

        generated_files.append(output_path)
        print(f"[{index + 1}/{len(df)}] Generated certificate for {name}")

    pdf_template.close()
    return generated_files


if __name__ == "__main__":
    if not os.path.exists(PDF_TEMPLATE) or not os.path.exists(EXCEL_FILE):
        print(f"Make sure '{PDF_TEMPLATE}' and '{EXCEL_FILE}' are in this folder.")
    else:
        files = add_names_to_certificates(PDF_TEMPLATE, EXCEL_FILE, OUTPUT_FOLDER, PLACEHOLDER_TEXT)
        print(f"\nDone. {len(files)} certificates saved in '{OUTPUT_FOLDER}'.")
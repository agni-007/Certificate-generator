# LICENSE DECISION

**Status:** No software licence chosen for the repository.

## Why this matters

This project depends on [PyMuPDF](https://github.com/pymupdf/PyMuPDF) which is
licensed under the GNU Affero General Public License, version 3.0 (AGPL-3.0).

If you distribute this application to others (as binaries, as a hosted web
service that others use, or in other ways that constitute distribution under
copyright law) you must comply with the terms of AGPL-3.0. For web-hosted
services, AGPL-3.0 can trigger source-offering obligations if you modify
PyMuPDF or combine it in ways covered by the licence. If you do not comply, you
risk copyright infringement.

## Options

1. **Comply with AGPL-3.0**  
   - If you keep using PyMuPDF unmodified and distribute the app, ensure
     recipients can access the source code of this application and any modified
     AGPL-licensed components (PyMuPDF itself and any other AGPL code).
   - For a public hosted deployment (e.g. Render/Vercel), if you have made
     modifications to AGPL-licensed components, AGPL-3.0 may require you to
     offer the corresponding source code to users of the service.
   - You may also need to provide notices, preserve licence texts, and allow
     redistribution under AGPL-3.0 terms.

2. **Purchase a commercial licence from Artifex**  
   - Artifex offers commercial licences for PyMuPDF that permit closed-source
     distribution, proprietary modifications, and use in products without AGPL
     obligations. Pricing depends on use case, deployment, and support needs.
   - Contact [Artifex](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-commercial-licensing)
     for details.

3. **Switch to a permissively licensed PDF library**  
   - Evaluate alternatives such as [pdf-lib](https://github.com/Hopding/pdf-lib)
     (MIT), [pdfkit](https://github.com/JazzCore/python-pdfkit) (MIT), or
     [PyPDF2/pypdf](https://github.com/py-pdf/pypdf) (BSD).
   - Trade-offs: some libraries have different capabilities for rendering,
     font handling, image manipulation, or performance. PyMuPDF is used here for
     efficient PDF/image rendering and layout; switching would require code
     changes and thorough testing.

## Recommendation

- **Do not add a licence yet.** First decide which option fits your
  distribution/hosting plans.  
- Keep this file in the repository as a record of the decision to be made.
- If you distribute this software publicly, choose (1) or (2). If you must
  avoid AGPL copyleft exposure, choose (2) or (3).

**Notes on this repository:** The code uses PyMuPDF (`fitz`) for template
rendering, image processing and PDF generation. No other AGPL-3.0 dependencies
were identified at the time of this decision. This decision file does not
constitute legal advice.

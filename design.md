# Film Developing: a clear photographic workspace

## Product contract

The visitor opens a photo of developed film, optionally calibrates it, converts locally,
inspects the result and downloads a chosen version. The photograph and next action come
before technical explanation. There is no upload to a server and no user library feature.

## Applied references

- FilmLab: https://www.filmlabapp.com/ — name the conversion task immediately and show a
  real photograph as evidence of the product.
- Darkroom first-edit guide: https://darkroom.co/help/guide/your-first-edit — central image,
  adjacent controls, explicit comparison and export. We do not claim its library or edit-history features.
- Photopea opening/saving: https://www.photopea.com/learn/opening-saving — file picker plus
  drag and drop, stable workspace, deliberate export format.

These are patterns, not copied layouts or assets. Photographs remain the existing BlueNeg examples.

## Site structure

- Develop (`/`): actual working converter. Main path: open image, choose film, develop.
  Calibration and AI are optional disclosures. The included sample runs in one click.
- Examples (`galleria.html`): three distinct questions under tabs: archive, clean-up/AI,
  experimental colour. Historical metrics stay with archive references.
- Guide (`guida.html`): capture, calibration, version meanings, formats, limits, project.
- Old `app.html` links forward to the working homepage.

## Visual system: the archive

The world is a photographer sorting rolls: the contact sheet, the lab envelope, the china marker.
Light page (grey archive board `#e3e1db`, print paper `#fbfaf7`), photographs inside black film
strips with sprocket holes and edge printing that names the selected film stock and frame.
The control column is a kraft lab envelope (`#c9a56f`, fine paper grain) with printed rules and
numbered stamped boxes for the three steps; inputs are pale field paper. One red, the china
marker `#b3261e`, carries the primary action, the current step, the chosen version (a hand-drawn
circle around its frame) and links. Archivo throughout (semi-condensed widths for headings,
uppercase stamped labels); Geist Mono only for numeric metadata.

Layout: the photo owns the stage at desktop width with the envelope column at its right; the
develop step stays sticky. Below 820px the envelope follows the photo and a bottom action bar
follows the task (open or sample, develop, download). Motion: the developed print emerges from
a washed-out state once per development; the marker circle draws itself on selection. Both are
removed under reduced motion. Icons are inline SVG; no unicode glyph icons.

## Acceptance checks

At 1440px and 390px: input and sample actions are discoverable, images retain their aspect
ratio, optional configuration does not block basic conversion, output/version/download
are together, no unintended horizontal scrolling. Check loading, partial output, error,
finished output, keyboard comparison, gallery tabs/deep links, language switch and downloads.
Synthetic engine tests and a real in-browser sample run must pass. Private fixture tests
must be reported as skipped when unavailable; do not claim a new colour accuracy score.

## Verification for this revision

The public engine suite passes 7 tests; 2 private-fixture/AI checks are explicitly skipped.
Browser checks covered real sample conversion, another included JPEG, invalid-image error
and recovery, sample-reference clearing, stale-export blocking, retained version-button
focus, keyboard detail movement, gallery tab keys/history, IT/EN, and 390px layout without
page overflow. The sample completed in about 2.4–2.7 seconds on the test machine; this is
an observation, not a promised product metric. AI enlargement and HEIC/Safari were not
rerun in this UX revision. No engine algorithm was changed in this revision.


## Manual editing

The negative upload offers a four-corner crop dialog. Automatic detection is a starting point; drag, arrow keys (Shift for fine adjustment), and percentage coordinates edit the same normalized quadrilateral. Apply marks existing output stale; the next development uses the manual perspective transform without automatic trimming or aspect snapping. A new negative resets the crop.

Colour controls appear after development, under an optional disclosure. Temperature, tint and a median 5×5 neutral patch adjust pristine floating-point output without rerunning development or enhancement. Corrections preserve luminance and compress out-of-gamut chroma. Reset restores the original encoded files. Before/after compares the selected version with its adjusted counterpart; JPEG and TIFF use the displayed adjustment. Downloads stay disabled while a new correction is pending or development settings are stale. Source and request IDs reject superseded work.

Verification: 12 Node tests pass; two private photographic-fixture checks are skipped when fixtures are absent. Browser checks cover the included sample, manual corner keyboard adjustment and resulting changed dimensions, colour adjustment, neutral selection and reset.


## Exposure, contrast and synchronized inspection

Image adjustments now include exposure (−3 to +3 linear-light stops) and contrast (a monotonic power curve around 18% gray), alongside the existing neutral patch, temperature and tint controls. Neutral-point selection retains exposure and contrast. The worker posts the JPEG preview before encoding TIFF, while downloads stay disabled until matching final output is ready. Identity reset reuses pristine encoded output.

The comparison reference defaults to base development, with an option to compare the selected version before adjustments. The optional detail view offers fit, 100%, 200%, centre, synchronized pointer/touch dragging and keyboard pan. At 100%, one selected-image pixel occupies one CSS pixel; the reference maps to the same scene area, including differently sized AI output. Captions show each source’s actual magnification. Both canvases use the display pixel ratio for crisp rendering; viewport edges clamp pan.

Validation adds tests for exposure stops, contrast pivot/monotonicity/limits, native pixel scale, AI reference alignment, fit and pan bounds.


Browser validation for the new controls: sample development, exposure/contrast changes, neutral selection retaining exposure, exact original-download URL after reset, before-adjustment reference, version switch during adjustment, native 100% and 200%, keyboard and mouse synchronized pan, mobile 390px with no horizontal overflow, and a real 2048×1426 AI result aligned with its 1181×822 base at 173% reference scale. A downloaded edited TIFF was inspected for expected dimensions and RGB 16-bit samples. Local 6 MP adjustment computation measured about 200 ms (excluding JPEG/TIFF encoding).

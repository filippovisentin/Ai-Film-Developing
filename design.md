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

## Visual system

Light neutral page and controls; charcoal canvas around photographs. Manrope for the UI,
monospace only for numeric metadata. One restrained terracotta action colour. Shared plain
header, visible current destination, consistent vocabulary in Italian and English.

No oversized slogans, floating pill navigation, decorative darkroom props, edition labels,
rotated image mounts, ornamental status dots, card grids or scroll-reveal dependencies.
Motion is reserved for useful feedback. Content stays visible without animation.

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

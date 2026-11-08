# Ai-Film-Developing

## What it is
A free, open-source web tool that turns a phone photo of a developed film negative into a
digital photograph. The conversion engine (a JavaScript port of `filmengine`) runs entirely in
the visitor's browser: photos are never uploaded.

## Who uses it
Hobbyist film photographers who develop at home or collect old negatives, and want a usable
digital image without a scanner. They photograph the strip on a light pad, tablet or window
with their phone, then open that photo here. Many arrive on a phone; the editing session is
often at a desk, in the evening, with the negatives still on the light pad.

## The job
Open a negative (or the included sample), choose the film stock, develop, compare versions
(base development, Enhanced, optional AI upscale), correct exposure/contrast/white balance,
download JPEG or 16-bit TIFF. Optional: manual crop, calibration photos (bare light, film edge).

## Truths the interface must keep
- Processing is local; nothing is sent to a server.
- AI upscaling can invent detail and must say so next to the result.
- Kodak Gold 100 is a preliminary calibration.
- Sample photographs come from the BlueNeg dataset, © Tien-Tsin Wong; credit stays visible.
- Italian is the primary language; English is a full translation.
- No accounts, no library, no edit history.

## Brand commitments
Photographs lead; interface serves them. No hype copy, no invented metrics or testimonials.

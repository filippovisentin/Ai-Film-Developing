# Image sources and licences

| Files | Source | Licence | Credit shown on slides |
|---|---|---|---|
| `ektar-strip-negative.jpg`, `ektar-frame-*` | [Color print film strip 01 - negative](https://commons.wikimedia.org/wiki/File:Color_print_film_strip_01_-_negative.jpg), Wikimedia Commons, by LoMit (2000 px copy) | CC BY 4.0 | Negative: LoMit, CC BY 4.0, via Wikimedia Commons |
| `farbnegativ-strip.jpg`, `superia-frame-*` | [Farbnegativ.jpg](https://commons.wikimedia.org/wiki/File:Farbnegativ.jpg), Wikimedia Commons, by Florian Schott, Fuji Superia 200 (2000 px copy) | CC BY-SA 3.0 | Negative: Florian Schott, CC BY-SA 3.0, via Wikimedia Commons |
| `kodak-street-*` | [Museums Victoria item 2057235](https://collections.museumsvictoria.com.au/items/2057235), glass negative, Kodak factory, Southampton Crescent, Abbotsford, c. 1930s | Public domain | Glass negatives: Museums Victoria, public domain |
| `kodak-garden-*` | [Museums Victoria item 2057260](https://collections.museumsvictoria.com.au/items/2057260), glass negative, Kodak factory and garden, Abbotsford, c. 1930s | Public domain | same |
| `plates/<item>-*` | Museums Victoria items 2057235, 2057242, 2057245, 2057251, 2057260, 2057262: raw glass negative scans from `incoming/museums-victoria/` (see `SOURCES.txt` there), whole plate with tape and edges | Public domain | same |
| `incoming/museums-victoria/` | Raw scans and the museum's own positives. Only the raw negatives are used on slides. | Public domain | |

Every `*-developed` file is the engine's base development (`filmengine`, generic colour or generic black-and-white profile, `--no-crop`), with no manual edits. Slides built from CC BY-SA material (the Superia slide, 09) should also be shared under CC BY-SA 3.0.

Fig. 3 in post 01 also shows a plain inversion (255 minus each value) of the Ektar frame, computed in `build_posts.py`, to compare with the engine.

Rebuild: `prepare_ektar.py`, `prepare_frames.py`, `prepare_plates.py`, then `build_posts.py`.

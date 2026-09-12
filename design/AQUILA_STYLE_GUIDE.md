# Aquila Design System

Accessible, ADHD- and dyslexia-friendly styling for BIL and the wider SANd-X ecosystem. This is the canonical spec — other apps in the ecosystem should import `aquila-tokens.json` / `aquila-theme.css` rather than reinventing the palette.

## Why

Standard "dark mode with a bright accent" themes are usually tuned for looks, not reading. Aquila is tuned for two specific things:

- **Dyslexia**: predictable letter shapes, generous spacing, ragged-right text, no visual noise competing with the text itself.
- **ADHD**: low clutter, one clear primary action per screen, chunked content over walls of prose, motion kept to a minimum and fully respecting `prefers-reduced-motion`.

## Typography

- Primary stack: `'Aquila', 'Atkinson Hyperlegible', 'Lexend', system-ui, sans-serif`
- **Aquila** is the brand typeface. If/when a licensed font file exists, self-host it with `@font-face` — do not hotlink an unverified "Aquila" font from a random CDN.
- Until then (and always, as the safety net), fall back to **Atkinson Hyperlegible** (designed by the Braille Institute specifically for low-vision/dyslexic legibility) and **Lexend** (shown in reading-fluency studies to reduce reading time). Never fall back to a serif or a geometric sans with ambiguous `b`/`d`/`p`/`q` shapes.
- Dyslexic mode swaps in `'OpenDyslexic'` first, widens line-height to 1.8, letter-spacing to 0.03em, word-spacing to 0.12em.
- Body text is always left-aligned. Never `text-align: justify` — justified text creates uneven word gaps ("rivers") that are one of the most common dyslexic reading complaints.
- Line measure capped at `70ch` so lines stay short enough to track without losing your place.

## Color

Dark theme is the default (matches the WaveAtlas-style reference board this spec was drafted against: near-black navy background, cyan accent, near-white text).

| Token | Hex | Role |
|---|---|---|
| `--aq-bg` | `#060A12` | Page background |
| `--aq-surface` | `#0B1420` | Cards/panels |
| `--aq-surface-alt` | `#10283C` | Hover/elevated surface |
| `--aq-border` | `#1B3A4B` | Dividers, outlines |
| `--aq-accent` | `#22D3EE` | Icons, borders, large graphics |
| `--aq-accent-text` | `#7FE7F5` | Links, accent text |
| `--aq-text` | `#F2FBFF` | Primary text |
| `--aq-text-muted` | `#9FB8C6` | Secondary text |
| `--aq-focus` | `#FFD166` | Focus ring — reserved, never reused elsewhere |

A light theme (`[data-theme="light"]`) mirrors the same roles with equivalent contrast, for users who read better on light backgrounds.

**Contrast is computed, not eyeballed.** Using the WCAG 2.1 relative-luminance formula against `--aq-bg` (#060A12):

| Foreground | Ratio vs. bg | WCAG level |
|---|---|---|
| `--aq-text` (#F2FBFF) | ~18.9:1 | AAA (needs 7:1) |
| `--aq-accent-text` (#7FE7F5) | ~13.8:1 | AAA |
| `--aq-text-muted` (#9FB8C6) | ~9.6:1 | AAA |
| `--aq-accent` (#22D3EE, graphics/icons only) | ~11:1 | AAA (graphics only need 3:1) |

Note we deliberately use near-black (`#060A12`) and near-white (`#F2FBFF`) rather than pure `#000`/`#FFF`. Pure black-on-white or white-on-black causes halation/glare for some light-sensitive and dyslexic readers; softened extremes keep the AAA contrast ratio while reducing that effect.

**Never use tight repeating high-frequency patterns** — fine stripes, moiré, busy textures — anywhere in a background, border, or loading state. These are a documented visual-stress trigger (Meares-Irlen / visual stress syndrome) for dyslexic and photosensitive readers. Use flat fills or soft, low-frequency gradients only.

## Motion

- Keep transitions short (`180ms`, `ease-out`) and purposeful — never decorative animation that runs without user action.
- `@media (prefers-reduced-motion: reduce)` must **fully disable** animation and transitions, not just shorten them. See `aquila-theme.css`.

## Focus & keyboard

- `:focus-visible` gets a thick (3px), high-contrast outline in a color (`--aq-focus`) used *only* for focus — never reuse it as a decorative accent, or users lose the cue.
- Never remove focus outlines to "clean up" a design.

## Layout principles (not just CSS)

- One clear primary action per screen. Competing equal-weight buttons force a decision an ADHD user may stall on.
- Chunk content: real headings, short paragraphs, lists — not walls of prose. (This is why this file uses headings and tables instead of one long paragraph.)
- Keep navigation and layout patterns consistent screen-to-screen; novelty for its own sake costs orientation.
- Make status/progress explicit (spinners alone aren't enough — pair with text: "Encoding tokens…").

## Files in this directory

- `aquila-tokens.json` — machine-readable source of truth (colors, type, spacing, motion, a11y rules). Import this into any app's build.
- `aquila-theme.css` — drop-in CSS implementing the tokens as custom properties + base element styles + utility classes (`.aq-surface`, `.aq-container`, `.aq-badge`, `.aq-button`).
- `demo.html` — live reference page applying the theme to real BIL content (SUES slots, token grammar) so you can see it rendered, not just read the tokens.

## Adopting this in another app

1. Copy `aquila-tokens.json` and `aquila-theme.css` (or vendor them via your build tool).
2. Link `aquila-theme.css` before your app's own stylesheet so your overrides win only where intentional.
3. Set `<html data-theme="dark">` (or `"light"`) and optionally `data-dyslexic-mode="on"`, driven by a user preference toggle — don't hardcode one theme.
4. Keep body copy inside `.aq-container` / respect `--aq-measure` so line length stays readable.
5. Any new color you introduce must be checked against `--aq-bg`/`--aq-surface` for the same AAA bar before shipping it.

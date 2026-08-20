# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A static, no-build HTML/CSS/JS marketing website for Nicky Sandoz Photography (home, about, gallery, contact pages). There is no package.json, bundler, linter, test runner, or framework — every page is hand-written HTML that links directly to plain CSS and JS files.

## Development workflow

There is no bundler, linter or test runner. The one script in the repo is `tools/build_gallery.py`, which regenerates the gallery grid from `images/gallery/`; it runs automatically in CI on push, so you normally never need to run it by hand. To work on the site:

- **Preview locally**: open the `.html` files directly in a browser, or serve the directory with any static file server (e.g. `python3 -m http.server`) from the repo root so relative asset paths resolve correctly.
- **Deploy**: files are uploaded/synced as-is to static hosting (no build step to run first).
- Edits are made directly to the HTML/CSS files; there's no templating, but the header and footer are shared via a small client-side include (see below), so those two don't need to be edited per page.

## Structure

- `index.html`, `about.html`, `contact.html`, `gallery.html`, `404.shtml` — the site's pages, each a self-contained HTML document.
- `partials/header.html`, `partials/footer.html` — the site's single copies of the header/nav and footer markup. Edit these, not the pages, to change nav links, the logo, or contact info (phone, Instagram, LinkedIn, email) — the change then applies to every page automatically.
- `js/include-partials.js` — fetches `partials/header.html`/`partials/footer.html` at page load and injects them into that page's `<div data-include="…">` placeholder. Also handles marking the current page's nav link with the `selected` class (matched by comparing the link's `href` to the current URL's filename) — there's no more hardcoded `class="selected"` per page.
- `stylesheet.css` — the primary sitewide stylesheet (typography, header/nav, `.block-a/b/c` content bands, buttons, and a single `max-width: 600px` mobile media query). Loaded by every page except `404.shtml`.
- `css/style.css` and `css/demo.css` — third-party gallery grid/lightbox styles (from a Codeconvey gallery template), used only by `gallery.html`.
- `js/gallery.js` — vanilla JS + jQuery gallery module for `gallery.html`. Handles lazy-loading thumbnails via `IntersectionObserver` (reading `data-src`/`data-image` attributes on `.thumb` images) and a custom swipeable lightbox (built entirely by DOM manipulation in `createLightbox()`, not markup in the HTML). jQuery itself is pulled from a CDN `<script>` tag in `gallery.html`, not vendored.
- `images/gallery/` — **the gallery's source of truth.** Every photo in this folder becomes a tile on `gallery.html`, and nothing else does. Dropping a photo in here (and pushing) is the entire process for adding one; see "Adding a gallery photo" below.
- `images/site/` — images used as page furniture rather than portfolio work: `collage1.png` (home page + Open Graph preview), `jellybelly.png` (a CSS background), `Nicky-Portrait-Pic.png` (the About portrait). These are referenced by hand from the pages, so they are deliberately kept out of `images/gallery/`.
- `images/archive/` — photos that live in the repo but are not published anywhere. Kept so nothing is lost; safe to ignore. Move a file from here into `images/gallery/` to put it on the site.
- `tools/build_gallery.py` — regenerates the gallery grid in `gallery.html` from `images/gallery/`. Pure Python 3 standard library, no dependencies to install. Reads each photo's real pixel dimensions and EXIF orientation straight out of the file header, and takes the page order from the filename. Run `python3 tools/build_gallery.py` to rebuild, or `--check` to see what would change without writing. This is the only script the repo should carry — utilities Nicky runs on their own machine (resizing photos for web before they go in `images/gallery/`, for instance) are not part of the build and live outside the repo.
- `.github/workflows/build-gallery.yml` — runs that script on every push that touches `images/gallery/` and commits the regenerated `gallery.html` back to `main`. This is what makes "drop a photo in the folder, push, done" work without running anything locally.
- `resize-mobile_stylesheet.css` — present but empty; not a real dependency.
- `favicon.svg` — simple "NS" monogram, linked from every page via `<link rel="icon">`.

## Conventions to preserve when editing

- **Header/nav/footer live only in `partials/header.html`/`partials/footer.html`** — don't add header/nav/footer markup back into individual pages. Each page just needs a `<div id="site-header" data-include="partials/header.html" data-mark-nav></div>` (and `id="site-footer" data-include="partials/footer.html"` for pages with a footer — `gallery.html` has none) plus `<script src="js/include-partials.js" defer></script>` in `<head>`. This relies on `fetch()`, so it only works when the page is served over `http(s)://` (a local static server, or the real deployed site) — opening a page directly via `file://` will leave the header/footer blank. `partials/header.html` wraps the nav in a semantic `<header class="header">`, and each page's own body content should stay wrapped in `<main>` (before the `<div id="site-footer">`) — keep new pages consistent with this landmark structure. When adding a new page, follow this include pattern rather than copying header/footer markup inline.
- **Buttons are anchors, not nested buttons**: `<a href="…" class="button button2">Label</a>`, never `<button>` nested inside an `<a>` (invalid HTML — a `<button>` can't sit inside another interactive element). The `.button`/`.button2` classes work identically on a plain `<a>`.
- **Adding a gallery photo**: drop the image into `images/gallery/`, commit, and push. That's the whole process — the `build-gallery` workflow regenerates the tile markup and commits it back. Do **not** hand-write `<div class="gallery-item">` blocks; the block between the `<!-- gallery:start -->` and `<!-- gallery:end -->` markers in `gallery.html` is generated and any manual edit there is overwritten on the next push. Two things are worth knowing:
  - **Order comes from the number in the filename**, highest first, so the newest photo leads the page. Two filename shapes count as numbered: a `065-` style prefix (preferred — see below) or a plain word-then-number like `image64.jpg`. Anything else, including camera originals like `0K8A9860.JPG`, has no sequence number and sorts to the end of the page with a warning. This is deliberately strict: a shutter counter is not a position in the gallery, and treating it as one put a 2022 photo above everything shot since.
  - **Alt text comes from the filename**: `065-beach-engagement.jpg` orders the photo at 65 and becomes `alt="Beach engagement"`. A leading `NNN-` is stripped before the rest is read as words. Names like `image54.jpg` carry no description, so they produce an empty `alt` plus a warning in the build log.
  - **The naming convention worth adopting is `NNN-short-description.jpg`** — it sets the order and supplies the alt text in one go, which the legacy `imageNN.jpg` names cannot do. Leave gaps (010, 020, 030) so a photo can be slotted between two others later without renaming anything else.
  - Ordering used to come from EXIF capture dates. That was replaced because only two thirds of the photos carry a date and the fallback for the rest resolved to whichever commit last touched the file — so a routine rebuild in CI could reshuffle the whole page. Filenames are stable; commit dates are not.
- **Tile shape is computed, not chosen**: the generator picks the closest `item-*` class (defined in `css/style.css`) from the photo's true aspect ratio, so no photo is squeezed into a shape it wasn't shot in. The old hand-written grid tagged portrait photos as `item-4x3` and vice versa, which meant `object-fit: cover` was cropping them; every photo in the current set is a true 2:3 or 3:2 frame.
- **`css/demo.css` must not set typography.** It is a third-party template file loaded only by `gallery.html`. Its original `body`/`a` font-family rules and Raleway `@import` were removed because they made the Gallery page's nav and body text render in a different typeface to every other page — a bare `a { font-family }` rule beats the `futura-pt` that `nav ul li` passes down by inheritance. Site typography belongs in `stylesheet.css`, which sets a `body` baseline and states the nav's face on `nav ul li a` directly so third-party CSS can't win.
- **Portrait + text pairing** (used on About/Contact): wrap the `.AboutpicCrop` image div and the text content in a shared `.bio-layout` div, with the text further wrapped in `.bio-text`. This is a flexbox pairing (`stylesheet.css`) — don't reintroduce `float` on the image, which was the old approach and didn't wrap cleanly at narrow widths.
- Fonts are loaded via Typekit (`futura-pt`) and Google Fonts (`Poppins`) `@import`s at the top of `stylesheet.css` — both require network access, so pages will look different offline or with those blocked.
- Mobile responsiveness for the main site lives in one `@media (max-width: 600px)` block at the bottom of `stylesheet.css`; the gallery grid's own responsive breakpoints live separately in `css/style.css`.

## Git workflow

This repo is tracked in git and pushed to a private GitHub remote (`origin`, `nsandoz/nicky-sandoz-photography`, branch `main`). Every change made in a Claude Code session must be committed and pushed — this is how changes are logged and how old versions stay recoverable.

- **Commit granularity**: one commit per logical change (a completed edit or task), not one commit per file save. Each commit message should describe what changed and why in a sentence or two — write these the way the initial-commit message in this repo's history was written, as a model for tone and detail.
- **After completing a change**: stage and commit it (`git add -A && git commit -m "…"`), then push immediately (`git push`). Don't batch multiple unrelated changes into one commit, and don't leave commits unpushed at the end of a session — `origin/main` should always reflect the latest local commit.
- **Reverting to an old version**: `git log --oneline` to find the commit to go back to, then either:
  - `git revert <commit>` to undo one specific commit while keeping history (preferred — keeps the undone change visible in history and is safe on a shared branch).
  - `git checkout <commit> -- <file>` to restore a single file to an older version without touching anything else.
  - `git reset --hard <commit>` to roll the whole working tree back to that point (only when you're intentionally discarding everything after it — this rewrites history and needs `git push --force` afterward, so confirm before using it).
- `.gitignore` excludes `.DS_Store` and `debug.log` (local/OS noise, not part of the site).

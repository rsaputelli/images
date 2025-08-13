Website Image Licensing Audit — MVP

This Streamlit app scans a website for images and flags items that may require licensing review. It collects images from <img> tags and CSS background-image URLs, checks for stock-library domains, optionally extracts EXIF metadata ("Artist"), and provides quick reverse‑image search links.

✨ Features

Same‑site crawl (respects robots.txt).

Finds images in <img> tags and (optionally) in inline/linked CSS background-image rules.

Stock‑domain hinting: marks images hosted on common stock sites (Shutterstock, Getty, Adobe Stock, iStock, Pexels, Pixabay, etc.).

Optional EXIF read (EXIF tag 315: Artist).

Reverse‑image helpers: one‑click links to Google Images and TinEye (no scraping).

Adjustable crawl depth, concurrency, and resource limits.

Clickable links in‑app via table link columns.

Export CSV and Excel (Excel outputs true hyperlinks).

Passcode gate using Streamlit Secrets or env var.

Checkpoint resume: continue a partial crawl later (saved in session with optional downloadable checkpoint).

Note: The MVP doesn’t execute JavaScript, so images loaded dynamically by client‑side code may not be discovered.

🧱 Requirements

Add this to requirements.txt:

streamlit==1.37.1
requests>=2.31.0
beautifulsoup4>=4.12.3
pandas>=2.2.2
tldextract>=5.1.2
Pillow>=10.4.0
xlsxwriter>=3.2.0

All other imports are from the Python standard library.

▶️ Run Locally

Clone the repo

git clone https://github.com/<your-org>/<your-repo>.git
cd <your-repo>

Install dependencies

pip install -r requirements.txt

(Optional) Set a passcode (choose one):

export APP_PASSCODE="your-passcode"  # macOS/Linux
# setx APP_PASSCODE your-passcode    # Windows (new shell after this)

Run the app

streamlit run app.py

Open the local URL shown in terminal. If a passcode is set, enter it to unlock.

☁️ Deploy on Streamlit Cloud

Push the repo to GitHub.

In Streamlit Cloud, New app → pick your repo/branch and point Main file to app.py.

Secrets (gear icon → Secrets): add

APP_PASSCODE="your-passcode"

(If you skip this, the app runs without a passcode.)

Deploy.

🔧 How to Use

Start URL: paste the site’s homepage or a deep page within the site.

Scope & Depth:

Include subdomains — off by default. Turn on for multi‑subdomain sites.

Max crawl depth — typical 2–3 for MVP.

Limits (safety valves):

Max pages / Max images — caps the run (session‑scoped).

Per‑page image cap — stop collecting more than N images per page.

Per‑image size cap (MB) & Total download cap (MB) — throttles bytes fetched for EXIF/thumbs.

Fetch Policy:

Concurrency and Base delay (ms) — be polite; increase delay if the site is rate‑limited.

Features:

Capture CSS background images — finds background-image: url(...) in inline styles and linked CSS.

Attempt EXIF/IPTC — reads EXIF Artist if the file has EXIF and you’ve allowed bytes to be fetched.

Show thumbnails — displays small previews in the results table (more bytes; respects caps).

Click Run Audit.

Results Table

Columns include Page, Image URL, Source Type (IMG/CSS), Alt Text, Domain, Guessed Source, Content‑Type, Estimated Bytes, EXIF Artist, Width/Height (if available), reverse‑image links, Notes, and Risk Flags.

Links are clickable in the app. Use the sidebar Results Filters to narrow by stock/library, risk flags, or text search.

Risk Flags (MVP)

Stock source — ensure license (image hosted on a known stock domain)

No alt text (check provenance) (for <img> where alt is missing)

These are heuristic hints, not legal determinations. Use them to prioritize manual checks.

🔁 Resuming a Crawl

The app saves in‑session state automatically. If you re‑run and see the Resumable state banner, you can:

Resume where I left off from the main banner, or

Use Continue from saved state in the sidebar.

Checkpoint file: Download a JSON checkpoint from the results screen to resume later or on another machine.

Load it via Resume / Checkpoint → Load checkpoint.

When resuming, the sliders for pages/images/bytes act as additional limits for this run (delta, not totals).

📤 Exporting

CSV: simple text; link clickability depends on your viewer.

Excel: includes true hyperlinks in Page, Image URL, Google Images, TinEye columns.

🤝 Robots & Ethics

The crawler respects robots.txt via urllib.robotparser. If the start URL is disallowed, the app aborts.

Keep concurrency modest and add delay, especially on smaller sites.

Use only on sites you own/manage or have permission to audit.

🧩 Troubleshooting

No passcode prompt: ensure APP_PASSCODE is set in Secrets (Streamlit Cloud) or as an environment variable locally.

Blocked crawl: check robots.txt and reduce depth, concurrency, or enable Include subdomains.

Few/No images: the site may use JS‑loaded assets (MVP doesn’t execute JS). Try enabling CSS captures.

No EXIF/Width/Height: the image format may not carry EXIF, or size caps prevented fetching bytes.

Hit limits: increase sliders and re‑run, or use the resume workflow.

📄 License & Credits

This tool provides heuristics to aid licensing review. It is not legal advice. Confirm rights before using any asset.

Stock domain list is non‑exhaustive and may need updates per organization.

Staff How‑To (One‑Pager)

Purpose: Quickly scan a site you manage for images that might need a licensing check.

1) Access

Go to the Streamlit app URL. Enter the passcode if prompted (ask your admin if you don’t have it).

2) Run a Scan

Paste the Start URL (usually the homepage).

Leave Include subdomains off at first; increase Max crawl depth to 2–3.

Keep default Limits; you can raise them later.

Under Features:

Start with EXIF on.

Turn on CSS backgrounds only if you need to catch hero/section backgrounds (may include fonts/gradients, some noise).

Turn on Thumbnails if you want previews (uses more data; slower).

Click Run Audit.

3) Review Results

Use Show likely stock/library only to focus on stock‑hosted images.

Use Show rows with risk flags to focus review.

Use Search to filter by URL, page, alt text, or domain.

Click Google Images / TinEye per row to do a quick provenance check.

4) Export & Share

Click Download Excel for a spreadsheet with clickable links.

Share the file with legal/brand/creative teams for follow‑up.

5) Resume Later

If you hit limits, raise them and click Continue from saved state.

Or download a checkpoint and re‑load it another day.

6) What do Risk Flags mean?

Stock source — ensure license: hosted on a known stock domain (confirm you have a license).

No alt text (check provenance): missing alt on an <img> tag; not proof of misuse, but worth verifying.

7) Good Citizen Tips

Avoid running with very high concurrency or no delay on small/fragile sites.

Respect your organization’s policies and any site’s terms of use.

Changelog (MVP)

Passcode gate using APP_PASSCODE secret/env.

Resume banner + checkpoint import/export.

Clickable links in app + Excel hyperlink export.

Optional CSS background scanning.

EXIF Artist extraction; optional thumbnails.

Website Image Licensing Audit — MVP (Streamlit)

Audit a website for images/graphics that may require licensing review.
The app crawls a domain (respecting robots.txt), collects images from <img> and CSS background-image: url(...), flags likely stock/library sources, optionally extracts EXIF “Artist,” and exports a CSV/Excel report.

✨ Features

Same‑domain crawl with depth & page limits

Image extraction from HTML and linked CSS

Stock/library domain heuristics (Shutterstock, Getty, Adobe Stock, iStock, Unsplash, Pexels, Pixabay, etc.)

Optional EXIF/IPTC “Artist” extraction (size‑capped)

Reverse‑image quick links (Google Images / TinEye)

Filters (stock‑only, risk‑only, search)

CSV/Excel export

Passcode gate (optional) via Streamlit Secrets

📦 Requirements

streamlit==1.37.1
requests>=2.31.0
beautifulsoup4>=4.12.3
pandas>=2.2.2
tldextract>=5.1.2
Pillow>=10.4.0
xlsxwriter>=3.2.0

These are already listed in requirements.txt. No additional packages are required for the MVP. (Optional: requests-file>=1.5.1 if you wish to allow tldextract to refresh the public suffix list from the network.)

🚀 Quick Start (Local)

git clone https://github.com/<you>/image-licensing-audit.git
cd image-licensing-audit
pip install -r requirements.txt
streamlit run app.py

Open the local URL shown in your terminal.

☁️ Deploy on Streamlit Cloud

Push this repo to GitHub.

Go to share.streamlit.io → New app.

Select the repo & branch, set Main file path to app.py.

Deploy and share the URL with staff.

No API keys are required for the MVP. If you later add a reverse‑image API (TinEye/Bing Visual Search), store keys in Secrets.

🔒 Optional Passcode Gate (recommended)

Add a lightweight passcode check for staff‑only access.

1) Set a secret on Streamlit Cloud

App → ⋮ > Settings > Secrets:

APP_PASSCODE = "yourpasscode"

2) Code snippet (already included near the top of app.py)

PASSCODE = st.secrets.get("APP_PASSCODE") or os.getenv("APP_PASSCODE")
if PASSCODE:  # only enforce if configured
    user_code = st.text_input("Enter passcode", type="password")
    if user_code != PASSCODE:
        st.stop()

If the secret is unset, the gate is automatically disabled (useful for dev branches).

🧭 How to Use

Enter the Start URL (e.g., https://example.com).

In the sidebar, configure:

Include subdomains (off by default)

Max crawl depth (default 3)

Max pages (default 100)

Max images (default 1,000)

Per‑page image cap (default 50)

Per‑image size cap (MB) (default 5)

Total download cap (MB) (default 200)

Concurrency (default 5) and Base delay (ms) (default 300)

Capture CSS backgrounds (on), Attempt EXIF/IPTC (on), Show thumbnails (off)

Power user (optional) to lift caps (use with caution)

Click Run Audit. You can Stop any time.

Filter results and Download CSV/Excel.

🔧 Default Limits (MVP)

Scope: same registrable domain.

Depth: 3 levels from the start page.

Max pages: 100 (hard cap 300).

Max images: 1,000 (hard cap 2,000).

Per‑page cap: 50 images.

Per‑image size cap: 5 MB.

Total download cap: 200 MB.

Concurrency: 5 threads.

Delay: 300 ms base between requests.

CSS backgrounds: enabled.

EXIF: enabled (subject to size caps).

These are adjustable via sidebar sliders.

✅ What Gets Flagged

Images hosted on known stock/library domains → “Stock source — ensure license.”

Missing alt text → “No alt text (check provenance).”

Quick links are provided to Google Images & TinEye (no scraping of results).

🧱 Limitations (by design for MVP)

No headless browser: JS‑inserted images on heavy SPA frameworks may be missed. (Future: Playwright/Selenium add‑on.)

robots.txt respected: Disallowed paths/assets aren’t fetched.

Reverse search: Click‑out links only. Use official APIs if you want automated matching.

🧩 Roadmap (optional enhancements)

Sitemap‑first crawling

Job history & scheduled re‑scans

Auth/SSO and per‑user run logs

TinEye/Bing Visual Search API auto‑annotation

Trademark/celebrity/logo detection heuristics

Org multi‑tenant mode & shared reports

🛟 Troubleshooting

“No images found.”

Verify the URL is correct and public.

Increase Max pages/Depth, enable Include subdomains.

Ensure robots.txt allows crawling of pages and CSS.

Run stops early.

You likely hit pages/images/bytes caps. Raise limits or enable Power user (use with caution).

EXIF not appearing.

Many images are stripped of EXIF. Also check size caps and total byte cap.

Dynamic content missing.

The MVP doesn’t execute JS. Consider a Playwright add‑on for SPA sites.

🔒 Legal & Ethics

Respect each site’s robots.txt and Terms of Service.

This tool flags licensing risks; it does not determine legal status. Final review is a human decision.

Handle exported reports per your organization’s privacy policy.

🏷️ License

MIT (or update to your preferred license).

📁 Repo Structure

.
├─ app.py                # Streamlit app (executable code only)
├─ requirements.txt
├─ README.md             # This document
└─ Staff_How_To.pdf      # Optional one‑pager for staff

🙋 Support / Contributions

Open an issue or PR with a clear description and steps to reproduce.

For feature requests, note whether it should remain MVP‑light or be a “pro” upgrade (API integrations, auth, scheduling, etc.).

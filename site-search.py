import os
import json
import base64
import streamlit as st
import requests
from urllib.parse import urljoin, urlparse
from urllib import robotparser
from bs4 import BeautifulSoup
import re
import pandas as pd
import tldextract
import time
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image, UnidentifiedImageError

# ==========================================
# Website Image Licensing Audit — MVP (app)
# ==========================================
# NOTE: README content must live in README.md, not inside this file.
# This file contains only executable Streamlit code.

# --------------------------
# App Config & Passcode Gate
# --------------------------
st.set_page_config(page_title="Website Image Licensing Audit (MVP)", layout="wide")

PASSCODE = st.secrets.get("APP_PASSCODE") or os.getenv("APP_PASSCODE")
if PASSCODE:
    if not st.session_state.get("_authed", False):
        with st.form("passcode_gate"):
            user_code = st.text_input("Enter passcode", type="password")
            submitted = st.form_submit_button("Unlock")
        if submitted:
            if (user_code or "").strip() == str(PASSCODE).strip():
                st.session_state["_authed"] = True
            else:
                st.error("Invalid passcode.")
        if not st.session_state.get("_authed", False):
            st.stop()

st.title("🕵️ Website Image Licensing Audit — MVP")

# --------------------------
# Quick Resume Banner (main area)
# --------------------------
if st.session_state.get("crawl_state"):
    _cs = st.session_state.crawl_state
    _su = (_cs or {}).get("start_url")
    _pp = int((_cs or {}).get("pages_processed", 0))
    _im = int((_cs or {}).get("images_found", 0))
    _dom = urlparse(_su).netloc if _su else ""
    with st.container(border=True):
        st.write(f"**Resumable state detected** for `{_dom}` — total pages: {_pp}, total images: {_im}.")
        st.caption("When resuming, slider limits apply to **additional** pages/images/bytes for this run.")
        c1, c2 = st.columns([1,1])
        with c1:
            if st.button("▶️ Resume where I left off"):
                st.session_state["_resume_request"] = True
        with c2:
            if st.button("🗑️ Discard saved state"):
                st.session_state["crawl_state"] = None
                st.rerun()

# --------------------------
# Constants
# --------------------------
DEFAULT_HEADERS = {
    "User-Agent": "ImageLicenseAuditor/1.0 (+https://example.org; contact=webmaster@example.org)"
}

STOCK_DOMAINS = {
    "shutterstock.com", "gettyimages.com", "istockphoto.com", "adobestock.com", "stock.adobe.com",
    "depositphotos.com", "dreamstime.com", "alamy.com", "123rf.com", "bigstockphoto.com",
    "canstockphoto.com", "pond5.com", "pixabay.com", "unsplash.com", "pexels.com"
}

IMG_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"}
URL_IN_CSS = re.compile(r"url\(([^)]+)\)")

if "crawl_state" not in st.session_state:
    st.session_state.crawl_state = None  # holds resumable state dict

# --------------------------
# Sidebar Controls
# --------------------------
with st.sidebar:
    st.header("Settings")
    start_url = st.text_input(
        "Start URL",
        value=(st.session_state.crawl_state.get("start_url") if st.session_state.get("crawl_state") else ""),
        placeholder="https://example.com",
    )

    # Determine if we are in a resume context for this start_url
    resuming_context = bool(
        st.session_state.get("crawl_state") and st.session_state.crawl_state.get("start_url") == start_url
    )

    st.markdown("**Scope & Depth**")
    include_subdomains = st.checkbox("Include subdomains", value=False)
    depth_max = st.slider("Max crawl depth", min_value=1, max_value=5, value=3)

    st.markdown("**Limits**")
    max_pages_default = 100
    max_images_default = 1000
    per_page_img_cap_default = 50
    per_image_size_mb_default = 5
    total_bytes_cap_mb_default = 200

    # On resume, these sliders mean "additional this run"
    pages_label = "Additional pages this run" if resuming_context else "Max pages"
    images_label = "Additional images this run" if resuming_context else "Max images (total)"
    bytes_label = "Additional download cap (MB) this run" if resuming_context else "Total download cap (MB)"

    max_pages = st.slider(pages_label, 10, 300, max_pages_default, step=10)
    max_images = st.slider(images_label, 100, 2000, max_images_default, step=100)
    per_page_img_cap = st.slider("Per-page image cap", 10, 100, per_page_img_cap_default, step=5)
    per_image_size_mb = st.slider("Per-image size cap (MB)", 1, 20, per_image_size_mb_default)
    total_bytes_cap_mb = st.slider(bytes_label, 50, 400, total_bytes_cap_mb_default, step=25)

    st.caption("On resume, page/image/byte limits apply to the **additional** work done in this run.")

    st.markdown("**Fetch Policy**")
    concurrency = st.slider("Concurrency (workers)", 1, 10, 5)
    base_delay_ms = st.slider("Base delay between requests (ms)", 0, 1000, 300, step=50)

    st.markdown("**Features**")
    parse_css_backgrounds = st.checkbox("Capture CSS background images", value=True)
    try_exif = st.checkbox("Attempt EXIF/IPTC (≤ size cap)", value=True)
    show_thumbs = st.checkbox("Show thumbnails (may be slow)", value=False)

    st.markdown("**Results Filters**")
    st.checkbox("Show likely stock/library only", value=False, key="filter_only_stock")
    st.checkbox("Show rows with risk flags", value=False, key="filter_only_risky")
    st.text_input("Search URL/Alt/Domain contains…", value="", key="filter_search")

    st.markdown("**Power User**")
    power = st.checkbox("Enable power-user mode (lifts caps, use cautiously)", value=False)
    if power:
        st.info("Power user mode enabled. Be respectful of target sites and your Streamlit resource limits.")

    st.markdown("**Resume / Checkpoint**")
    resume_upload = st.file_uploader("Resume from checkpoint (.json)", type=["json"], help="Load a previously saved crawl state.")
    load_clicked = st.button("Load checkpoint")
    cont_clicked = st.button("Continue from saved state") if st.session_state.get("crawl_state") else False
    reset_clicked = st.button("Reset saved state") if st.session_state.get("crawl_state") else False

    go = st.button("Run Audit", type="primary")
    stop = st.button("Stop")

# Handle checkpoint load/reset in sidebar
if resume_upload is not None and load_clicked:
    try:
        cp = json.load(resume_upload)
        state = cp.get("state", {})
        # Basic sanity check
        if not state or "queue" not in state:
            st.sidebar.error("Invalid checkpoint file.")
        else:
            st.session_state.crawl_state = state
            st.sidebar.success("Checkpoint loaded. Click 'Continue from saved state' or 'Run Audit' to resume.")
    except Exception as e:
        st.sidebar.error(f"Failed to load checkpoint: {e}")

if reset_clicked:
    st.session_state.crawl_state = None
    st.sidebar.info("Saved state cleared.")

# Stop flag
if "_stop" not in st.session_state:
    st.session_state._stop = False
if stop:
    st.session_state._stop = True

# Allow 'Continue' from saved state
if cont_clicked:
    go = True
# Allow Resume from main banner
if st.session_state.get("_resume_request"):
    go = True
    st.session_state["_resume_request"] = False

# --------------------------
# Helpers
# --------------------------

def same_scope(url: str, root: str, include_subs: bool) -> bool:
    try:
        t_root = tldextract.extract(root)
        t_url = tldextract.extract(url)
        same_reg = (t_root.domain == t_url.domain and t_root.suffix == t_url.suffix)
        if not same_reg:
            return False
        if include_subs:
            return True
        return (t_root.subdomain == t_url.subdomain)
    except Exception:
        return False


def get_robots_session(base_url: str):
    parsed = urlparse(base_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = robotparser.RobotFileParser()
    try:
        rp.set_url(robots_url)
        rp.read()
    except Exception:
        pass
    s = requests.Session()
    s.headers.update(DEFAULT_HEADERS)
    return rp, s


def polite_get(session: requests.Session, url: str, delay_ms: int, timeout: int = 15):
    time.sleep(delay_ms / 1000.0)
    try:
        return session.get(url, timeout=timeout)
    except Exception:
        return None


def extract_img_links_from_html(base_url: str, html: str, per_page_cap: int):
    soup = BeautifulSoup(html, 'html.parser')
    found = []
    for img in soup.find_all('img'):
        src = img.get('src') or img.get('data-src')
        if not src:
            continue
        u = urljoin(base_url, src)
        alt = img.get('alt') or ''
        found.append((u, 'IMG Tag', alt))
        if len(found) >= per_page_cap:
            break

    for el in soup.find_all(style=True):
        style = el.get('style')
        for m in URL_IN_CSS.findall(style or ''):
            u = m.strip('\"\'')
            u = urljoin(base_url, u)
            found.append((u, 'CSS Background', ''))
            if len(found) >= per_page_cap:
                break
        if len(found) >= per_page_cap:
            break

    css_links = []
    for link in soup.find_all('link', rel=lambda x: x and 'stylesheet' in x):
        href = link.get('href')
        if href:
            css_links.append(urljoin(base_url, href))

    return found, css_links


def extract_urls_from_css(css_text: str, base_url: str):
    urls = []
    for m in URL_IN_CSS.findall(css_text or ''):
        u = m.strip('\"\'')
        u = urljoin(base_url, u)
        urls.append(u)
    return urls


def file_ext(url: str) -> str:
    path = urlparse(url).path.lower()
    for ext in IMG_EXTS:
        if path.endswith(ext):
            return ext
    return ''


def domain_of(url: str) -> str:
    try:
        return tldextract.extract(url).registered_domain
    except Exception:
        return ''


def guessed_source(url: str) -> str:
    dom = domain_of(url)
    if dom in STOCK_DOMAINS:
        return f"Stock / Library ({dom})"
    return "Unknown / Site-hosted"


def reverse_links(url: str):
    g = f"https://www.google.com/searchbyimage?image_url={requests.utils.quote(url, safe='')}"
    t = f"https://tineye.com/search?url={requests.utils.quote(url, safe='')}"
    return g, t


def head_size(session: requests.Session, url: str, timeout: int = 15):
    try:
        r = session.head(url, allow_redirects=True, timeout=timeout)
        size = r.headers.get('Content-Length')
        ct = r.headers.get('Content-Type', '')
        return int(size) if size and size.isdigit() else None, ct
    except Exception:
        return None, ''


def fetch_bytes(session: requests.Session, url: str, max_bytes: int):
    try:
        r = session.get(url, stream=True, timeout=20)
        r.raise_for_status()
        buf = BytesIO()
        total = 0
        for chunk in r.iter_content(8192):
            if chunk:
                buf.write(chunk)
                total += len(chunk)
                if total > max_bytes:
                    break
        buf.seek(0)
        return buf, total
    except Exception:
        return None, 0


def try_make_thumb(img_bytes: BytesIO, max_px: int = 128) -> BytesIO | None:
    try:
        with Image.open(img_bytes) as im:
            im = im.convert("RGB") if im.mode not in ("RGB", "RGBA") else im
            im.thumbnail((max_px, max_px))
            out = BytesIO()
            im.save(out, format='PNG')
            out.seek(0)
            return out
    except (UnidentifiedImageError, OSError):
        return None


def make_checkpoint_dict(state: dict, settings: dict) -> dict:
    # Convert non-JSON types (set/tuples) to JSON-serializable structures
    serializable_state = {
        "start_url": state.get("start_url"),
        "visited_pages": sorted(list(state.get("visited_pages", []))),
        "queue": list(state.get("queue", [])),
        "depth": state.get("depth", {}),
        "pages_processed": int(state.get("pages_processed", 0)),
        "images_found": int(state.get("images_found", 0)),
        "total_bytes_downloaded": int(state.get("total_bytes_downloaded", 0)),
        "rows": state.get("rows", []),
        "css_queue": list(state.get("css_queue", [])),  # list of [page_url, css_url]
    }
    return {"settings": settings, "state": serializable_state}

# --------------------------
# Main Audit Logic (with resume/delta limits)
# --------------------------
if go:
    st.session_state._stop = False

    if not start_url:
        st.error("Please enter a start URL.")
        st.stop()

    # Initialize or resume state
    if st.session_state.crawl_state and st.session_state.crawl_state.get("start_url") == start_url:
        state = st.session_state.crawl_state
        visited_pages = set(state.get("visited_pages", []))
        q = list(state.get("queue", []))
        depth = dict(state.get("depth", {}))
        pages_processed = int(state.get("pages_processed", 0))
        images_found = int(state.get("images_found", 0))
        total_bytes_downloaded = int(state.get("total_bytes_downloaded", 0))
        rows = list(state.get("rows", []))
        css_queue = list(state.get("css_queue", []))
        # Baselines for delta-limits this run
        baseline_pages = pages_processed
        baseline_images = images_found
        baseline_bytes = total_bytes_downloaded
        resuming_now = True
    else:
        visited_pages = set()
        q = [start_url]
        depth = {start_url: 0}
        pages_processed = 0
        images_found = 0
        total_bytes_downloaded = 0
        rows = []
        css_queue = []
        baseline_pages = 0
        baseline_images = 0
        baseline_bytes = 0
        resuming_now = False

    rp, session = get_robots_session(start_url)

    if rp and not rp.can_fetch(DEFAULT_HEADERS["User-Agent"], start_url):
        st.warning("robots.txt disallows crawling the start URL. Aborting.")
        st.stop()

    progress = st.progress(0)
    status = st.empty()

    def added_pages() -> int:
        return max(0, pages_processed - baseline_pages)

    def added_images() -> int:
        return max(0, images_found - baseline_images)

    def added_bytes() -> int:
        return max(0, total_bytes_downloaded - baseline_bytes)

    while q and not st.session_state._stop:
        # Per-run (delta) page cap
        if added_pages() >= max_pages:
            status.info("Hit additional page limit for this run. You can raise the limit and resume again.")
            break

        url = q.pop(0)
        if url in visited_pages:
            continue
        visited_pages.add(url)
        d = depth.get(url, 0)

        if d > depth_max:
            continue

        if rp and not rp.can_fetch(DEFAULT_HEADERS["User-Agent"], url):
            continue

        resp = polite_get(session, url, base_delay_ms)
        if not resp or not (200 <= resp.status_code < 300):
            continue

        content_type = resp.headers.get('Content-Type', '')
        if 'text/html' not in content_type:
            continue

        html = resp.text
        page_imgs, css_links = extract_img_links_from_html(url, html, per_page_img_cap)

        if parse_css_backgrounds:
            for css in css_links:
                if same_scope(css, start_url, include_subdomains):
                    css_queue.append((url, css))

        soup = BeautifulSoup(html, 'html.parser')
        for a in soup.find_all('a', href=True):
            href = urljoin(url, a['href'])
            href = href.split('#')[0]
            if not same_scope(href, start_url, include_subdomains):
                continue
            if href not in visited_pages and href not in depth:
                depth[href] = d + 1
                if d + 1 <= depth_max:
                    q.append(href)

        to_process = list({u for (u, _, _) in page_imgs})
        results = []
        with ThreadPoolExecutor(max_workers=concurrency) as ex:
            futs = {ex.submit(head_size, session, u): u for u in to_process}
            for fut in as_completed(futs):
                u = futs[fut]
                size, ct = fut.result()
                results.append((u, size, ct))

        for (u, stype, alt) in page_imgs:
            if added_images() >= max_images or st.session_state._stop:
                break

            ext = file_ext(u)
            dom = domain_of(u)
            source_guess = guessed_source(u)
            g_link, t_link = reverse_links(u)

            match = next((r for r in results if r[0] == u), None)
            est_bytes = match[1] if match else None
            content_type_img = match[2] if match else ''

            size_ok = True
            note = ""
            if est_bytes is not None and est_bytes > per_image_size_mb * 1024 * 1024:
                size_ok = False
                note = "Skipped (exceeds per-image size cap)"

            exif_author = ""
            thumb_data = None
            width = None
            height = None
            # Download bytes if needed for EXIF and/or thumbnails
            need_fetch = (try_exif or show_thumbs) and size_ok and (content_type_img.startswith("image/") or ext in IMG_EXTS)
            if need_fetch:
                if added_bytes() < total_bytes_cap_mb * 1024 * 1024:
                    buf, n = fetch_bytes(session, u, per_image_size_mb * 1024 * 1024)
                    total_bytes_downloaded += n
                    if buf:
                        if try_exif:
                            try:
                                with Image.open(buf) as im:
                            width, height = im.size
                            exif = im.getexif()
                                    if exif:
                                        artist = exif.get(315)
                                        if artist:
                                            exif_author = str(artist)
                            except (UnidentifiedImageError, OSError):
                                pass
                        if show_thumbs:
                            thumb = try_make_thumb(buf)
                            if thumb:
                                thumb_data = f"data:image/png;base64,{base64.b64encode(thumb.read()).decode('ascii')}"
                else:
                    note = (note + "; " if note else "") + "Skipped (hit additional download cap this run)"

            risk = []
            if dom in STOCK_DOMAINS:
                risk.append("Stock source — ensure license")
            if not alt:
                risk.append("No alt text (check provenance)")

            rows.append({
                "Page": url,
                "Image URL": u,
                "Source Type": stype,
                "Alt Text": alt,
                "Domain": dom,
                "Guessed Source": source_guess,
                "Content-Type": content_type_img,
                "Estimated Bytes": est_bytes,
                "EXIF Artist": exif_author,
                "Width": width,
                "Height": height,
                "Google Images": g_link,
                "TinEye": t_link,
                "Thumbnail": thumb_data,
                "Notes": note,
                "Risk Flags": ", ".join(risk)
            })
            images_found += 1

        pages_processed += 1
        # Progress and status use delta pages as denominator
        progress.progress(min(1.0, added_pages() / max(1, max_pages)))
        status.write(
            f"Total pages {pages_processed} (+{added_pages()} this run), "
            f"images {images_found} (+{added_images()} this run)."
        )

        if added_images() >= max_images:
            status.info("Hit additional image limit for this run. You can raise the limit and resume again.")
            break

        if parse_css_backgrounds and css_queue and not st.session_state._stop:
            with ThreadPoolExecutor(max_workers=min(concurrency, 4)) as ex:
                futs = {ex.submit(polite_get, session, css_url, base_delay_ms): (page_url, css_url)
                        for (page_url, css_url) in css_queue}
                css_queue = []
                for fut in as_completed(futs):
                    page_url, css_url = futs[fut]
                    resp_css = fut.result()
                    if not resp_css or resp_css.status_code != 200:
                        continue
                    css_text = resp_css.text
                    for u in extract_urls_from_css(css_text, css_url):
                        if added_images() >= max_images:
                            break
                        ext = file_ext(u)
                        size, ct = head_size(session, u)
                        size_ok = True
                        note = ""
                        if size is not None and size > per_image_size_mb * 1024 * 1024:
                            size_ok = False
                            note = "Skipped (exceeds per-image size cap)"
                        exif_author = ""
                        thumb_data = None
                        width = None
                        height = None
                        need_fetch = (try_exif or show_thumbs) and size_ok and (ct.startswith("image/") or ext in IMG_EXTS)
                        if need_fetch:
                            if added_bytes() < total_bytes_cap_mb * 1024 * 1024:
                                buf, n = fetch_bytes(session, u, per_image_size_mb * 1024 * 1024)
                                total_bytes_downloaded += n
                                if buf:
                                    if try_exif:
                                        try:
                                            with Image.open(buf) as im:
                                                width, height = im.size
                                                exif = im.getexif()
                                                if exif:
                                                    artist = exif.get(315)
                                                    if artist:
                                                        exif_author = str(artist)
                                        except (UnidentifiedImageError, OSError):
                                            pass
                                    if show_thumbs:
                                        thumb = try_make_thumb(buf)
                                        if thumb:
                                            thumb_data = f"data:image/png;base64,{base64.b64encode(thumb.read()).decode('ascii')}"
                            else:
                                note = (note + "; " if note else "") + "Skipped (hit additional download cap this run)"

                        g_link, t_link = reverse_links(u)
                        dom = domain_of(u)
                        rows.append({
                        "Page": page_url,
                        "Image URL": u,
                        "Source Type": "CSS Background",
                        "Alt Text": "",
                        "Domain": dom,
                        "Guessed Source": guessed_source(u),
                        "Content-Type": ct,
                        "Estimated Bytes": size,
                        "EXIF Artist": exif_author,
                        "Width": width,
                        "Height": height,
                        "Google Images": g_link,
                        "TinEye": t_link,
                        "Thumbnail": thumb_data,
                            "Notes": note,
                            "Risk Flags": "Stock source — ensure license" if dom in STOCK_DOMAINS else ""
                        })
                        images_found += 1
                        if added_images() >= max_images:
                            break

        # Persist state after each page
        st.session_state.crawl_state = {
            "start_url": start_url,
            "visited_pages": list(visited_pages),
            "queue": list(q),
            "depth": depth,
            "pages_processed": pages_processed,
            "images_found": images_found,
            "total_bytes_downloaded": total_bytes_downloaded,
            "rows": rows,
            "css_queue": css_queue,
        }

    # --------------------------
    # Results & Export + Checkpoint
    # --------------------------
    if rows:
        df = pd.DataFrame(rows)
        finished = (not q) and (not css_queue)
        if finished:
            st.success(
                f"Audit complete: total pages {pages_processed}, total images {images_found}."
            )
        else:
            st.info(
                f"Partial results: total pages {pages_processed}, total images {images_found}. "
                f"You can resume later."
            )

        # Apply filters from sidebar (works even before the first run next time)
        only_stock = st.session_state.get("filter_only_stock", False)
        only_risky = st.session_state.get("filter_only_risky", False)
        search = st.session_state.get("filter_search", "")

        view = df.copy()
        view['Guessed Source'] = view['Guessed Source'].fillna('')
        view['Risk Flags'] = view['Risk Flags'].fillna('')
        if only_stock:
            view = view[view['Guessed Source'].str.contains('Stock / Library', na=False)]
        if only_risky:
            view = view[view['Risk Flags'].str.len() > 0]
        if search:
            mask = (
                view['Image URL'].astype(str).str.contains(search, case=False, na=False) |
                view['Page'].astype(str).str.contains(search, case=False, na=False) |
                view['Alt Text'].astype(str).str.contains(search, case=False, na=False) |
                view['Domain'].astype(str).str.contains(search, case=False, na=False)
            )
            view = view[mask]

        # Drop Thumbnail from view if toggle off
        render_df = view.copy()
        if not show_thumbs:
            render_df = render_df.drop(columns=['Thumbnail'], errors='ignore')

        # Clickable links + optional image thumbnails in UI
        col_cfg = {
            "Image URL": st.column_config.LinkColumn("Image URL"),
            "Google Images": st.column_config.LinkColumn("Google Images"),
            "TinEye": st.column_config.LinkColumn("TinEye"),
        }
        if show_thumbs and 'Thumbnail' in render_df.columns:
            col_cfg["Thumbnail"] = st.column_config.ImageColumn("Thumbnail")

        st.data_editor(
            render_df,
            use_container_width=True,
            hide_index=True,
            disabled=True,
            column_config=col_cfg,
        )

        def to_excel_bytes(df_: pd.DataFrame) -> bytes:
            export = df_.drop(columns=['Thumbnail'], errors='ignore').copy()
            out = BytesIO()
            with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
                export.to_excel(writer, sheet_name="Audit", index=False)
                ws = writer.sheets["Audit"]
                # Make certain columns clickable
                url_cols = [c for c in ["Page", "Image URL", "Google Images", "TinEye"] if c in export.columns]
                for r in range(len(export)):
                    for c in url_cols:
                        val = export.iloc[r][c]
                        if isinstance(val, str) and val.startswith(("http://", "https://")):
                            ws.write_url(r+1, export.columns.get_loc(c), val, string=c)
            out.seek(0)
            return out.read()

        csv_bytes = render_df.drop(columns=['Thumbnail'], errors='ignore').to_csv(index=False).encode('utf-8')
        xlsx_bytes = to_excel_bytes(view)

        st.download_button("Download CSV", data=csv_bytes, file_name="image_licensing_audit.csv", mime="text/csv")
        st.download_button("Download Excel", data=xlsx_bytes, file_name="image_licensing_audit.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        # Offer a checkpoint download to resume later
        settings = {
            "include_subdomains": include_subdomains,
            "depth_max": depth_max,
            "max_pages": max_pages,
            "max_images": max_images,
            "per_page_img_cap": per_page_img_cap,
            "per_image_size_mb": per_image_size_mb,
            "total_bytes_cap_mb": total_bytes_cap_mb,
            "concurrency": concurrency,
            "base_delay_ms": base_delay_ms,
            "parse_css_backgrounds": parse_css_backgrounds,
            "try_exif": try_exif,
        }
        cp_dict = make_checkpoint_dict(st.session_state.crawl_state, settings)
        cp_bytes = json.dumps(cp_dict).encode('utf-8')
        st.download_button("Download checkpoint to resume later", data=cp_bytes, file_name="audit_checkpoint.json", mime="application/json")

        st.caption(
            "Notes: You can resume a partial crawl using the sidebar 'Resume from checkpoint' loader, the 'Continue from saved state' button, or the main 'Resume' panel. Limits apply to additional work this run."
        )
    else:
        st.warning("No images found or crawl blocked. Try adjusting limits, enabling subdomains, or verifying the start URL.")



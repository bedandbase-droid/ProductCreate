import base64
import io
import json
import math
import os
import re
import shutil
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
import streamlit as st
from bs4 import BeautifulSoup
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    OpenAI,
    RateLimitError,
)
from PIL import Image, ImageOps


# ============================================================
# APP CONFIG
# ============================================================

st.set_page_config(
    page_title="That Couch Place - AI Fabric Studio",
    page_icon="🛋️",
    layout="wide",
)

st.title("🛋️ That Couch Place — AI Fabric Studio")
st.caption(
    "Upload one furniture photo, choose fabric names, and generate each "
    "variation safely through a resumable one-at-a-time queue."
)

APP_DIR = Path(__file__).resolve().parent
SWATCH_DIR = APP_DIR / "swatches"
DATA_DIR = APP_DIR / "data"
JOBS_DIR = DATA_DIR / "jobs"
LIBRARY_FILE = DATA_DIR / "fabric_library.json"

FABRIC_PAGE_DEFAULT = "https://thatcouchplace.co.za/pages/fabric-options"

# Precision editing model recommended for this use case.
DEFAULT_MODEL = "gpt-image-2.5-sunburst"

# We manage retries ourselves so the UI never hides a very long chain of retries.
API_TIMEOUT_SECONDS = 180.0
MAX_ATTEMPTS_PER_SWATCH = 3
RETRY_DELAYS_SECONDS = [5, 10]
PAUSE_BETWEEN_SWATCHES_SECONDS = 0.75

CATEGORY_ORDER = [
    "Buffalo",
    "Poly Linen",
    "PU Leather",
    "Velvet",
    "Corduroy",
    "Other",
]

for folder in (SWATCH_DIR, DATA_DIR, JOBS_DIR):
    folder.mkdir(parents=True, exist_ok=True)


# ============================================================
# GENERAL HELPERS
# ============================================================

def utc_now():
    return datetime.now(timezone.utc).isoformat()


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")


def clean_display_name(filename):
    name = Path(filename).stem
    for token in (
        "_Fabric_Swatch",
        "_fabric_swatch",
        "-Fabric-Swatch",
        "-fabric-swatch",
        "_swatch",
        "-swatch",
    ):
        name = name.replace(token, "")
    return re.sub(r"[_-]+", " ", name).strip().title()


def safe_error_text(exc, max_len=700):
    text = str(exc).strip() or exc.__class__.__name__
    return text if len(text) <= max_len else text[:max_len] + "…"


def atomic_write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    tmp.replace(path)


def read_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def get_configured_api_key():
    # 1) Streamlit secrets
    try:
        key = st.secrets.get("OPENAI_API_KEY", "")
        if key:
            return str(key).strip()
    except Exception:
        pass

    # 2) Environment variable
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if key:
        return key

    # 3) Session-only sidebar entry
    return st.session_state.get("api_key_input", "").strip()


def image_bytes_to_png(uploaded_bytes):
    with Image.open(io.BytesIO(uploaded_bytes)) as im:
        im = ImageOps.exif_transpose(im)
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGBA" if "A" in im.getbands() else "RGB")

        buf = io.BytesIO()
        im.save(buf, format="PNG")
        return buf.getvalue(), im.size


def resize_result_to_exact_source_size(image_bytes, target_size):
    with Image.open(io.BytesIO(image_bytes)) as im:
        im = ImageOps.exif_transpose(im)
        if im.size == tuple(target_size):
            return image_bytes

        resized = im.resize(tuple(target_size), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        resized.save(out, format="PNG")
        return out.getvalue()


def calculate_api_size(width, height):
    """
    Preserve the source aspect ratio while producing a valid GPT Image 2.5 size:
    - width/height multiples of 16
    - aspect ratio between 1:3 and 3:1
    - 655,360 to 8,294,400 total pixels
    - max edge <= 3840

    We target roughly 1.57MP (similar to 1536x1024) for a good quality/latency
    balance, while retaining the source aspect ratio.
    """
    width = max(int(width), 1)
    height = max(int(height), 1)
    ratio = width / height

    # Clamp only if the source is outside the API's supported ratio.
    ratio = min(max(ratio, 1 / 3), 3)

    target_pixels = 1_572_864  # 1536 x 1024
    api_w = math.sqrt(target_pixels * ratio)
    api_h = api_w / ratio

    def mult16(value):
        return max(16, int(round(value / 16.0) * 16))

    api_w = mult16(api_w)
    api_h = mult16(api_h)

    # Enforce minimum total pixels.
    min_pixels = 655_360
    pixels = api_w * api_h
    if pixels < min_pixels:
        scale = math.sqrt(min_pixels / pixels)
        api_w = mult16(api_w * scale)
        api_h = mult16(api_h * scale)

    # Keep the long edge in a conservative production range.
    max_edge = max(api_w, api_h)
    if max_edge > 2560:
        scale = 2560 / max_edge
        api_w = mult16(api_w * scale)
        api_h = mult16(api_h * scale)

    # Final safety constraints.
    api_w = min(api_w, 3840)
    api_h = min(api_h, 3840)

    return f"{api_w}x{api_h}"


# ============================================================
# FABRIC LIBRARY / WEBSITE SYNC
# ============================================================

def category_from_heading(heading):
    text = re.sub(r"\s+", " ", heading or "").strip().lower()
    if "buffalo" in text:
        return "Buffalo"
    if "poly" in text and "linen" in text:
        return "Poly Linen"
    if "pu leather" in text or text.startswith("pu "):
        return "PU Leather"
    if "velvet" in text:
        return "Velvet"
    if "corduroy" in text:
        return "Corduroy"
    return "Other"


def infer_category_from_name(name):
    lower = name.lower()
    if "buffalo" in lower:
        return "Buffalo"
    if "corduroy" in lower:
        return "Corduroy"
    if "velvet" in lower:
        return "Velvet"
    if re.search(r"\bpu\b", lower):
        return "PU Leather"
    if "fabric" in lower or "linen" in lower:
        return "Poly Linen"
    return "Other"


def best_image_url(img_tag, base_url):
    if img_tag is None:
        return None

    # Prefer a srcset candidate because Shopify commonly provides higher-res URLs there.
    for attr in ("data-srcset", "srcset"):
        srcset = img_tag.get(attr)
        if srcset:
            candidates = []
            for item in srcset.split(","):
                parts = item.strip().split()
                if not parts:
                    continue
                url = parts[0]
                score = 0
                if len(parts) > 1:
                    marker = parts[1].lower()
                    try:
                        if marker.endswith("w"):
                            score = int(marker[:-1])
                        elif marker.endswith("x"):
                            score = int(float(marker[:-1]) * 1000)
                    except ValueError:
                        score = 0
                candidates.append((score, url))
            if candidates:
                _, chosen = max(candidates, key=lambda x: x[0])
                if chosen.startswith("//"):
                    chosen = "https:" + chosen
                return urljoin(base_url, chosen)

    for attr in ("data-src", "src"):
        value = img_tag.get(attr)
        if value:
            if value.startswith("//"):
                value = "https:" + value
            return urljoin(base_url, value)

    return None


def find_image_for_heading(h3):
    # On the Shopify fabric page each swatch image appears immediately before
    # its H3 fabric name. The nearest preceding image is therefore the safest
    # match and avoids accidentally selecting the first image in a larger section.
    img = h3.find_previous("img")
    if img is not None:
        return img

    # Defensive fallback for a future layout where image + title share a card.
    node = h3
    for _ in range(4):
        parent = getattr(node, "parent", None)
        if parent is None:
            break
        img = parent.find("img")
        if img is not None:
            return img
        node = parent

    return None


def sync_fabric_library(page_url):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; ThatCouchPlaceFabricStudio/2.0; "
            "+https://thatcouchplace.co.za)"
        )
    }

    response = requests.get(page_url, headers=headers, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    discovered = []
    seen_names = set()

    for h3 in soup.find_all("h3"):
        name = re.sub(r"\s+", " ", h3.get_text(" ", strip=True)).strip()
        if not name or name.lower() in seen_names:
            continue

        nearest_h2 = h3.find_previous("h2")
        category = category_from_heading(
            nearest_h2.get_text(" ", strip=True) if nearest_h2 else ""
        )

        # The fabric page uses these five categories. Ignore unrelated H3s.
        if category == "Other":
            inferred = infer_category_from_name(name)
            if inferred == "Other":
                continue
            category = inferred

        img = find_image_for_heading(h3)
        image_url = best_image_url(img, page_url)
        if not image_url:
            continue

        seen_names.add(name.lower())
        discovered.append(
            {
                "name": name,
                "category": category,
                "source_url": image_url,
            }
        )

    if not discovered:
        raise RuntimeError(
            "No fabric swatches were detected on the page. "
            "The Shopify page layout may have changed."
        )

    synced_entries = []
    failures = []

    for entry in discovered:
        try:
            img_response = requests.get(
                entry["source_url"],
                headers=headers,
                timeout=30,
            )
            img_response.raise_for_status()

            # Re-encode to PNG so the local file extension always matches its bytes.
            with Image.open(io.BytesIO(img_response.content)) as im:
                im = ImageOps.exif_transpose(im)
                if im.mode not in ("RGB", "RGBA"):
                    im = im.convert("RGBA" if "A" in im.getbands() else "RGB")

                # A large Shopify master image is unnecessary as an AI material
                # reference. Keep plenty of texture detail without storing 3200px
                # copies of every swatch.
                im.thumbnail((1600, 1600), Image.Resampling.LANCZOS)

                filename = f"{slugify(entry['category'])}__{slugify(entry['name'])}.png"
                out_path = SWATCH_DIR / filename
                im.save(out_path, format="PNG", optimize=True)

            synced_entries.append(
                {
                    "name": entry["name"],
                    "category": entry["category"],
                    "filename": filename,
                    "source_url": entry["source_url"],
                    "synced_at": utc_now(),
                }
            )
        except Exception as exc:
            failures.append(f"{entry['name']}: {safe_error_text(exc, 180)}")

    if not synced_entries:
        raise RuntimeError(
            "The page was read, but none of the swatch images could be downloaded."
        )

    synced_entries.sort(
        key=lambda item: (
            CATEGORY_ORDER.index(item["category"])
            if item["category"] in CATEGORY_ORDER
            else 999,
            item["name"].lower(),
        )
    )

    payload = {
        "source_page": page_url,
        "synced_at": utc_now(),
        "fabrics": synced_entries,
    }
    atomic_write_json(LIBRARY_FILE, payload)

    return synced_entries, failures


def load_fabric_library():
    payload = read_json(LIBRARY_FILE, default={}) or {}
    entries = []

    for item in payload.get("fabrics", []):
        path = SWATCH_DIR / item.get("filename", "")
        if path.exists():
            entries.append(item)

    # Keep compatibility with the old app's manually maintained swatches folder.
    known_files = {item.get("filename") for item in entries}
    for path in sorted(SWATCH_DIR.iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
            continue
        if path.name in known_files:
            continue

        display_name = clean_display_name(path.name)
        entries.append(
            {
                "name": display_name,
                "category": infer_category_from_name(display_name),
                "filename": path.name,
                "source_url": None,
                "synced_at": None,
            }
        )

    entries.sort(
        key=lambda item: (
            CATEGORY_ORDER.index(item["category"])
            if item.get("category") in CATEGORY_ORDER
            else 999,
            item["name"].lower(),
        )
    )
    return entries


# ============================================================
# JOB STORAGE
# ============================================================

def get_job_dir(job_id):
    return JOBS_DIR / job_id


def get_manifest_path(job_id):
    return get_job_dir(job_id) / "job.json"


def save_job(job):
    job["updated_at"] = utc_now()
    atomic_write_json(get_manifest_path(job["id"]), job)


def load_job(job_id):
    job = read_json(get_manifest_path(job_id))
    if not job:
        return None

    # A process interrupted by a browser refresh/restart may leave "processing".
    # Recover it safely so the same swatch can be resumed.
    changed = False
    for item in job.get("queue", []):
        if item.get("status") == "processing":
            item["status"] = "pending"
            item["last_error"] = "Recovered after an interrupted run."
            changed = True

    if changed:
        save_job(job)

    return job


def list_jobs():
    jobs = []
    for manifest in JOBS_DIR.glob("*/job.json"):
        job = read_json(manifest)
        if not job:
            continue
        jobs.append(job)

    jobs.sort(key=lambda j: j.get("updated_at", ""), reverse=True)
    return jobs


def create_job(
    product_name,
    uploaded_bytes,
    uploaded_filename,
    source_size,
    selected_fabrics,
    model,
    quality,
    preserve_exact_dimensions,
):
    job_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    folder = get_job_dir(job_id)
    results_dir = folder / "results"
    folder.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    source_path = folder / "source.png"
    source_path.write_bytes(uploaded_bytes)

    api_size = calculate_api_size(*source_size)

    queue = []
    for fabric in selected_fabrics:
        queue.append(
            {
                "id": uuid.uuid4().hex[:10],
                "fabric_name": fabric["name"],
                "category": fabric.get("category", "Other"),
                "swatch_filename": fabric["filename"],
                "status": "pending",
                "attempts": 0,
                "last_error": None,
                "last_request_id": None,
                "result_filename": None,
                "approved": True,
            }
        )

    job = {
        "id": job_id,
        "product_name": product_name.strip(),
        "uploaded_filename": uploaded_filename,
        "source_filename": "source.png",
        "source_width": int(source_size[0]),
        "source_height": int(source_size[1]),
        "api_size": api_size,
        "model": model,
        "quality": quality,
        "preserve_exact_dimensions": bool(preserve_exact_dimensions),
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "queue": queue,
    }
    save_job(job)
    return job


def create_results_zip(job, approved_only=True):
    buf = io.BytesIO()
    job_folder = get_job_dir(job["id"])

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in job.get("queue", []):
            if item.get("status") != "completed":
                continue
            if approved_only and not item.get("approved", False):
                continue
            filename = item.get("result_filename")
            if not filename:
                continue
            path = job_folder / "results" / filename
            if path.exists():
                zf.writestr(filename, path.read_bytes())

    buf.seek(0)
    return buf


# ============================================================
# OPENAI IMAGE EDITING
# ============================================================

def build_prompt(product_name, fabric_name, category):
    texture_notes = {
        "Corduroy": (
            "Transfer the visible corduroy wale/rib texture faithfully. "
            "Keep rib direction physically plausible across each upholstered panel."
        ),
        "Velvet": (
            "Transfer the velvet pile, softness, directional nap, highlights, and sheen "
            "without turning it into a flat solid colour."
        ),
        "Buffalo": (
            "Transfer the buffalo upholstery grain and mottled surface character accurately."
        ),
        "PU Leather": (
            "Transfer the PU leather surface finish, grain, reflectivity, and sheen accurately."
        ),
        "Poly Linen": (
            "Transfer the woven poly-linen texture, thread character, and matte fabric finish."
        ),
    }

    special = texture_notes.get(
        category,
        "Transfer the swatch's real visible weave, grain, pile, sheen, and surface texture.",
    )

    return f"""
REFERENCE IMAGE 1 is the original furniture product photograph.
REFERENCE IMAGE 2 is the exact upholstery fabric swatch to apply.

TASK
Create a photorealistic upholstery replacement of REFERENCE IMAGE 1.
Change ONLY the upholstered fabric/material on the furniture.
Use REFERENCE IMAGE 2 as the authoritative material and colour reference.

PRODUCT
{product_name}

FABRIC
{fabric_name}
Category: {category}

MATERIAL MATCH
- Match the swatch's colour and undertone accurately.
- Match its texture, grain, weave, pile, ribbing, sheen, highlights and surface character.
- Scale the material texture realistically for furniture upholstery.
- Respect seams and panel boundaries.
- {special}

LOCK THE ORIGINAL FURNITURE
Preserve the exact same:
- furniture model and silhouette
- overall width, height and depth
- perspective and camera position
- arm shape and arm thickness
- back shape and height
- seat and back cushions
- cushion count, size, placement and fullness
- bolster/scatter cushions that are part of the product
- buttons, tufting, studs, piping, seams and stitching
- legs, feet and visible hardware
- proportions and spacing

LOCK THE PHOTOGRAPH
Preserve the exact same:
- background and room
- floor and wall
- lighting direction
- shadows
- reflections unrelated to the upholstery
- crop and framing
- surrounding objects

Do not redesign the couch.
Do not modernize it.
Do not add or remove cushions.
Do not change the legs.
Do not change the background.
Do not change the camera angle.
Do not add text, labels, watermarks or logos.

The result must look like the SAME physical furniture item photographed in the SAME photograph,
with only its upholstery replaced by the supplied fabric swatch.
""".strip()


def get_error_code(exc):
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error_obj = body.get("error", body)
        if isinstance(error_obj, dict):
            return error_obj.get("code")
    return None


def is_retryable_api_error(exc):
    if isinstance(exc, (APIConnectionError, APITimeoutError)):
        return True

    if isinstance(exc, RateLimitError):
        code = (get_error_code(exc) or "").lower()
        non_retryable_quota_codes = {
            "insufficient_quota",
            "billing_hard_limit_reached",
            "billing_not_active",
        }
        return code not in non_retryable_quota_codes

    if isinstance(exc, APIStatusError):
        status = getattr(exc, "status_code", None)
        return status in (408, 409, 429) or (isinstance(status, int) and status >= 500)

    return False


def friendly_api_error(exc):
    request_id = getattr(exc, "request_id", None)
    suffix = f" Request ID: {request_id}" if request_id else ""

    if isinstance(exc, AuthenticationError):
        return "OpenAI rejected the API key. Check the key and try again." + suffix
    if isinstance(exc, RateLimitError):
        code = (get_error_code(exc) or "").lower()
        if code in {"insufficient_quota", "billing_hard_limit_reached", "billing_not_active"}:
            return "OpenAI API billing/quota does not currently allow this request." + suffix
        return "OpenAI rate limit reached after the automatic retries." + suffix
    if isinstance(exc, APITimeoutError):
        return (
            f"The image request exceeded the {int(API_TIMEOUT_SECONDS)} second timeout."
            + suffix
        )
    if isinstance(exc, APIConnectionError):
        return "Network/API connection failed after retries." + suffix
    if isinstance(exc, BadRequestError):
        return "OpenAI rejected this image-edit request: " + safe_error_text(exc, 500) + suffix
    if isinstance(exc, APIStatusError):
        return (
            f"OpenAI API error {getattr(exc, 'status_code', 'unknown')}: "
            + safe_error_text(exc, 500)
            + suffix
        )
    return safe_error_text(exc, 600) + suffix


def generate_one_variation(job, item, api_key):
    client = OpenAI(
        api_key=api_key,
        timeout=API_TIMEOUT_SECONDS,
        max_retries=0,
    )

    job_folder = get_job_dir(job["id"])
    source_path = job_folder / job["source_filename"]
    swatch_path = SWATCH_DIR / item["swatch_filename"]

    if not source_path.exists():
        raise FileNotFoundError(f"Source image missing: {source_path.name}")
    if not swatch_path.exists():
        raise FileNotFoundError(f"Swatch missing: {item['swatch_filename']}")

    prompt = build_prompt(
        job["product_name"],
        item["fabric_name"],
        item.get("category", "Other"),
    )

    last_exc = None

    for attempt_number in range(1, MAX_ATTEMPTS_PER_SWATCH + 1):
        item["attempts"] = int(item.get("attempts", 0)) + 1
        save_job(job)

        try:
            with open(source_path, "rb") as source_file, open(swatch_path, "rb") as swatch_file:
                result = client.images.edit(
                    model=job["model"],
                    image=[source_file, swatch_file],
                    prompt=prompt,
                    quality=job["quality"],
                    size=job["api_size"],
                    output_format="png",
                )

            if not result.data or not result.data[0].b64_json:
                raise RuntimeError("OpenAI returned no image data.")

            image_bytes = base64.b64decode(result.data[0].b64_json)

            if job.get("preserve_exact_dimensions", True):
                image_bytes = resize_result_to_exact_source_size(
                    image_bytes,
                    (job["source_width"], job["source_height"]),
                )

            clean_fabric = slugify(item["fabric_name"])
            result_filename = (
                f"{slugify(job['product_name'])}-{clean_fabric}.png"
            )
            output_path = job_folder / "results" / result_filename
            output_path.write_bytes(image_bytes)

            item["result_filename"] = result_filename
            item["status"] = "completed"
            item["last_error"] = None
            item["last_request_id"] = None
            item["approved"] = True
            save_job(job)
            return

        except Exception as exc:
            last_exc = exc
            item["last_request_id"] = getattr(exc, "request_id", None)
            item["last_error"] = friendly_api_error(exc)
            save_job(job)

            if attempt_number >= MAX_ATTEMPTS_PER_SWATCH:
                break

            if not is_retryable_api_error(exc):
                break

            delay_index = min(attempt_number - 1, len(RETRY_DELAYS_SECONDS) - 1)
            time.sleep(RETRY_DELAYS_SECONDS[delay_index])

    item["status"] = "failed"
    item["last_error"] = friendly_api_error(last_exc) if last_exc else "Unknown error."
    save_job(job)


# ============================================================
# SESSION STATE
# ============================================================

if "active_job_id" not in st.session_state:
    st.session_state.active_job_id = None

if "run_active" not in st.session_state:
    st.session_state.run_active = False

if "api_key_input" not in st.session_state:
    st.session_state.api_key_input = ""


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.header("🔑 OpenAI")

    secret_key_present = bool(
        os.getenv("OPENAI_API_KEY", "").strip()
    )
    try:
        secret_key_present = secret_key_present or bool(
            st.secrets.get("OPENAI_API_KEY", "")
        )
    except Exception:
        pass

    if secret_key_present:
        st.success("API key loaded from app configuration.")
    else:
        st.text_input(
            "OpenAI API Key",
            type="password",
            key="api_key_input",
            help="Stored only in this Streamlit browser session.",
        )

    st.markdown("---")
    st.header("🎨 Fabric Library")

    fabric_page_url = st.text_input(
        "Fabric page",
        value=FABRIC_PAGE_DEFAULT,
    )

    if st.button("↻ Sync fabrics from website", use_container_width=True):
        try:
            with st.spinner("Reading fabric names and swatch images…"):
                synced, failures = sync_fabric_library(fabric_page_url)
            st.success(f"Synced {len(synced)} fabrics.")
            if failures:
                with st.expander(f"{len(failures)} swatches could not be downloaded"):
                    for failure in failures:
                        st.write(failure)
            st.rerun()
        except Exception as exc:
            st.error(safe_error_text(exc))

    library_payload = read_json(LIBRARY_FILE, default={}) or {}
    if library_payload.get("synced_at"):
        st.caption(f"Last synced: {library_payload['synced_at'][:19].replace('T', ' ')} UTC")

    st.markdown("---")
    st.header("⚙️ Generation")

    model = st.selectbox(
        "Image model",
        options=[
            "gpt-image-2.5-sunburst",
            "gpt-image-2.5-flare",
        ],
        index=0,
        help=(
            "Sunburst is recommended for precision editing. "
            "Flare is intended for faster everyday generation."
        ),
    )

    quality = st.selectbox(
        "Quality",
        options=["medium", "high", "xhigh", "max"],
        index=1,
        help="Use Medium for testing; High is a good production starting point.",
    )

    preserve_exact_dimensions = st.checkbox(
        "Return exact original pixel dimensions",
        value=True,
    )

    st.markdown("---")
    st.header("🗂️ Recent Jobs")

    recent_jobs = list_jobs()
    if recent_jobs:
        job_labels = {
            job["id"]: (
                f"{job.get('product_name', 'Unnamed')} — "
                f"{job.get('created_at', '')[:16].replace('T', ' ')}"
            )
            for job in recent_jobs[:15]
        }

        chosen_job_id = st.selectbox(
            "Saved batches",
            options=list(job_labels.keys()),
            format_func=lambda value: job_labels[value],
            label_visibility="collapsed",
        )

        if st.button("Load selected batch", use_container_width=True):
            st.session_state.active_job_id = chosen_job_id
            st.session_state.run_active = False
            st.rerun()
    else:
        st.caption("No saved batches yet.")


# ============================================================
# NEW BATCH
# ============================================================

fabric_library = load_fabric_library()

# On a fresh deployment the generated local folders may be empty. Attempt one
# automatic website sync so the app can recover after a cold restart without
# requiring the user to rebuild the library manually.
if not fabric_library:
    try:
        with st.spinner("First run: loading fabric library from That Couch Place…"):
            sync_fabric_library(FABRIC_PAGE_DEFAULT)
        fabric_library = load_fabric_library()
    except Exception as exc:
        st.warning(
            "Automatic fabric sync was not available. You can retry it from the "
            f"sidebar. Details: {safe_error_text(exc, 220)}"
        )

fabric_map = {item["name"]: item for item in fabric_library}

st.subheader("1. Create a new fabric batch")

new_left, new_right = st.columns([1, 1.25])

with new_left:
    product_name = st.text_input(
        "Product name",
        value="",
        placeholder="e.g. Vegas Corner Couch",
    )

    uploaded_image = st.file_uploader(
        "Upload the original couch/furniture photo",
        type=["png", "jpg", "jpeg", "webp"],
    )

    if uploaded_image:
        uploaded_raw = uploaded_image.getvalue()
        normalized_upload, source_size = image_bytes_to_png(uploaded_raw)
        st.image(normalized_upload, caption=f"Original — {source_size[0]} × {source_size[1]} px")
        st.caption(f"API edit size will preserve this aspect ratio: {calculate_api_size(*source_size)}")
    else:
        normalized_upload = None
        source_size = None

with new_right:
    if not fabric_library:
        st.warning(
            "No fabric swatches are available yet. Use **Sync fabrics from website** "
            "in the sidebar, or keep image files in the existing `swatches/` folder."
        )
        selected_fabric_names = []
    else:
        categories_available = [
            category
            for category in CATEGORY_ORDER
            if any(item["category"] == category for item in fabric_library)
        ]

        selected_categories = st.multiselect(
            "Filter fabric categories",
            options=categories_available,
            default=categories_available,
        )

        visible_names = [
            item["name"]
            for item in fabric_library
            if item["category"] in selected_categories
        ]

        selected_fabric_names = st.multiselect(
            "Choose fabric names",
            options=visible_names,
            placeholder="Select one or many fabrics",
        )

        if selected_fabric_names:
            st.caption(f"{len(selected_fabric_names)} fabric(s) selected")

            preview_cols = st.columns(4)
            for idx, name in enumerate(selected_fabric_names):
                item = fabric_map[name]
                swatch_path = SWATCH_DIR / item["filename"]
                with preview_cols[idx % 4]:
                    if swatch_path.exists():
                        st.image(str(swatch_path), use_container_width=True)
                    st.caption(f"{item['category']} · {name}")

    can_start = bool(
        product_name.strip()
        and normalized_upload
        and selected_fabric_names
    )

    if st.button(
        f"▶ Start batch ({len(selected_fabric_names)} fabrics)",
        type="primary",
        disabled=not can_start,
        use_container_width=True,
    ):
        selected_fabrics = [fabric_map[name] for name in selected_fabric_names]

        new_job = create_job(
            product_name=product_name,
            uploaded_bytes=normalized_upload,
            uploaded_filename=uploaded_image.name,
            source_size=source_size,
            selected_fabrics=selected_fabrics,
            model=model,
            quality=quality,
            preserve_exact_dimensions=preserve_exact_dimensions,
        )

        st.session_state.active_job_id = new_job["id"]
        st.session_state.run_active = True
        st.rerun()


# ============================================================
# ACTIVE JOB / QUEUE UI
# ============================================================

active_job = None
if st.session_state.active_job_id:
    active_job = load_job(st.session_state.active_job_id)

if active_job:
    st.markdown("---")
    st.subheader(f"2. Generation Queue — {active_job['product_name']}")

    queue = active_job.get("queue", [])
    total = len(queue)
    completed = sum(1 for item in queue if item["status"] == "completed")
    failed = sum(1 for item in queue if item["status"] == "failed")
    pending = sum(1 for item in queue if item["status"] == "pending")
    processing = sum(1 for item in queue if item["status"] == "processing")
    processed = completed + failed

    metric_cols = st.columns(5)
    metric_cols[0].metric("Total", total)
    metric_cols[1].metric("Completed", completed)
    metric_cols[2].metric("Pending", pending)
    metric_cols[3].metric("Failed", failed)
    metric_cols[4].metric("Attempts", sum(int(i.get("attempts", 0)) for i in queue))

    st.progress(processed / total if total else 0.0)
    st.caption(
        f"Model: {active_job['model']} · Quality: {active_job['quality']} · "
        f"Edit size: {active_job['api_size']} · "
        f"Final size: {active_job['source_width']}×{active_job['source_height']} px"
    )

    control_cols = st.columns([1, 1, 1, 2])

    with control_cols[0]:
        if st.session_state.run_active:
            if st.button("⏹ Stop after current", use_container_width=True):
                st.session_state.run_active = False
                st.rerun()
        else:
            unfinished = any(item["status"] == "pending" for item in queue)
            if st.button(
                "▶ Resume queue",
                disabled=not unfinished,
                use_container_width=True,
            ):
                st.session_state.run_active = True
                st.rerun()

    with control_cols[1]:
        if st.button(
            "↻ Retry failed",
            disabled=failed == 0,
            use_container_width=True,
        ):
            for item in active_job["queue"]:
                if item["status"] == "failed":
                    item["status"] = "pending"
                    item["last_error"] = None
            save_job(active_job)
            st.session_state.run_active = True
            st.rerun()

    with control_cols[2]:
        if st.button("⏸ Pause queue", use_container_width=True):
            st.session_state.run_active = False
            st.rerun()

    with control_cols[3]:
        if st.session_state.run_active:
            st.info(
                "Queue is running one image at a time. "
                "You can stop after the current request."
            )
        elif pending:
            st.warning("Queue is paused.")
        elif failed:
            st.warning("Batch finished with one or more failed fabrics.")
        else:
            st.success("Batch complete.")

    st.markdown("#### Queue status")

    status_icon = {
        "pending": "⏳",
        "processing": "🔄",
        "completed": "✅",
        "failed": "❌",
    }

    for item in active_job["queue"]:
        row = st.columns([0.5, 3.0, 1.2, 1.2, 2.5])
        row[0].write(status_icon.get(item["status"], "•"))
        row[1].write(f"**{item['fabric_name']}**")
        row[2].write(item.get("category", ""))
        row[3].write(f"{item.get('attempts', 0)} attempt(s)")
        if item["status"] == "failed":
            row[4].error(item.get("last_error") or "Generation failed.")
        elif item["status"] == "processing":
            row[4].info("Generating now…")
        elif item["status"] == "completed":
            row[4].success("Saved")
        else:
            row[4].caption("Waiting")

    # ========================================================
    # RESULTS
    # ========================================================

    completed_items = [
        item for item in active_job["queue"]
        if item["status"] == "completed" and item.get("result_filename")
    ]

    if completed_items:
        st.markdown("---")
        st.subheader("3. Review Results")

        result_cols = st.columns(3)

        for idx, item in enumerate(completed_items):
            result_path = (
                get_job_dir(active_job["id"])
                / "results"
                / item["result_filename"]
            )
            if not result_path.exists():
                continue

            with result_cols[idx % 3]:
                st.image(str(result_path), use_container_width=True)
                st.markdown(f"**{item['fabric_name']}**")
                st.caption(item.get("category", ""))

                approved_key = f"approved__{active_job['id']}__{item['id']}"
                if approved_key not in st.session_state:
                    st.session_state[approved_key] = bool(item.get("approved", True))

                approved_value = st.checkbox(
                    "Approved for ZIP",
                    key=approved_key,
                )

                if approved_value != item.get("approved", True):
                    item["approved"] = approved_value
                    save_job(active_job)

                st.download_button(
                    "⬇ Download image",
                    data=result_path.read_bytes(),
                    file_name=item["result_filename"],
                    mime="image/png",
                    key=f"download__{active_job['id']}__{item['id']}",
                    use_container_width=True,
                )

                if st.button(
                    "↻ Regenerate",
                    key=f"regen__{active_job['id']}__{item['id']}",
                    use_container_width=True,
                ):
                    item["status"] = "pending"
                    item["last_error"] = None
                    item["approved"] = True
                    save_job(active_job)
                    st.session_state.run_active = True
                    st.rerun()

        approved_count = sum(
            1
            for item in active_job["queue"]
            if item["status"] == "completed" and item.get("approved", False)
        )

        if approved_count:
            zip_data = create_results_zip(active_job, approved_only=True)
            st.download_button(
                f"📦 Download approved ZIP ({approved_count} images)",
                data=zip_data,
                file_name=f"{slugify(active_job['product_name'])}-fabric-variants.zip",
                mime="application/zip",
                use_container_width=True,
            )

    # ========================================================
    # PROCESS EXACTLY ONE QUEUE ITEM PER SCRIPT RUN
    # ========================================================

    # This is the key reliability change from V1.
    #
    # V1 tried to finish the entire batch inside one long blocking loop.
    # V2 processes one swatch, writes its result + job state to disk, then
    # reruns Streamlit. A later failure therefore cannot erase earlier results.
    if st.session_state.run_active:
        api_key = get_configured_api_key()

        if not api_key:
            st.session_state.run_active = False
            st.error(
                "Add an OpenAI API key in the sidebar before resuming the queue."
            )
        else:
            # Reload immediately before modifying the manifest.
            current_job = load_job(active_job["id"])
            next_item = next(
                (
                    item
                    for item in current_job["queue"]
                    if item["status"] == "pending"
                ),
                None,
            )

            if next_item is None:
                st.session_state.run_active = False
                st.rerun()

            next_item["status"] = "processing"
            next_item["last_error"] = None
            save_job(current_job)

            with st.spinner(
                f"Generating {next_item['fabric_name']} — "
                f"this queue runs one image at a time…"
            ):
                try:
                    generate_one_variation(
                        current_job,
                        next_item,
                        api_key,
                    )
                except Exception as exc:
                    next_item["status"] = "failed"
                    next_item["last_error"] = safe_error_text(exc)
                    save_job(current_job)

            time.sleep(PAUSE_BETWEEN_SWATCHES_SECONDS)
            st.rerun()

else:
    st.info(
        "Create a new batch above, or load a saved batch from **Recent Jobs** "
        "in the sidebar."
    )

import base64
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import streamlit as st
from openai import OpenAI
from PIL import Image

st.set_page_config(
    page_title="That Couch Place Lifestyle Generator",
    page_icon="🛋️",
    layout="wide",
)

# ============================================================
# APP DATA
# ============================================================

STYLE_LIBRARY = {
    "Bright Scandinavian": "Airy Scandinavian-inspired styling with light woods, pale neutrals, clean lines and restrained decor.",
    "Warm Contemporary": "Comfortable contemporary styling with warm neutrals, tactile materials and welcoming modern decor.",
    "Industrial Loft": "Urban industrial character with a balanced mix of raw and refined materials, large-scale architecture and modern decor.",
    "Luxury Lodge": "Upscale lodge character with natural materials, generous proportions and a calm premium atmosphere.",
    "Coastal Holiday": "Relaxed coastal holiday-home feeling with breezy finishes, soft natural textures and an easy indoor-outdoor mood.",
    "Student / Compact Living": "Smart compact living with practical youthful styling, efficient use of space and bright modern finishes.",
    "Hunting Lodge": "Rugged refined lodge character with timber, stone, leather-like textures and subtle hunting-country references.",
    "Urban Penthouse": "Sophisticated high-end city apartment styling with contemporary finishes, generous glazing and polished decor.",
    "Countryside Cottage": "Charming country-home character with natural textures, traditional touches and a comfortable lived-in feeling.",
    "Japandi": "Calm Japandi direction combining Scandinavian simplicity with Japanese-inspired restraint and natural materials.",
    "Mid-Century Modern": "Mid-century modern influence with clean geometry, warm wood, curated decor and a sophisticated residential feel.",
    "Modern Farmhouse": "Modern farmhouse direction with natural timber, soft neutrals and simple architectural details.",
    "Mediterranean": "Relaxed Mediterranean-inspired styling using warm plaster, stone, timber and sunny natural textures.",
    "Art Deco": "Elegant Art Deco influence with confident geometry, refined materials and controlled glamour.",
    "Boutique Hotel": "Curated boutique-hotel styling with layered textures, premium finishes and thoughtful decorative details.",
    "Contemporary African": "Contemporary African-inspired styling using warm natural materials, crafted textures and earthy sophistication.",
    "Minimal Luxury": "High-end minimalist styling with excellent materials, generous negative space and understated decor.",
    "Tropical Resort": "Relaxed upscale tropical-resort character with natural materials, greenery and an indoor-outdoor feeling.",
    "Rustic Modern": "A balanced mix of rustic natural materials and clean modern detailing.",
    "Classic Elegant": "Timeless elegant styling with refined proportions, subtle traditional details and polished contemporary comfort.",
    "Boho Eclectic": "Layered but tasteful bohemian styling with natural textures, collected decor and relaxed personality.",
    "French Country": "Soft French-country influence with graceful shapes, warm natural materials and a comfortable residential feel.",
    "Dark Modern": "Moody modern decor with deeper finishes and dramatic materials while keeping the furniture clearly visible.",
    "Playful Modern": "Fresh modern styling with tasteful colour, playful forms and creative accessories.",
}

ROOM_TYPES = [
    "Lounge / Living Room",
    "Family Room",
    "TV Room",
    "Entertainment Room",
    "Dining Room",
    "Kitchen",
    "Bar",
    "Restaurant",
    "Hotel Room",
    "Hotel Foyer / Lobby",
    "Kids Bedroom",
    "Main Bedroom",
    "Salon",
    "Office / Reception",
    "Wedding Venue",
    "Outdoor Area appropriate to the selected style",
    "Custom",
]

SIZE_OPTIONS = {
    "Square — Google Shopping friendly": "1024x1024",
    "Landscape": "1536x1024",
    "Portrait": "1024x1536",
}

QUALITY_OPTIONS = {
    "Medium — draft": "medium",
    "High — recommended": "high",
}

MODEL_OPTIONS = {
    "GPT Image 2 — recommended": "gpt-image-2",
    "GPT Image 1 — fallback": "gpt-image-1",
}

JOBS_DIR = Path("lifestyle_jobs")
JOBS_DIR.mkdir(exist_ok=True)


# ============================================================
# BACKGROUND QUEUE
# ============================================================

class JobRuntime:
    def __init__(self):
        # Deliberately one worker: jobs queue safely instead of hitting the API in parallel.
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="lifestyle")
        self.jobs = {}
        self.lock = threading.RLock()

    def set_job(self, job_id, **values):
        with self.lock:
            self.jobs.setdefault(job_id, {}).update(values)

    def get_jobs(self, session_id):
        with self.lock:
            rows = [dict(v) for v in self.jobs.values() if v.get("session_id") == session_id]
        return sorted(rows, key=lambda x: x.get("created", ""), reverse=True)


@st.cache_resource
def get_runtime():
    return JobRuntime()


runtime = get_runtime()

if "lifestyle_session_id" not in st.session_state:
    st.session_state.lifestyle_session_id = uuid.uuid4().hex

SESSION_ID = st.session_state.lifestyle_session_id


def get_api_key():
    try:
        secret_key = st.secrets.get("OPENAI_API_KEY")
        if secret_key:
            return secret_key
    except Exception:
        pass
    return os.getenv("OPENAI_API_KEY")


def build_prompt(style_name, style_text, room_type, labels, extra):
    refs = "\n".join(
        f"- Reference image {i + 1}: {label or f'Furniture piece {i + 1}'}"
        for i, label in enumerate(labels)
    )

    outdoor = ""
    if room_type.startswith("Outdoor Area"):
        outdoor = (
            "For this outdoor option, interpret the selected style as a believable matching "
            "patio, veranda, deck, courtyard, terrace, poolside or garden area. Choose what "
            "fits naturally rather than forcing a specific outdoor setting."
        )

    extra_block = f"\nADDITIONAL USER DIRECTION:\n{extra.strip()}" if extra.strip() else ""

    return f"""
Create a photorealistic commercial lifestyle photograph using the uploaded furniture reference images.

FURNITURE REFERENCES
{refs}

PRIORITY 1 — PRESERVE THE UPLOADED FURNITURE
The uploaded furniture images are identity references for the real products.
Reproduce every uploaded furniture piece faithfully.
Do not redesign, recolour, restyle or substitute any uploaded furniture.
Keep the original silhouette, proportions, upholstery colour, fabric appearance, seams, piping,
buttons, tufting, cushions, arms, headboards, bases, legs, feet, frames and other identifying details.
If several furniture pieces are supplied, include all of them as separate real objects in one believable
scene. Do not merge their designs or borrow features from one product for another.
Only make the normal photographic adjustments needed to place them naturally into the room:
perspective, scale, floor contact, realistic shadows and sensible overlap.
Do not copy the original product-photo background.

PRIORITY 2 — CREATE THE ROOM FREELY
Room type: {room_type}
Style: {style_name}
Style direction: {style_text}

Treat the style direction as inspiration, NOT a rigid checklist.
You have creative freedom to invent the architecture, walls, floors, rugs, curtains, plants, art,
lamps, tables, accessories and supporting decor. The room should look professionally styled and
believable, and it may vary substantially from one generation to another.
Supporting decor must complement the uploaded furniture, never cover it or visually overpower it.
{outdoor}

COMMERCIAL VISIBILITY
The result must work even as a small Google Shopping-style thumbnail.
Make the uploaded furniture the clear visual subject and large enough to recognise immediately.
Use clean, bright, balanced photographic lighting. The room may still have mood and character,
but do not underexpose the furniture, crush shadow detail, create strong colour casts on the product,
or use dramatic darkness that hides fabric texture and construction detail.
Keep important furniture surfaces well illuminated with believable natural light, soft fill light, or both.
Maintain clear visual separation between furniture and background.

FINAL IMAGE
Professional photorealistic interior photography.
Natural scale and perspective.
Believable contact shadows.
Sharp furniture detail.
No people unless explicitly requested.
No text, logos, labels or watermarks.
No duplicate copies of an uploaded product unless explicitly requested.
{extra_block}
""".strip()


def save_inputs(job_id, uploaded_files):
    job_dir = JOBS_DIR / job_id
    input_dir = job_dir / "inputs"
    output_dir = job_dir / "outputs"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = []
    for index, uploaded in enumerate(uploaded_files, start=1):
        suffix = Path(uploaded.name).suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
            suffix = ".png"
        path = input_dir / f"furniture_{index}{suffix}"
        path.write_bytes(uploaded.getvalue())
        paths.append(str(path))
    return paths, output_dir


def run_generation(job_id, api_key, input_paths, output_dir, prompt, model, quality, size):
    runtime.set_job(job_id, status="Generating")
    handles = []
    try:
        client = OpenAI(api_key=api_key)
        handles = [open(path, "rb") for path in input_paths]

        response = client.images.edit(
            model=model,
            image=handles,
            prompt=prompt,
            size=size,
            quality=quality,
            output_format="jpeg",
        )

        image_b64 = response.data[0].b64_json
        if not image_b64:
            raise RuntimeError("The image API returned no image data.")

        image_bytes = base64.b64decode(image_b64)
        output_path = Path(output_dir) / f"lifestyle_{job_id[:8]}.jpg"
        output_path.write_bytes(image_bytes)
        runtime.set_job(job_id, status="Complete", output_path=str(output_path))

    except Exception as exc:
        runtime.set_job(job_id, status="Failed", error=str(exc))
    finally:
        for handle in handles:
            try:
                handle.close()
            except Exception:
                pass


def submit_job(api_key, uploaded_files, prompt, style_name, room_type, model, quality, size):
    job_id = uuid.uuid4().hex
    input_paths, output_dir = save_inputs(job_id, uploaded_files)

    runtime.set_job(
        job_id,
        id=job_id,
        session_id=SESSION_ID,
        created=job_id,
        status="Queued",
        style=style_name,
        room=room_type,
        model=model,
        quality=quality,
        size=size,
        prompt=prompt,
        output_path=None,
        error=None,
    )

    runtime.executor.submit(
        run_generation,
        job_id,
        api_key,
        input_paths,
        output_dir,
        prompt,
        model,
        quality,
        size,
    )
    return job_id


# ============================================================
# UI
# ============================================================

st.title("🛋️ That Couch Place Lifestyle Generator")
st.caption(
    "Upload 1–3 furniture pieces. The furniture stays strict; the room decor stays creative. "
    "Jobs generate one at a time in the background while you prepare the next scene."
)

stored_api_key = get_api_key()
manual_api_key = st.sidebar.text_input(
    "OpenAI API Key",
    type="password",
    help="Leave blank when OPENAI_API_KEY is already saved in Streamlit secrets.",
)
api_key = manual_api_key.strip() or stored_api_key

st.sidebar.subheader("Generation settings")
model_label = st.sidebar.selectbox("Image model", list(MODEL_OPTIONS.keys()))
model = MODEL_OPTIONS[model_label]
quality_label = st.sidebar.selectbox("Quality", list(QUALITY_OPTIONS.keys()), index=1)
quality = QUALITY_OPTIONS[quality_label]
size_label = st.sidebar.selectbox("Image shape", list(SIZE_OPTIONS.keys()))
size = SIZE_OPTIONS[size_label]
st.sidebar.info("Safe queue: only one API image request runs at a time.")

st.subheader("1. Upload furniture")
uploaded_files = st.file_uploader(
    "Upload 1 to 3 furniture images",
    type=["jpg", "jpeg", "png", "webp"],
    accept_multiple_files=True,
)

if len(uploaded_files) > 3:
    st.error("Please upload a maximum of 3 furniture images.")

labels = []
if 1 <= len(uploaded_files) <= 3:
    columns = st.columns(len(uploaded_files))
    for index, (uploaded, column) in enumerate(zip(uploaded_files, columns)):
        with column:
            try:
                st.image(Image.open(uploaded), use_container_width=True)
            except Exception:
                st.warning("Preview unavailable")
            default_name = Path(uploaded.name).stem.replace("_", " ").replace("-", " ")
            labels.append(
                st.text_input(
                    f"Furniture {index + 1} name / role",
                    value=default_name,
                    key=f"label_{index}",
                )
            )

st.subheader("2. Choose the room")
room = st.selectbox("Room type", ROOM_TYPES)
if room == "Custom":
    room = st.text_input("Describe the room", placeholder="Example: rooftop cocktail lounge")

st.subheader("3. Choose the room style")
style_name = st.selectbox("Style", list(STYLE_LIBRARY.keys()) + ["Custom"])
if style_name == "Custom":
    style_text = st.text_area(
        "Describe the style direction",
        placeholder="Give a loose design direction. The AI will create the actual decor.",
    )
else:
    style_text = STYLE_LIBRARY[style_name]
    st.caption(style_text)

st.subheader("4. Optional extra direction")
extra = st.text_area(
    "Extra instructions for this image",
    placeholder=(
        "Examples: Put the chair beside the couch. Use a garden view. "
        "Make the room feel more premium. Do not include a coffee table."
    ),
    height=110,
)

valid_uploads = 1 <= len(uploaded_files) <= 3
valid_setup = bool(room.strip()) and bool(style_text.strip())

prompt = ""
if valid_uploads and valid_setup:
    prompt = build_prompt(style_name, style_text, room, labels, extra)
    with st.expander("Preview generation prompt"):
        st.text_area("Prompt", prompt, height=420, disabled=True, label_visibility="collapsed")

if st.button(
    "➕ Add image to background queue",
    type="primary",
    use_container_width=True,
    disabled=not (api_key and valid_uploads and valid_setup),
):
    submit_job(api_key, uploaded_files, prompt, style_name, room, model, quality, size)
    st.success(
        "Added to the queue. You can immediately change the furniture, room, style or instructions "
        "and prepare the next image while this one generates."
    )

if not api_key:
    st.info("Enter your OpenAI API key in the sidebar, or save OPENAI_API_KEY in Streamlit secrets.")


def render_queue():
    jobs = runtime.get_jobs(SESSION_ID)
    st.markdown("---")
    st.subheader("Generation queue")

    if not jobs:
        st.caption("No images queued in this session yet.")
        return

    queued = sum(job["status"] == "Queued" for job in jobs)
    generating = sum(job["status"] == "Generating" for job in jobs)
    complete = sum(job["status"] == "Complete" for job in jobs)
    failed = sum(job["status"] == "Failed" for job in jobs)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Queued", queued)
    c2.metric("Generating", generating)
    c3.metric("Complete", complete)
    c4.metric("Failed", failed)

    for job in jobs:
        with st.expander(f"{job['status']} — {job['style']} / {job['room']}", expanded=job["status"] in {"Generating", "Failed"}):
            st.caption(f"Model: {job['model']} | Quality: {job['quality']} | Size: {job['size']}")

            if job["status"] == "Generating":
                st.info("Generating in the background. You can keep preparing the next scene above.")
            elif job["status"] == "Failed":
                st.error(job.get("error") or "Generation failed.")
            elif job["status"] == "Complete":
                output_path = job.get("output_path")
                if output_path and Path(output_path).exists():
                    image_bytes = Path(output_path).read_bytes()
                    st.image(image_bytes, use_container_width=True)
                    st.download_button(
                        "Download image",
                        image_bytes,
                        file_name=Path(output_path).name,
                        mime="image/jpeg",
                        key=f"download_{job['id']}",
                    )

            with st.expander("Prompt used"):
                st.text(job["prompt"])


if hasattr(st, "fragment"):
    @st.fragment(run_every="3s")
    def queue_fragment():
        render_queue()

    queue_fragment()
else:
    render_queue()
    st.caption("Refresh the page to update generation status on this Streamlit version.")

st.markdown("---")
st.caption(
    "Furniture preservation is strict. Room styling is intentionally flexible. "
    "The queue runs one image request at a time to avoid the previous overload/stalling problem."
)

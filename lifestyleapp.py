import base64
import io
import os
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests
import streamlit as st
from openai import OpenAI
from PIL import Image


st.set_page_config(
    page_title="That Couch Place Lifestyle Studio",
    page_icon="🛋️",
    layout="wide",
)


ROOMS = {
    "Lounge": "a welcoming residential lounge designed around the uploaded furniture",
    "Family Room": "a comfortable, practical family room with tasteful everyday decor",
    "TV Room": "a comfortable TV room with a discreet entertainment wall and relaxed styling",
    "Entertainment Room": "a polished entertainment room suitable for hosting friends and family",
    "Dining Room": "a well-proportioned dining room with an elegant but believable residential finish",
    "Kitchen": "a bright contemporary kitchen with an appropriate dining or seating area",
    "Bar": "a stylish upmarket bar interior with attractive ambient details",
    "Restaurant": "a professionally designed restaurant interior with realistic table spacing",
    "Hotel Room": "a refined hotel room or suite with uncluttered commercial styling",
    "Kids Bedroom": "a cheerful, age-appropriate children's bedroom with safe practical decor",
    "Bedroom": "a calm, inviting bedroom with balanced decor and comfortable proportions",
    "Salon": "a polished modern beauty salon with a clean, welcoming atmosphere",
    "Wedding Venue": "an elegant wedding venue with refined decor that does not obscure the furniture",
    "Outdoor Area": "a realistic covered South African patio, veranda, garden or poolside setting",
}


STYLES = {
    "Auto-match the furniture": "Choose the room styling that best complements the uploaded furniture.",
    "Bright Scandinavian": "Light oak, warm whites, restrained natural textures and an airy Scandinavian mood.",
    "Cozy Contemporary": "Warm neutral tones, soft layered textures and relaxed contemporary decor.",
    "Modern Minimalist": "Clean architectural lines, calm neutral colours and carefully selected minimal decor.",
    "Industrial Loft": "Exposed brick or concrete, large windows, dark metal accents and softened industrial details.",
    "Luxury Lodge": "High ceilings, natural timber and stone, open views and refined lodge styling.",
    "Coastal Holiday Home": "Whitewashed or light floors, breezy textures, open doors and subtle coastal character.",
    "Modern South African": "Warm contemporary South African home styling with natural materials and generous light.",
    "Urban Apartment": "A realistic, well-designed compact apartment with space-conscious decor.",
    "Student Living": "Bright, practical and affordable student accommodation with uncluttered styling.",
    "Boutique Hotel": "Layered, sophisticated boutique-hotel decor with premium but believable finishes.",
    "Classic Elegant": "Timeless proportions, elegant detailing and a sophisticated neutral palette.",
    "Rustic Farmhouse": "Warm timber, tactile natural materials and relaxed contemporary farmhouse styling.",
}


CAMERAS = {
    "Google Shopping / product focus": "Medium-wide ecommerce composition; furniture large, unobstructed and instantly readable at thumbnail size.",
    "45-degree room view": "Natural 45-degree interior-photography angle showing the furniture and enough room context.",
    "Straight-on elevation": "Mostly straight-on view with corrected verticals and a balanced symmetrical composition.",
    "Wide interior": "Wide interior view while keeping the uploaded furniture prominent and clearly identifiable.",
    "Editorial magazine": "Premium interior editorial composition with realistic professional photography.",
}


def slugify(value):
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value or "lifestyle-image")
    return value.strip("-").lower() or "lifestyle-image"


def get_secret(name, default=""):
    value = os.getenv(name, default)
    if value:
        return value
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


def uploaded_bytes(upload):
    upload.seek(0)
    data = upload.read()
    upload.seek(0)
    return data


def build_prompt(product_name, room, style, camera, extra_instruction, image_count):
    references = "The first uploaded image is the hero product."
    if image_count > 1:
        references += (
            f" The remaining {image_count - 1} uploaded image(s) are supporting furniture pieces "
            "that must also be included accurately in the same scene."
        )

    return f"""
Create one photorealistic furniture lifestyle image for That Couch Place.

PRODUCT: {product_name or 'Use the uploaded furniture as the product reference.'}
ROOM: {room} — {ROOMS[room]}
STYLE: {style} — {STYLES[style]}
CAMERA: {CAMERAS[camera]}

REFERENCE IMAGE RULES:
- {references}
- Preserve the exact identity and construction of every uploaded furniture piece.
- Preserve shape, proportions, dimensions, upholstery colour and texture, seams, cushions, buttons, studs, arms, legs, headboard panels, table bases and all other distinguishing details.
- Do not redesign, simplify, duplicate, merge or substitute any uploaded product.
- You have creative freedom over the room architecture, decor and secondary accessories only.
- Arrange the supplied pieces naturally together, with believable scale and perspective.
- Do not place decor in front of, on top of, or across the main selling features of the furniture.

COMMERCIAL LIGHTING:
- Use clean, bright, natural-looking professional interior lighting.
- The furniture must remain clearly visible in a small Google Shopping thumbnail.
- Retain realistic shadows, material texture and depth; avoid gloomy exposure, colour casts, blown highlights and dramatic darkness.
- Produce a polished ecommerce photograph with no text, logos, borders, watermarks or people.

ADDITIONAL DIRECTION:
{extra_instruction.strip() if extra_instruction.strip() else 'Use tasteful decor appropriate to the selected room and style.'}
""".strip()


@st.cache_resource
def job_executor():
    # Two workers allow one new request to be queued while another image is generating.
    return ThreadPoolExecutor(max_workers=2, thread_name_prefix="lifestyle")


def generate_image(api_key, prompt, reference_images, size, quality):
    client = OpenAI(api_key=api_key)
    files = []
    for index, item in enumerate(reference_images, start=1):
        buffer = io.BytesIO(item["data"])
        buffer.name = item.get("name") or f"product-{index}.png"
        files.append(buffer)

    response = client.images.edit(
        model="gpt-image-1",
        image=files,
        prompt=prompt,
        input_fidelity="high",
        size=size,
        quality=quality,
        n=1,
    )

    result = response.data[0]
    if getattr(result, "b64_json", None):
        return base64.b64decode(result.b64_json)
    if getattr(result, "url", None):
        download = requests.get(result.url, timeout=90)
        download.raise_for_status()
        return download.content
    raise RuntimeError("OpenAI returned no image data.")


if "lifestyle_jobs" not in st.session_state:
    st.session_state.lifestyle_jobs = []


st.title("🛋️ That Couch Place Lifestyle Studio")
st.caption("Combine up to three furniture pieces in a bright, sales-ready lifestyle scene.")

with st.sidebar:
    st.header("API configuration")
    stored_api_key = get_secret("OPENAI_API_KEY")
    manual_api_key = st.text_input(
        "OpenAI API key",
        type="password",
        placeholder="Stored securely in Streamlit Secrets" if stored_api_key else "Enter your API key",
        help="Add OPENAI_API_KEY to Streamlit Secrets to avoid entering it each time.",
    )
    api_key = manual_api_key or stored_api_key
    st.divider()
    st.write("Generation runs in the background. You can prepare and submit another scene while an earlier job continues.")


left, right = st.columns([1.05, 1], gap="large")

with left:
    st.subheader("1. Furniture")
    product_name = st.text_input("Product or collection name", placeholder="Example: Oasis Serenity Dining Set")
    hero = st.file_uploader("Main furniture image (required)", type=["jpg", "jpeg", "png", "webp"], key="hero")
    supporting_1 = st.file_uploader("Second furniture piece (optional)", type=["jpg", "jpeg", "png", "webp"], key="support1")
    supporting_2 = st.file_uploader("Third furniture piece (optional)", type=["jpg", "jpeg", "png", "webp"], key="support2")

    previews = [item for item in (hero, supporting_1, supporting_2) if item]
    if previews:
        preview_columns = st.columns(len(previews))
        for column, upload in zip(preview_columns, previews):
            with column:
                st.image(Image.open(upload), caption=upload.name, use_container_width=True)

with right:
    st.subheader("2. Scene")
    room = st.selectbox("Room", list(ROOMS))
    style = st.selectbox("Room style", list(STYLES))
    camera = st.selectbox("Composition", list(CAMERAS))
    extra_instruction = st.text_area(
        "Extra instructions (optional)",
        placeholder="Example: Keep the windows on the left and use a light neutral rug.",
        height=100,
    )

    output_size_label = st.selectbox(
        "Image shape",
        ["Landscape (1536 × 1024)", "Square (1024 × 1024)", "Portrait (1024 × 1536)"],
    )
    size = {
        "Landscape (1536 × 1024)": "1536x1024",
        "Square (1024 × 1024)": "1024x1024",
        "Portrait (1024 × 1536)": "1024x1536",
    }[output_size_label]
    quality = st.selectbox("Quality", ["medium", "high"], index=0)

    if st.button("Generate lifestyle image", type="primary", use_container_width=True):
        if not api_key:
            st.error("Enter an OpenAI API key or add OPENAI_API_KEY to this app's Streamlit Secrets.")
        elif not hero:
            st.error("Upload the main furniture image first.")
        else:
            uploads = [item for item in (hero, supporting_1, supporting_2) if item]
            references = [{"name": item.name, "data": uploaded_bytes(item)} for item in uploads]
            prompt = build_prompt(product_name, room, style, camera, extra_instruction, len(references))
            job_id = uuid.uuid4().hex[:8]
            future = job_executor().submit(generate_image, api_key, prompt, references, size, quality)
            st.session_state.lifestyle_jobs.insert(
                0,
                {
                    "id": job_id,
                    "name": product_name or "Lifestyle image",
                    "created": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                    "prompt": prompt,
                    "future": future,
                    "status": "running",
                },
            )
            st.success(f"Generation {job_id} started. You can now prepare another scene.")


st.divider()
st.subheader("Generation queue")


@st.fragment(run_every=4)
def show_jobs():
    jobs = st.session_state.lifestyle_jobs
    if not jobs:
        st.info("No generations submitted in this session yet.")
        return

    for job in jobs:
        future = job.get("future")
        if job["status"] == "running" and future.done():
            try:
                job["image"] = future.result()
                job["status"] = "complete"
            except Exception as error:
                job["error"] = str(error)
                job["status"] = "failed"

        with st.container(border=True):
            title_col, status_col = st.columns([3, 1])
            title_col.markdown(f"**{job['name']}**  \n{job['created']} · Job `{job['id']}`")
            if job["status"] == "running":
                status_col.info("Generating…")
            elif job["status"] == "complete":
                status_col.success("Complete")
                st.image(job["image"], use_container_width=True)
                st.download_button(
                    "Download image",
                    job["image"],
                    file_name=f"{slugify(job['name'])}-{job['id']}.png",
                    mime="image/png",
                    key=f"download-{job['id']}",
                )
            else:
                status_col.error("Failed")
                st.error(job.get("error", "The image request failed."))

            with st.expander("View the exact generation prompt"):
                st.code(job["prompt"], language=None)


show_jobs()

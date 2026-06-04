import streamlit as st
from openai import OpenAI
from PIL import Image
import io
import os
import zipfile
import base64
import re

# =====================================================
# CONFIG
# =====================================================

st.set_page_config(
    page_title="Furniture Fabric AI Studio",
    layout="wide"
)

st.title("🛋️ Furniture Fabric AI Studio")
st.write(
    "Upload a couch image and generate realistic fabric variations "
    "using your swatch library."
)

# =====================================================
# HELPERS
# =====================================================

def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")

def create_zip(assets):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(
        zip_buffer,
        "w",
        zipfile.ZIP_DEFLATED
    ) as zip_file:
        for item in assets:
            zip_file.writestr(
                item["filename"],
                item["bytes"]
            )
    zip_buffer.seek(0)
    return zip_buffer

# =====================================================
# SWATCH LOADER
# =====================================================

SWATCH_FOLDER = "swatches"
swatch_files = []

if os.path.exists(SWATCH_FOLDER):
    for file in os.listdir(SWATCH_FOLDER):
        if file.lower().endswith(
            (".png", ".jpg", ".jpeg")
        ):
            swatch_files.append(file)

swatch_files.sort()

# =====================================================
# SESSION STATE
# =====================================================

if "results" not in st.session_state:
    st.session_state.results = []

# =====================================================
# SIDEBAR
# =====================================================

with st.sidebar:
    st.header("🔑 OpenAI")
    api_key = st.text_input(
        "OpenAI API Key",
        type="password"
    )
    st.markdown("---")
    st.header("🎨 Swatches")
    selected_swatches = st.multiselect(
        "Choose Swatches",
        swatch_files
    )

# =====================================================
# MAIN
# =====================================================

left, right = st.columns([1, 1.2])

with left:
    st.header("Product")
    product_name = st.text_input(
        "Product Name",
        value="Chesterfield Couch"
    )
    uploaded_image = st.file_uploader(
        "Upload Couch Image",
        type=["png", "jpg", "jpeg"]
    )

with right:
    st.header("Generate Variants")
    if st.button(
        "✨ Generate Variations",
        type="primary"
    ):
        if not api_key:
            st.error("Enter OpenAI API key.")
        elif not uploaded_image:
            st.error("Upload couch image.")
        elif not selected_swatches:
            st.error("Select at least one swatch.")
        else:
            client = OpenAI(api_key=api_key)
            st.session_state.results = []

            for swatch_name in selected_swatches:
                try:
                    with st.spinner(f"Generating {swatch_name}..."):
                        uploaded_image.seek(0)
                        swatch_path = os.path.join(SWATCH_FOLDER, swatch_name)

                        with open(swatch_path, "rb") as swatch_file:
                            prompt = f"""
IMAGE 1:
The first image is a professional furniture product photograph.

IMAGE 2:
The second image is a fabric swatch sample.

TASK:
Replace ONLY the upholstery material on the furniture in image 1.

Use the fabric shown in image 2 as the upholstery reference.

Match exactly:
* fabric texture
* fabric grain
* weave pattern
* corduroy ribbing direction
* velvet pile
* buffalo leather grain
* PU leather finish
* colour
* sheen
* surface characteristics

Preserve exactly:
* couch dimensions
* couch width
* couch height
* couch depth
* arm shape
* cushions
* bolster cushions
* buttons
* studs
* stitching
* piping
* furniture proportions
* camera angle
* shadows
* lighting

Do not redesign.
Do not modernize.
Do not improve.
Do not replace furniture.
Do not change proportions.

This is a furniture catalog upholstery replacement task.

Product Name:
{product_name}

Swatch:
{swatch_name}
"""

                            result = client.images.edit(
                                model="gpt-image-1", # Note: double check if this is your custom model name, as standard OpenAI edit models are 'dall-e-2'
                                image=[uploaded_image, swatch_file],
                                prompt=prompt
                            )

                            image_bytes = base64.b64decode(result.data[0].b64_json)

                            clean_name = (
                                swatch_name
                                .replace("_Fabric_Swatch", "")
                                .replace("_fabric_swatch", "")
                                .replace("_swatch", "")
                                .replace(".png", "")
                                .replace(".jpg", "")
                            )

                            filename = f"{slugify(product_name)}-{slugify(clean_name)}.png"
                            alt_text = f"{product_name} upholstered in {clean_name.replace('_', ' ')}"

                            st.session_state.results.append({
                                "filename": filename,
                                "alt": alt_text,
                                "bytes": image_bytes,
                                "approved": True
                            })

                except Exception as e:
                    st.error(f"{swatch_name}: {str(e)}")

# =====================================================
# RESULTS
# =====================================================

if st.session_state.results:
    st.markdown("---")
    st.header("Review Results")

    for idx, item in enumerate(st.session_state.results):
        col1, col2 = st.columns([1, 2])

        with col1:
            st.image(
                item["bytes"],
                use_container_width=True
            )
            item["approved"] = st.checkbox(
                "Approve",
                value=item["approved"],
                key=f"approve_{idx}"
            )

        with col2:
            st.text_input(
                "Filename",
                value=item["filename"],
                disabled=True,
                key=f"file_{idx}"
            )
            st.text_area(
                "Alt Text",
                value=item["alt"],
                height=100,
                disabled=True,
                key=f"alt_{idx}"
            )

    approved = [x for x in st.session_state.results if x["approved"]]

    if approved:
        zip_file = create_zip(approved)
        st.download_button(
            "📦 Download Approved Images ZIP",
            data=zip_file,
            file_name="that-couch-place-variants.zip",
            mime="application/zip"
        )
import streamlit as st
from pathlib import Path
import json
from datetime import datetime
from PIL import Image

# --- CONFIG ---
st.set_page_config(page_title="Lifestyle Prompt Builder", layout="wide")
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# --- SIMPLIFIED SCENE LIBRARY ---
SCENES = {
    "Bright & Scandi": "Sun-drenched Scandinavian-style living space with light oak floors and sheer curtains. Open, airy composition with natural light and soft tones.",
    "Cozy & Warm": "Inviting family room with warm lighting and wooden textures. Comfortable, relaxed atmosphere with soft shadows and evening glow.",
    "Industrial Loft": "Bright industrial loft with exposed brick walls and large windows. Afternoon sunlight cutting across concrete floors.",
    "Luxury Lodge": "Grand lodge lounge with high ceilings and warm golden light. Natural materials and open views create a serene mood.",
    "Weekend Getaway": "Relaxed coastal holiday home with whitewashed floors and open doors to a deck. Breezy seaside light fills the space.",
    "Student Res": "Compact, functional apartment common room with neutral walls and practical furnishings. Bright, efficient lighting."
}

# --- HELPERS ---
def save_uploaded_file(uploaded_file):
    dest = UPLOAD_DIR / uploaded_file.name
    with open(dest, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return str(dest.as_posix())

def build_prompt(product_ref, scene_text, render_style):
    return (
        f"Place this product in the following setting:\n\n"
        f"Scene: {scene_text}\n"
        f"Rendering style: {render_style}\n"
        f"Notes: Use the exact product image provided; do not substitute or hallucinate the product."
    )

# --- UI ---
st.title("Lifestyle Image Prompt Builder")

# Product input
st.subheader("Main product image")
col1, col2 = st.columns([1, 2])
with col1:
    product_file = st.file_uploader("Upload product image (jpg/png)", type=["jpg", "jpeg", "png"])
    product_url = st.text_input("Or enter hosted product image URL")
with col2:
    if product_file:
        st.image(Image.open(product_file), caption="Uploaded product", width="stretch")
    elif product_url:
        st.image(product_url, caption="Hosted product", width="stretch")
    else:
        st.info("Upload or paste a hosted image URL to proceed.")

# Scene selection
st.subheader("Choose a lifestyle scene")
selected_scene = st.selectbox("Select scene", list(SCENES.keys()))
scene_text = SCENES[selected_scene]

# Rendering style
render_style = st.text_input(
    "Rendering style",
    value="Hyper-realistic interior photography, warm golden hour lighting, 8k resolution, photorealistic fabric detail"
)

# Build prompt
if st.button("Generate Prompt"):
    if not product_file and not product_url:
        st.error("Please upload or provide a hosted product image.")
    else:
        product_ref = product_url if product_url else save_uploaded_file(product_file)
        final_prompt = build_prompt(product_ref, scene_text, render_style)

        st.subheader("Generated Prompt")
        st.text_area("Prompt (copy/paste to your AI tool)", final_prompt, height=220)

        metadata = {
            "product_image": product_ref,
            "scene": selected_scene,
            "scene_text": scene_text,
            "render_style": render_style,
            "generated_at": datetime.utcnow().isoformat() + "Z"
        }

        st.download_button("Download Prompt as TXT", final_prompt, file_name="lifestyle_prompt.txt")
        st.download_button("Download Metadata as JSON", json.dumps(metadata, indent=2), file_name="lifestyle_prompt.json")

# Footer
st.markdown("---")
st.caption("Simplified prompt logic: minimal object description, flexible scene interpretation, product image preserved exactly.")

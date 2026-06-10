import streamlit as st
import base64
from openai import OpenAI

st.set_page_config(
    page_title="That Couch Place Lifestyle Generator",
    page_icon="🛋️",
    layout="wide"
)

st.title("🛋️ That Couch Place Lifestyle Generator")

api_key = st.sidebar.text_input(
    "OpenAI API Key",
    type="password"
)

product_name = st.text_input(
    "Product Name",
    placeholder="Example: Chesterfield Corner Couch"
)

style_choice = st.selectbox(
    "Room Style",
    [
        "Auto Detect",
        "Luxury Lodge",
        "Modern Minimalist",
        "Coastal",
        "Industrial Loft",
        "Weekend Getaway",
        "Student Res"
    ]
)

camera_angle = st.selectbox(
    "Camera Angle",
    [
        "Wide Interior",
        "45 Degree",
        "Front Elevation",
        "Editorial Magazine"
    ]
)

hero_product = st.file_uploader(
    "Hero Product (Required)",
    type=["jpg","jpeg","png"]
)

coffee_table = st.file_uploader(
    "Coffee Table (Optional)",
    type=["jpg","jpeg","png"]
)

rug = st.file_uploader(
    "Rug / Carpet (Optional)",
    type=["jpg","jpeg","png"]
)

accent_chair = st.file_uploader(
    "Accent Chair (Optional)",
    type=["jpg","jpeg","png"]
)

lamp = st.file_uploader(
    "Lamp (Optional)",
    type=["jpg","jpeg","png"]
)

if hero_product:
    st.image(hero_product, width=350)

if st.button("Generate Lifestyle Image"):

    if not api_key:
        st.error("Please enter an API key.")
        st.stop()

    if not hero_product:
        st.error("Please upload a hero product.")
        st.stop()

    with st.spinner("Creating lifestyle scene..."):

        room_instruction = ""

        if style_choice == "Auto Detect":
            room_instruction = """
            Determine the most suitable interior environment
            for this furniture product.
            """
        else:
            room_instruction = f"""
            Create a {style_choice} interior.
            """

        prompt = f"""
        Create an ultra realistic luxury furniture lifestyle image.

        HERO PRODUCT:
        {product_name}

        {room_instruction}

        CAMERA:
        {camera_angle}

        IMPORTANT:

        The hero product must be the visual focus.

        Design the room around the furniture.

        Use professional interior styling.

        Use realistic lighting.

        Create a premium ecommerce photograph.

        Suitable for:
        Shopify
        Meta Ads
        Website Hero Banner

        Optional supporting decor may include:
        coffee table
        rug
        accent chair
        lamp

        Decor must remain secondary.

        The hero product must dominate the image.
        """

        try:

            client = OpenAI(
                api_key=api_key
            )

            response = client.images.generate(
                model="gpt-image-1",
                prompt=prompt,
                size="1024x1024",
                n=1
            )

            image_b64 = response.data[0].b64_json

            image_bytes = base64.b64decode(
                image_b64
            )

            st.image(
                image_bytes,
                caption="Generated Lifestyle Scene",
                use_container_width=True
            )

            st.download_button(
                "Download Image",
                image_bytes,
                file_name=f"{product_name}.png",
                mime="image/png"
            )

        except Exception as e:
            st.error(str(e))
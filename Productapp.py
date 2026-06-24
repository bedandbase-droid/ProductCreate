import streamlit as st
from PIL import Image
from google import genai
from google.genai import types
import json
import re
import requests

# ====================== INITIALIZATION & LAYOUT ======================
st.set_page_config(page_title="AI Product Text Studio", layout="wide")
st.title("🛋️ AI Product Matrix & Text Studio")
st.write("Generate complete, SEO-optimized Shopify product descriptions and technical data templates instantly.")
st.markdown("---")

if 'generated_product' not in st.session_state:
    st.session_state['generated_product'] = {}

# ====================== SIDEBAR CONFIGURATION ======================
with st.sidebar:
    st.header("🔑 API Configuration")
    gemini_key = st.text_input(
        "Gemini API Key", 
        value="", 
        type="password",
        help="Enter your Gemini API key here."
    )
    
    st.header("🛍️ Shopify Connection")
    shopify_url = st.text_input("Shopify Store URL", value="that-couch-place.myshopify.com")
    shopify_api_key = st.text_input("Shopify API Key / Client Key", value="8ea16b30d85ce8f2e530e4e70893a9b5")
    
    # Securely input your Shopify API secret key
    shopify_api_secret = st.text_input(
        "Shopify API Secret / Client Secret",
        value="",
        type="password",
        help="Enter your Shopify app secret for token exchange."
    )
    
    shopify_access_token = st.text_input(
        "Shopify Access Token (optional)",
        value="",
        type="password",
        help="If you already have a valid store access token, paste it here to skip token exchange."
    )

# ====================== MASTER FABRIC SWATCH GUIDE ======================
FABRIC_DATABASE = {
    "Corduroy": ["Light Mocha Brown Corduroy", "Warm Cream Corduroy", "Dark Grey Corduroy", "Olive Green Corduroy", "Deep Teal Corduroy"],
    "Buffalo Fabric": ["Light Buffalo", "Black Buffalo", "Cream Buffalo", "Dark Brown Buffalo", "Light Grey Buffalo", "Ox-Blood Buffalo"],
    "Poly Linen": ["Light Grey Fabric", "Black Fabric", "Cream Fabric", "Charcoal Fabric"],
    "PU Leather": ["Black PU", "Brown PU", "Cream PU"],
    "Velvet": ["Dark Grey Velvet", "Emerald Velvet", "Royal Blue Velvet", "Light Grey Velvet", "Pink Velvet", "Sky Blue Velvet", "Black Velvet", "Dark Pink Velvet", "Cream Velvet"],
    "Ripstop Canvas": ["Grey Canvas", "Blue Canvas", "Brown Canvas", "Green Canvas"],
    "Colour": ["Black", "Red", "White", "Grey", "Cream", "Clear", "Brown"]
}

COLLECTIONS = [
    "Cozy Corner Couches Collection", "Division Couches", "Lodge Collection",
    "Tables and Chairs", "Mattress Toppers", "Newly Weds Collection",
    "Office Furniture", "Sleeper Couches", "Student Collection",
    "Toddler To Teen Collection", "Ultimate Bed & Mattresses Collection",
    "Ultimate U-Shape Couches Collection", "Specials: Limited Deals"
]

# Automated OAuth Client Credentials token exchange engine
def get_automated_shopify_token(shop_url, api_key, api_secret):
    token_url = f"https://{shop_url}/admin/oauth/access_token"
    payload = {
        "client_id": api_key,
        "client_secret": api_secret,
        "grant_type": "client_credentials"
    }
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(token_url, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json().get("access_token")
        return None
    except Exception:
        return None

# ====================== MAIN FACTORY UI LAYOUT ======================
col1, col2 = st.columns([1, 1.2])

with col1:
    st.header("1. Product Configuration")
    product_base_name = st.text_input("Product Base Name", value="Chesterfield Couch")
    category = st.selectbox("Collection", COLLECTIONS)
    
    st.subheader("Fabric Types & Colors")
    selected_fabric_types = st.multiselect(
        "Select Fabric Type(s)", 
        options=list(FABRIC_DATABASE.keys()), 
        default=["Corduroy"]
    )
    
    # Process cascading multi-select panels dynamically
    fabric_selections = {}
    for fabric in selected_fabric_types:
        colors = FABRIC_DATABASE[fabric]
        selected = st.multiselect(f"Colors for {fabric}", colors, default=colors[:2], key=f"colors_{fabric}")
        if selected:
            fabric_selections[fabric] = selected

    st.subheader("Product Image Reference")
    uploaded_image = st.file_uploader(
        "Upload a product photo for AI reference",
        type=["jpg", "jpeg", "png"],
        help="Upload a photo the AI can use when generating the product description and SEO copy."
    )
    if uploaded_image:
        st.image(Image.open(uploaded_image), caption="Uploaded product image", width=400)

    st.subheader("📏 Dimensions")
    use_ai_dimensions = st.toggle("Let Gemini auto-fill missing dimensions", value=True)
    
    with st.expander("Enter Known Dimensions (mm)", expanded=True):
        col_a, col_b = st.columns(2)
        with col_a:
            total_width = st.text_input("Total Width (mm)", value="2500")
            seat_width = st.text_input("Seat Width (mm)", value="700")
            chaise_width = st.text_input("Chaise Width (mm)", value="")
            adjustable_from = st.text_input("Adjustable Height From (mm)", value="")
        with col_b:
            total_depth = st.text_input("Total Depth (mm)", value="950")
            seat_depth = st.text_input("Seat Depth (mm)", value="700")
            chaise_length = st.text_input("Chaise Length (mm)", value="")
            adjustable_to = st.text_input("Adjustable Height To (mm)", value="")
        total_height = st.text_input("Total Height (mm)", value="850")
        seat_height = st.text_input("Seat Height (mm)", value="450")

    st.subheader("Internal Construction")
    core_material = st.text_input("Internal Core / Frame Structure", value="Solid Pine Frame / High-density foam layers")
    comfort_level = st.selectbox(
        "Comfort Rating (optional)",
        options=["", "Soft", "Medium", "Firm"],
        index=0,
        help="Leave this blank if you do not want to specify a firmness level."
    )

with col2:
    st.header("2. Generate & Push Product")

    if st.button("✨ Generate Complete Shopify-Ready Product", type="primary"):
        if not gemini_key:
            st.error("Gemini API Key is required")
        elif not fabric_selections:
            st.error("Please select at least one fabric and color choice.")
        elif not uploaded_image:
            st.error("Please upload a product image for AI reference.")
        else:
            with st.spinner("Compiling copy blueprint and analyzing sizing parameters..."):
                try:
                    variant_summary = [f"{fabric}: {', '.join(colors)}" for fabric, colors in fabric_selections.items()]
                    variant_text = " | ".join(variant_summary)

                    dimensions_input = f"Total: {total_width}W x {total_depth}D x {total_height}H mm | Seat: {seat_width}x{seat_depth}x{seat_height}mm"
                    image_note = f"Product image filename: {uploaded_image.name}. Use this visual reference when generating copy for the product." if uploaded_image else "No product image was uploaded[...]

                    client = genai.Client(api_key=gemini_key)

                    prompt = f"""
                    You are an expert Shopify furniture copywriter. Create a premium commercial retail product listing description block.
                    Product: {product_base_name}
                    Collection: {category}
                    Fabrics: {variant_text}
                    Construction: {core_material}
                    Comfort: {comfort_level}
                    Dimensions Given: {dimensions_input}
                    Image Reference: {image_note}

                    SIZE ENFORCEMENT & SA MARKET COMPLIANCE:
                    If use_ai_dimensions is True, check all fields. If any dimensions parameters above are blank, evaluate the item archetype, calculate standard industry specifications, and output th[...]
                    Note: For South African bedding layouts, explicitly map the standard 3/4 bed base size (1070mm wide) alongside conventional dimensions metrics.

                    Return ONLY a clean, valid JSON dictionary with these exact keys. Do not wrap in markdown code fences:
                    {{"title": "...", "handle": "...", "meta_title": "...", "meta_description": "...", "body_html": "...", "tags": ["tag1","tag2"]}}
                    """

                    response = client.models.generate_content(model="gemini-2.5-flash", contents=[prompt])
                    text = response.text.strip()
                    
                    try:
                        product_data = json.loads(text)
                    except:
                        json_match = re.search(r'\{[\s\S]*\}', text)
                        product_data = json.loads(json_match.group(0)) if json_match else {"title": "JSON Parse Failed"}

                    st.session_state['generated_product'] = product_data
                    st.success("✅ Complete text template model computed successfully!")

                    st.subheader("Calculated SEO Title")
                    st.success(product_data.get("title", "N/A"))
                    st.subheader("Meta Description Block")
                    st.info(product_data.get("meta_description", "N/A"))
                    st.subheader("HTML Body Blueprint Preview")
                    st.markdown(product_data.get("body_html", "No content"))

                except Exception as e:
                    st.error(f"Generation Engine Runtime Error: {str(e)}")

    st.markdown("---")
    
    # ==================== SHOPIFY API INJECTION COMMANDS ====================
    if st.button("🚀 Push to Shopify as Draft", type="secondary"):
        if not st.session_state.get('generated_product'):
            st.error("Please generate the product first before running the push engine!")
        elif not shopify_access_token and not shopify_api_secret:
            st.error("Please enter either a valid Shopify access token or your Shopify API secret.")
        else:
            with st.spinner("Exchanging OAuth keys and transmitting data packets directly into Shopify..."):
                try:
                    if shopify_access_token:
                        access_token = shopify_access_token
                    else:
                        access_token = get_automated_shopify_token(shopify_url, shopify_api_key, shopify_api_secret)
                    
                    if not access_token:
                        st.error("Shopify authentication failed. Verify your API key/secret or provide a valid access token.")
                    else:
                        product_data = st.session_state['generated_product']

                        shopify_payload = {
                            "product": {
                                "title": product_data.get("title"),
                                "body_html": product_data.get("body_html"),
                                "vendor": "That Couch Place",
                                "product_type": category,
                                "status": "draft",
                                "tags": ",".join(product_data.get("tags", [])),
                                "handle": product_data.get("handle")
                            }
                        }

                        api_url = f"https://{shopify_url}/admin/api/2026-04/products.json"
                        headers = {
                            "X-Shopify-Access-Token": access_token,
                            "Content-Type": "application/json"
                        }

                        resp = requests.post(api_url, json=shopify_payload, headers=headers)

                        if resp.status_code == 201:
                            st.success(f"🎉 Success! '{product_base_name}' text listing has been pushed straight to your Shopify store dashboard as a Draft!")
                            st.balloons()
                        else:
                            st.error(f"Shopify Core Error ({resp.status_code}): {resp.text}")

                except Exception as e:
                    st.error(f"Network Connection Fault: {str(e)}")

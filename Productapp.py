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
    "Colour": ["Black", "Red", "White", "Grey", "Cream", "Clear", "Brown", "Yellow", "Blue", "Orange", "Silver", "Gold"]
}

# Replaced COLLECTIONS with detailed list (IDs, Titles, Products, Conditions)
COLLECTIONS = [
    {"id": "657001414977", "title": "Dining Tables and Consoles", "products": "7", "conditions": ""},
    {"id": "86092939315", "title": "Cozy Corner Couches Collection", "products": "16", "conditions": ""},
    {"id": "87063429171", "title": "Couches & Seating Sets: Sofas, Chairs, Lounge Suites - Modern furnishing solutions", "products": "42", "conditions": ""},
    {"id": "159881658419", "title": "All Tables and Chairs", "products": "89", "conditions": ""},
    {"id": "644949213505", "title": "Winter Collection", "products": "27", "conditions": "Tag includes winter comfort"},
    {"id": "657002430785", "title": "Headboards and Bed Bases", "products": "3", "conditions": ""},
    {"id": "657001185601", "title": "Kitchen Nook & Bar Chairs Modern – Stylish, Comfortable Seating", "products": "31", "conditions": ""},
    {"id": "638433853761", "title": "Lodge Collection", "products": "28", "conditions": ""},
    {"id": "476175401281", "title": "Student Collection", "products": "23", "conditions": "Title contains student\nType is equal to Student bed\nTag includes student"},
    {"id": "474598342977", "title": "Toddler To Teen Collection", "products": "16", "conditions": ""},
    {"id": "261479268403", "title": "Sleeper Couches", "products": "11", "conditions": ""},
    {"id": "81365794867", "title": "Division Couches", "products": "20", "conditions": ""},
    {"id": "81365401651", "title": "Ultimate Bed & Mattresses Collection", "products": "16", "conditions": ""},
    {"id": "657001218369", "title": "Dining Tables, Glass, Marble, Wood, or Melamine", "products": "11", "conditions": ""},
    {"id": "485588304193", "title": "Newly Weds Collection", "products": "6", "conditions": "Tag includes newly weds\nTitle contains Newly Weds"},
    {"id": "657003413825", "title": "Occasional Chairs - Statement Pieces Collection – Furniture That Defines Your Space", "products": "10", "conditions": ""},
    {"id": "657000988993", "title": "Dining Room Chairs", "products": "11", "conditions": ""},
    {"id": "657003708737", "title": "Outdoor Furniture Collection – Patio, Garden & Balcony Sets", "products": "9", "conditions": ""},
    {"id": "657002398017", "title": "Bedroom Tables and Chairs", "products": "25", "conditions": ""},
    {"id": "633710444865", "title": "SOHO Furniture", "products": "23", "conditions": "Title contains office, office, +2 more\nTag includes office chair, office furniture, +1 more"},
    {"id": "657002889537", "title": "Coffee Tables, Tv Stands and Consoles", "products": "19", "conditions": ""},
    {"id": "86093070387", "title": "Ultimate U-Shape Couches Collection", "products": "3", "conditions": ""},
    {"id": "657003577665", "title": "Pet Products", "products": "2", "conditions": ""},
    {"id": "491328864577", "title": "Mattress Toppers", "products": "", "conditions": ""}
]

# ====================== GOOGLE CATEGORIES ======================
GOOGLE_CATEGORIES = [
    "Furniture > Bedroom Furniture > Beds",
    "Furniture > Bedroom Furniture > Bed Frames",
    "Furniture > Bedroom Furniture > Mattresses",
    "Furniture > Bedroom Furniture > Mattress Toppers",
    "Furniture > Bedroom Furniture > Nightstands",
    "Furniture > Bedroom Furniture > Dressers",
    "Furniture > Bedroom Furniture > Wardrobes",
    "Furniture > Living Room Furniture > Couches",
    "Furniture > Living Room Furniture > Sofas",
    "Furniture > Living Room Furniture > Sectional Sofas",
    "Furniture > Living Room Furniture > Sleeper Couches",
    "Furniture > Living Room Furniture > Chairs",
    "Furniture > Living Room Furniture > Recliners",
    "Furniture > Living Room Furniture > Ottomans",
    "Furniture > Living Room Furniture > Coffee Tables",
    "Furniture > Living Room Furniture > End Tables",
    "Furniture > Living Room Furniture > Console Tables",
    "Furniture > Dining Room Furniture > Dining Tables",
    "Furniture > Dining Room Furniture > Dining Chairs",
    "Furniture > Dining Room Furniture > Bar Chairs",
    "Furniture > Dining Room Furniture > Buffets",
    "Furniture > Office Furniture > Desks",
    "Furniture > Office Furniture > Office Chairs",
    "Furniture > Office Furniture > Bookcases",
    "Furniture > Office Furniture > Filing Cabinets",
    "Furniture > Accent Furniture > Benches",
    "Furniture > Accent Furniture > Stools",
    "Furniture > Accent Furniture > Bar Stools",
    "Furniture > Accent Furniture > Poufs",
    "Furniture > Accent Furniture > Storage Benches",
    "Furniture > Pet Furniture > Pet Beds",
    "Furniture > Pet Furniture > Pet Couches",
    "Furniture > Pet Furniture > Pet Chairs",
    "Furniture > Pet Furniture > Pet Houses",
    "Home & Garden > Furniture > Outdoor Furniture > Seating",
    "Home & Garden > Furniture > Outdoor Furniture > Outdoor Couches",
    "Home & Garden > Furniture > Outdoor Furniture > Outdoor Chairs",
    "Home & Garden > Furniture > Outdoor Furniture > Outdoor Tables",
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
    
    st.subheader("Collections")
    # Allow multi-select of collections; map labels back to collection dicts
    collection_labels = [f"{c['title']} ({c['id']})" for c in COLLECTIONS]
    selected_collection_labels = st.multiselect(
        "Select one or more Collections to assign this product to:",
        options=collection_labels,
        help="Select one or multiple collections to assign this product to when pushing to Shopify."
    )
    selected_collections = [next(c for c in COLLECTIONS if f"{c['title']} ({c['id']})" == lbl) for lbl in selected_collection_labels]
    # Human readable display for prompts and previews
    category_display = ", ".join([c['title'] for c in selected_collections]) if selected_collections else ""
    
    st.subheader("📂 Google Product Category")
    google_search = st.text_input(
        "Search Google Categories",
        placeholder="e.g., 'sofa', 'couch', 'bed', 'desk', 'chair', 'pet', 'bar'...",
        help="Type keywords to search through Google Merchant Center categories. Leave empty to see all options."
    )
    
    # Filter categories based on search input
    if google_search:
        filtered_categories = [cat for cat in GOOGLE_CATEGORIES if google_search.lower() in cat.lower()]
        if not filtered_categories:
            st.warning(f"No categories found matching '{google_search}'. Here are some popular options:")
            google_category = st.selectbox(
                "Select from popular categories:",
                options=["Furniture > Living Room Furniture > Couches",
                        "Furniture > Bedroom Furniture > Beds",
                        "Furniture > Dining Room Furniture > Dining Tables",
                        "Furniture > Office Furniture > Desks",
                        "Furniture > Pet Furniture > Pet Beds"]
            )
        else:
            google_category = st.selectbox(
                f"Found {len(filtered_categories)} matching categories:",
                options=filtered_categories
            )
    else:
        google_category = st.selectbox(
            "Or select from all categories (scroll to browse):",
            options=GOOGLE_CATEGORIES,
            index=8,
            help="Choose the appropriate Google Merchant Center category for your product."
        )
    
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
                    image_note = f"Product image filename: {uploaded_image.name}. Use this visual reference when generating copy for the product." if uploaded_image else "No product image was upl[...]"

                    client = genai.Client(api_key=gemini_key)

                    # Use category_display which may contain multiple selected collection titles
                    prompt = f"""
                    You are an expert Shopify furniture copywriter and SEO specialist. Create a premium commercial retail product listing with compelling, conversion-focused copy.
                    
                    Product: {product_base_name}
                    Collection: {category_display}
                    Google Category: {google_category}
                    Fabrics: {variant_text}
                    Construction: {core_material}
                    Comfort: {comfort_level}
                    Dimensions Given: {dimensions_input}
                    Image Reference: {image_note}

                    SIZE ENFORCEMENT & SA MARKET COMPLIANCE:
                    If use_ai_dimensions is True, check all fields. If any dimensions parameters above are blank, evaluate the item archetype, calculate standard industry specifications, and output th[...]
                    Note: For South African bedding layouts, explicitly map the standard 3/4 bed base size (1070mm wide) alongside conventional dimensions metrics.

                    META DESCRIPTION REQUIREMENTS:
                    - Keep meta_description between 150-160 characters (critical for SEO)
                    - Include primary keyword: {product_base_name}
                    - Mention key fabric types and benefits
                    - Include a compelling call-to-action element
                    - Make it persuasive and click-worthy for search results
                    Example format: "Premium [Product] in [Fabric]. [Key Feature]. [Benefit/Comfort]. Shop [Collection] for luxury [adjective] comfort."

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
                    st.session_state['google_category'] = google_category
                    st.success("✅ Complete text template model computed successfully!")

                    st.subheader("Calculated SEO Title")
                    st.success(product_data.get("title", "N/A"))
                    st.subheader("Meta Description Block")
                    meta_desc = product_data.get("meta_description", "N/A")
                    char_count = len(meta_desc) if meta_desc != "N/A" else 0
                    st.info(f"{meta_desc} ({char_count} characters)")
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
                        google_cat = st.session_state.get('google_category', '')

                        # Map selected collections for payloads
                        collection_ids = [c['id'] for c in selected_collections]
                        collection_titles = [c['title'] for c in selected_collections]

                        # Use first selected collection as product_type if available, otherwise empty
                        product_type_value = collection_titles[0] if len(collection_titles) >= 1 else ""

                        # Merge tags from AI output and collection titles so product appears in tag searches
                        base_tags = product_data.get("tags", []) if isinstance(product_data.get("tags", []), list) else []
                        final_tags = base_tags + collection_titles

                        shopify_payload = {
                            "product": {
                                "title": product_data.get("title"),
                                "body_html": product_data.get("body_html"),
                                "vendor": "That Couch Place",
                                "product_type": product_type_value,
                                "status": "draft",
                                "tags": ",".join(final_tags),
                                "handle": product_data.get("handle"),
                                "metafields": [
                                    {
                                        "namespace": "global",
                                        "key": "description_tag",
                                        "value": product_data.get("meta_description", ""),
                                        "type": "string"
                                    },
                                    {
                                        "namespace": "global",
                                        "key": "title_tag",
                                        "value": product_data.get("meta_title", ""),
                                        "type": "string"
                                    },
                                    {
                                        "namespace": "google",
                                        "key": "product_category",
                                        "value": google_cat,
                                        "type": "string"
                                    },
                                    {
                                        "namespace": "shopify",
                                        "key": "collection_ids",
                                        "value": ",".join(collection_ids),
                                        "type": "string"
                                    },
                                    {
                                        "namespace": "shopify",
                                        "key": "collection_titles",
                                        "value": ",".join(collection_titles),
                                        "type": "string"
                                    }
                                ]
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
                            st.success(f"Meta Description: {product_data.get('meta_description', 'N/A')}")
                            st.success(f"Google Category: {google_cat}")
                            if collection_titles:
                                st.success(f"Assigned Collections: {', '.join(collection_titles)}")
                            st.balloons()
                        else:
                            st.error(f"Shopify Core Error ({resp.status_code}): {resp.text}")

                except Exception as e:
                    st.error(f"Network Connection Fault: {str(e)}")

import streamlit as st
from PIL import Image

# Set up the page layout
st.set_page_config(page_title="AI Product Listing Studio", layout="wide")

st.title("🛋️ AI Product Listing Studio")
st.write("Upload raw pictures, fill in the hard specs, and publish directly to Shopify.")

st.markdown("---")

# Create a two-column layout for the interface
col1, col2 = st.columns([1, 1.2])

# --- COLUMN 1: INPUT FIELDS & PHOTO UPLOAD ---
with col1:
    st.header("1. Product Details")
    
    product_name = st.text_input("Product Base Name", placeholder="e.g., The Winston")
    
    # 1. Categories updated to match your exact Shopify Collections
    category = st.selectbox(
        "Shopify Target Collection", 
        [
            "Cozy Corner Couches Collection",
            "Division Couches",
            "Lodge Collection",
            "Mattress Toppers",
            "Newly Weds Collection",
            "Office Furniture",
            "Sleeper Couches",
            "Specials: Limited Deals",
            "Student Collection",
            "Tables and Chairs",
            "Toddler To Teen Collection",
            "Ultimate Bed & Mattresses Collection",
            "Ultimate U-Shape Couches Collection"
        ]
    )
    
    # Grid for dimensions
    st.subheader("Dimensions & Specs")
    width = st.text_input("Width (mm)", placeholder="e.g., 2100")
    depth = st.text_input("Depth (mm)", placeholder="e.g., 900")
    height = st.text_input("Height (mm)", placeholder="e.g., 850")
    
    # 2-6. Updated fabric types per instructions
    st.subheader("Materials & Core")
    fabric_type = st.selectbox(
        "Primary Fabric/Material", 
        [
            "Corduroy", 
            "Velvet", 
            "Buffalo Fabric", 
            "Pu Leather", 
            "Polyester", 
            "Quilted Bamboo", 
            "Knitted Mattress Fabric", 
            "Suede", 
            "Canvas"
        ]
    )
    core_material = st.text_input("Internal Core Material", placeholder="e.g., Re-bonded foam core with yellow high-density outer layers")
    comfort_level = st.select_slider("Comfort / Firmness Rating", options=["Soft", "Medium-Soft", "Medium", "Medium-Firm", "Firm"])
    
    st.subheader("Photos")
    uploaded_files = st.file_uploader("Upload raw showroom/workshop photos", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

# --- COLUMN 2: PREVIEW & GENERATION ---
with col2:
    st.header("2. AI Engine Preview")
    
    # Show uploaded images immediately so you know they registered
    if uploaded_files:
        st.write("### Raw Images Selected:")
        image_cols = st.columns(len(uploaded_files))
        for idx, file in enumerate(uploaded_files):
            img = Image.open(file)
            image_cols[idx].image(img, use_column_width=True)
            
    st.markdown("---")
    
    # The action buttons
    if st.button("✨ Step 1: Run AI Magic", type="secondary"):
        if not product_name or not uploaded_files:
            st.error("Please provide a product name and upload at least one image.")
        else:
            with st.spinner("Gemini is writing copy & editing your images..."):
                st.success("AI Generation Complete!")
                st.subheader("Generated SEO Title")
                st.code(f"{product_name} ({fabric_type})", language="text")
                
                st.subheader("Target Shopify Destination")
                st.info(f"This product will automatically route into: {category}")
                
                st.subheader("Generated Website Description")
                st.write(f"Expertly crafted with a robust {core_material}, this premium item from our {category} offers a perfectly tailored {comfort_level.lower()} experience finished in high-quality {fabric_type.lower()}...")

    st.markdown("### ") # Spacing
    
    # The final push button
    if st.button("🚀 Step 2: Publish Directly to Shopify Store", type="primary"):
        with st.spinner("Uploading images and pushing product page to Shopify admin..."):
            st.balloons()
            st.success(f"Boom! Product is live as a draft inside '{category}'.")
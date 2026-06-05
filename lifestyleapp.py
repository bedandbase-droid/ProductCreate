import streamlit as st
from pathlib import Path

# --- CONFIG ---
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Lifestyle prompt library (expanded from your PDF)
LIFESTYLE_PROMPTS = {
    # 3-Piece Division Couches
    "Bright & Scandi": "Arrange the 3-piece division couch in a spacious, sun-drenched Scandinavian-style living room with light oak floors...",
    "Cozy & Warm": "Position the 3-piece division couch in a warm, inviting family room with exposed wooden ceiling beams and a stone fireplace...",
    "Industrial Loft": "Place the 3-piece division couch floating in the center of an industrial concrete loft with exposed brick walls...",
    "Luxury Lodge (Couch)": "Arrange the 3-piece division couch in a grand, double-volume safari lodge lounge with exposed thatch ceilings...",
    "Weekend Getaway (Couch)": "Place the 3-piece division couch in a cozy, sun-drenched coastal holiday home with whitewashed wooden floors...",
    "Student Res (Couch)": "Position the 3-piece division couch pushed together as a solid, space-efficient 3-seater sofa against a clean, neutral wall...",

    # Corner Couches
    "Modern Minimalist": "Float the large L-shaped corner couch in a sleek, ultra-modern open-plan apartment...",
    "Sunroom Transition": "Place the corner couch snugly against a wall of sliding glass doors that open up to a lush, green garden patio...",
    "Moody Luxury": "Position the corner couch in a dark, moody media room or home cinema setup with charcoal-painted walls...",
    "Luxury Lodge (Corner Couch)": "Float the massive L-shaped corner couch in an expansive game lodge viewing deck enclosed with floor-to-ceiling glass...",
    "Weekend Getaway (Corner Couch)": "Place the corner couch snugly into the corner of a rustic forest cabin lounge with a roaring wood-burning stove...",
    "Student Res (Corner Couch)": "Position the compact corner couch in the living area of a modern, trendy student loft apartment...",

    # Accent Chair
    "Reading Nook": "Place the single accent chair at a 45-degree angle in a cozy, sunlit corner of a room...",
    "Lounge Companion": "Position the accent chair opposite a large corner couch, breaking up the living room space...",
    "Bedroom Retreat": "Place the accent chair next to a large window in a spacious master bedroom...",
    "Luxury Lodge (Chair)": "Place the single accent chair next to a massive telescope facing an open savanna view window...",
    "Weekend Getaway (Chair)": "Position the accent chair in a sunny bay window nook of a country cottage...",
    "Student Res (Chair)": "Place the accent chair in the corner of a compact student bedroom...",

    # Sleeper Couch
    "Stylish Studio": "Position the sleeper couch folded up as a crisp 3-seater sofa along the main wall of a chic studio apartment...",
    "Guest Suite": "Show the sleeper couch fully unfolded into a bed in a bright, dedicated guest bedroom...",
    "Home Office": "Place the sleeper couch against the back wall of a modern home office...",
    "Luxury Lodge (Sleeper)": "Position the sleeper couch folded up as an elegant sofa in the private lounge alcove of a luxury safari suite...",
    "Weekend Getaway (Sleeper)": "Show the sleeper couch fully unfolded into a comfortable bed in a cozy countryside Airbnb cottage...",
    "Student Res (Sleeper)": "Position the sleeper couch folded up as a sleek 3-seater sofa against the main wall of a student apartment...",

    # Coffee Table
    "Architectural": "Center the coffee table perfectly in front of a modern linear sofa...",
    "Lived-in Family": "Place the coffee table in the center of a bustling family living room setup...",
    "High-End Contrast": "Position the coffee table directly within the crook of a deep-seated fabric corner couch...",
    "Luxury Lodge (Table)": "Center the coffee table within a high-end lodge lounge layout...",
    "Weekend Getaway (Table)": "Place the coffee table in the center of a relaxed beach cottage living room...",
    "Student Res (Table)": "Position the coffee table centrally in a modern student apartment lounge...",

    # Bedroom: Headboard
    "Boutique Feature": "Mount the luxury upholstered headboard centrally against a dramatic, vertically paneled wooden feature wall...",
    "Soft & Organic": "Position the standalone headboard against a soft cream, lime-washed textured wall...",
    "Urban Masculine": "Place the headboard against a raw, dark concrete wall in a modern urban apartment...",
    "Luxury Lodge (Headboard)": "Mount the luxury upholstered headboard centrally against a dramatic feature wall made of stacked stone...",
    "Weekend Getaway (Headboard)": "Position the standalone headboard against a crisp white paneled wall in a breezy holiday cottage bedroom...",
    "Student Res (Headboard)": "Place the sleek, standalone headboard flush against a minimalist painted brick wall in a student residence...",

    # Bed Set
    "Luxury Master Suite": "Center the complete bed set and matching headboard against a wide, elegant master bedroom wall...",
    "Coastal Sanctuary": "Place the bed set in a bright, white-walled bedroom with sheer linen curtains blowing gently...",
    "Editorial Drama": "Position the bed set in a rich, deeply toned bedroom with olive green or navy walls...",
    "Luxury Lodge (Bed)": "Center the complete bed set and matching headboard in an ultra-luxurious safari oasis bedroom suite...",
    "Weekend Getaway (Bed)": "Place the complete bed set in a charming farmhouse getaway bedroom...",
    "Student Res (Bed)": "Position the bed set (3/4 size) against the wall of a bright, modern student dorm room...",

    # Dining
    "Grand Entertainer": "Position the complete dining table and chairs in a large, open-plan dining hall...",
    "Intimate Family": "Place the dining set in a warm, cottage-style kitchen-dining area...",
    "Sleek Urban": "Position the dining set in a modern apartment dining space...",
    "Luxury Lodge (Dining)": "Position the grand dining table and chairs in an elite lodge dining room...",
    "Weekend Getaway (Dining)": "Place the dining set in a sun-drenched, open-plan holiday cottage kitchen...",
    "Student Res (Dining)": "Position a compact version of the dining set in a modern student apartment kitchen...",

    # Bar Chairs
    "Luxury Island": "Line up three matching bar chairs along a massive, white waterfall marble kitchen island...",
    "Industrial Counter": "Place a row of bar chairs tucked under a rustic wooden bar counter...",
    "Morning Nook": "Position two bar chairs at a compact kitchen counter bathed in bright morning light...",
    "Luxury Lodge (Bar)": "Line up a row of premium bar chairs along a spectacular solid wood bar counter...",
    "Weekend Getaway (Bar)": "Place three matching bar stools tucked under a casual breakfast bar in a holiday home kitchen...",
    "Student Res (Bar)": "Position two sleek, durable bar chairs at a compact kitchen counter ledge in a student studio apartment...",

    # Dining Chairs (Restaurant)
    "High-End Bistro": "Arrange multiple pairs of the dining chairs tucked into dark wood tables in an upscale restaurant...",
    "Trendy Café": "Place the dining chairs around light oak tables in a bright, sunlit café...",
    "Cocktail Lounge": "Position the dining chairs in an exclusive, low-lit restaurant setting...",
    "Luxury Lodge (Restaurant)": "Arrange pairs of the dining chairs at intimate tables spread out across a luxury lodge's outdoor dining deck...",
    "Weekend Getaway (Restaurant)": "Place the dining chairs around rustic wooden tables in a bustling wine estate bistro...",
    "Student / Campus": "Position rows of the durable dining chairs tucked into long tables in a university campus canteen...",

    # Pet Beds
    "Lounge Companion (Pet)": "Place the premium dog bed flat on a light wood floor next to a modern couch...",
    "Sunlit Nap Spot": "Position the durable pet bed in a warm patch of afternoon sunlight on a concrete floor...",
    "Master Bed Setup": "Place the dog bed neatly at the foot of a large bed set...",

    # Ottomans
    "Extended Chaise": "Position a square modular ottoman pushed up against the open end of a division couch...",
    "Freestanding": "Place the modular ottoman freestanding as a flexible center footstool...",
    "Luxury Lodge (Ottoman)": "Position two matching large square ottomans side-by-side in front of a grand fireplace...",
    "Weekend Getaway (Ottoman)": "Place a soft modular ottoman loosely near a cottage window reading nook...",
    "Student Res (Ottoman)": "Tuck the modular ottoman under a floating media ledge in a compact student common area..."
}

# --- STREAMLIT UI ---
st.title("Lifestyle Image Prompt Builder")

# Product upload
product_file = st.file_uploader("Upload main product image", type=["jpg", "png"])
product_url = None
if product_file:
    product_path = UPLOAD_DIR / product_file.name
    with open(product_path, "wb") as f:
        f.write(product_file.getbuffer())
    product_url = f"/uploads/{product_file.name}"  # Replace with your CDN/website URL if hosted
    st.image(product_file, caption="Main Product", width="stretch")

# Decor
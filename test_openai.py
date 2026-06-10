from openai import OpenAI
import base64

client = OpenAI
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)
result = client.images.generate(
    model="gpt-image-1",
    prompt="""
    Chesterfield couch upholstered in ox blood buffalo leather,
    professional ecommerce furniture photograph,
    white background
    """,
    size="1024x1024"
)

image_bytes = base64.b64decode(result.data[0].b64_json)

with open("test_couch.png", "wb") as f:
    f.write(image_bytes)

print("Image saved as test_couch.png")
import os

from openai import OpenAI
import base64

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY", "")
)

with open("/workspaces/ProductCreate/couch.png", "rb") as image_file:

    result = client.images.edit(
        model="gpt-image-1",

        image=image_file,

        prompt="""
        Change this couch upholstery to rich ox blood buffalo leather.

        Preserve:
        - exact couch shape
        - exact cushions
        - exact buttons
        - exact studs
        - exact proportions
        - exact arm shape
        - exact camera angle
        - exact lighting

        Do not redesign the couch.
        Do not change dimensions.
        Do not change furniture style.

        Only replace the upholstery material.

        Create a realistic ecommerce furniture photograph.
        """
    )

image_bytes = base64.b64decode(
    result.data[0].b64_json
)

with open("edited_couch.png", "wb") as f:
    f.write(image_bytes)

print("Saved edited_couch.png")
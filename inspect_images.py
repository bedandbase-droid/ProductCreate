from openai import OpenAI

client = OpenAI(api_key="YOUR_API_KEY")

print(dir(client.images))
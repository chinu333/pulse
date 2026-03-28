"""Quick standalone test for gpt-image-1 via Azure OpenAI."""

import os
from dotenv import load_dotenv

load_dotenv()

from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

endpoint = os.getenv("AZURE_OPENAI_IMAGE_ENDPOINT", "")
deployment = os.getenv("AZURE_OPENAI_IMAGE_DEPLOYMENT", "gpt-image-1")
api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

print(f"Endpoint:   {endpoint}")
print(f"Deployment: {deployment}")
print(f"API Version: {api_version}")

token_provider = get_bearer_token_provider(
    DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
)

client = AzureOpenAI(
    azure_endpoint=endpoint,
    azure_ad_token_provider=token_provider,
    api_version=api_version,
)

prompt = (
    "Photojournalistic news image of a major weather event: "
    "dramatic storm clouds over a coastal city skyline, "
    "editorial photography style, dramatic lighting, high quality, "
    "suitable for a major news network website hero image. "
    "No text overlays. No watermarks."
)

print(f"\nPrompt: {prompt[:100]}...")
print("Generating image... (this may take 15-30 seconds)")

try:
    response = client.images.generate(
        model=deployment,
        prompt=prompt,
        n=1,
        size="1024x1024",
    )
    print(f"\n✅ API call succeeded!")
    item = response.data[0]
    
    if item.b64_json:
        import base64
        img_bytes = base64.b64decode(item.b64_json)
        out_path = os.path.join("static", "images", "test_generated.png")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(img_bytes)
        size_kb = len(img_bytes) / 1024
        print(f"Saved to: {out_path}  ({size_kb:.0f} KB)")
        print("Open this file to verify the image looks correct.")
    elif item.url:
        print(f"URL: {item.url}")
    else:
        print("No image data returned!")
except Exception as e:
    import traceback
    print(f"\n❌ FAILED: {type(e).__name__}: {e}")
    traceback.print_exc()

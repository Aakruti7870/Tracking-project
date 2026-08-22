import asyncio
import os
import base64
from emergentintegrations.llm.chat import LlmChat, UserMessage

API_KEY = os.environ["EMERGENT_LLM_KEY"]
OUT = "/app/frontend/assets/images/transit-mixer.png"

PROMPT = (
    "Ultra realistic cinematic studio product render of a modern ready-mix concrete "
    "TRANSIT MIXER TRUCK. A pristine white and light-grey cement mixer truck with a large "
    "rotating drum, shown in a dynamic three-quarter front view facing left, headlights "
    "glowing warm. The truck sits on a dark seamless charcoal-black studio backdrop with a "
    "soft circular spotlight halo behind it and a subtle glossy reflection on the dark floor. "
    "Dramatic rim lighting, high detail, premium automotive advertising photography, moody "
    "professional lighting, 8k, sharp focus, wide landscape composition with the truck "
    "centered, plenty of dark negative space at the top for text overlay. No text, no logos, "
    "no watermarks."
)


async def main():
    chat = LlmChat(api_key=API_KEY, session_id="mixer-hero-gen", system_message="You are an image generation assistant.")
    chat.with_model("gemini", "gemini-3.1-flash-image-preview").with_params(modalities=["image", "text"])
    msg = UserMessage(text=PROMPT)
    text, images = await chat.send_message_multimodal_response(msg)
    print("text:", (text or "")[:80])
    if not images:
        print("NO IMAGES RETURNED")
        return
    img = images[0]
    print("mime:", img.get("mime_type"))
    data = base64.b64decode(img["data"])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "wb") as f:
        f.write(data)
    print("SAVED:", OUT, len(data), "bytes")


if __name__ == "__main__":
    asyncio.run(main())

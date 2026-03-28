"""
PULSE - Image Generator Agent
Generates hero images and thumbnails for news stories using Azure OpenAI gpt-image-1.
"""

import logging
from app.config import settings
from app.models.schemas import AgentMessage, AgentRole, PipelineState, StoryStatus

logger = logging.getLogger("pulse.agent.image_generator")


async def image_generator_agent(state: dict) -> dict:
    """
    Image Generator Agent — creates a photojournalistic hero image for the story
    using Azure OpenAI's gpt-image-1 model, plus a thumbnail variant.
    """
    pipeline = PipelineState(**state)
    pipeline.current_agent = AgentRole.IMAGE_GENERATOR
    pipeline.status = StoryStatus.GENERATING_IMAGE

    headline = pipeline.input.headline
    draft = pipeline.draft

    # ── Step 1: Generate prompt ──────────────────────────────
    pipeline.messages.append(AgentMessage(
        agent=AgentRole.IMAGE_GENERATOR,
        action="generating_image",
        content=f"🎨 Generating hero image for: \"{headline}\"",
        confidence=0.90,
    ))

    if settings.demo_mode:
        image_result = _mock_image(headline, draft)
    else:
        image_result = await _generate_live_image(headline, draft)

    pipeline.image = image_result

    # ── Step 2: Report results ───────────────────────────────
    num_images = 1 + len(image_result.get("additional_images", []))
    pipeline.messages.append(AgentMessage(
        agent=AgentRole.IMAGE_GENERATOR,
        action="image_generation_complete",
        content=(
            f"✅ Image generation complete:\n"
            f"- Hero image: {image_result.get('dimensions', '1024x1024')}\n"
            f"- Style: {image_result.get('style', 'photojournalistic')}\n"
            f"- Alt text: \"{image_result.get('alt_text', '')[:60]}...\"\n"
            f"- Total images: {num_images}"
        ),
        confidence=0.93,
        metadata={
            "style": image_result.get("style", "photojournalistic"),
            "dimensions": image_result.get("dimensions", "1024x1024"),
            "image_count": num_images,
        },
    ))

    return pipeline.model_dump()


async def _generate_live_image(headline: str, draft) -> dict:
    """Generate hero image + 2 variants using Azure OpenAI gpt-image-1.

    gpt-image-1 returns base64-encoded PNG data (not a URL),
    so we decode it, save to static/images/, and return local URLs.
    All 3 images are generated concurrently for speed.
    """
    import asyncio
    import base64
    import os
    import uuid
    from concurrent.futures import ThreadPoolExecutor
    from openai import AzureOpenAI
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider

    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
    )

    image_endpoint = settings.azure_openai.image_endpoint or settings.azure_openai.endpoint

    client = AzureOpenAI(
        azure_endpoint=image_endpoint,
        azure_ad_token_provider=token_provider,
        api_version=settings.azure_openai.api_version,
    )

    summary = draft.summary if draft else headline

    # 3 distinct prompts — NO people/humans in any image
    prompts = [
        (
            f"Cinematic wide-angle scene photograph for a major news story. "
            f"Story: {summary[:300]}. "
            f"Style: award-winning photojournalism of the SCENE and ENVIRONMENT only, "
            f"dramatic natural lighting, vivid colors, shallow depth of field, "
            f"high dynamic range. Focus on landscapes, buildings, vehicles, "
            f"weather phenomena, or physical aftermath — absolutely NO people, "
            f"no human figures, no silhouettes, no crowds. "
            f"No text overlays. No watermarks."
        ),
        (
            f"Aerial overhead wide-angle photograph related to a news story. "
            f"Story: {summary[:300]}. "
            f"Style: aerial drone photography, wide establishing shot, daytime, "
            f"showing the scale of the event from above — roads, terrain, "
            f"structures, natural features. Absolutely NO people or human "
            f"figures visible. No text overlays. No watermarks."
        ),
        (
            f"Dramatic close-up detail photograph for a news story. "
            f"Story: {summary[:300]}. "
            f"Style: macro/close-up editorial photography capturing a telling "
            f"detail or symbolic object related to the story — damaged materials, "
            f"equipment, signage, nature, textures, documents, debris. "
            f"Shallow depth of field, moody lighting, evocative composition. "
            f"Absolutely NO people, no hands, no human body parts. "
            f"No text overlays. No watermarks."
        ),
    ]
    styles = ["cinematic-scene", "aerial-overview", "detail-closeup"]

    img_dir = os.path.join("static", "images")
    os.makedirs(img_dir, exist_ok=True)

    def _call_api(prompt: str) -> str | None:
        """Synchronous API call — will be run in a thread pool."""
        try:
            resp = client.images.generate(
                model=settings.azure_openai.image_deployment,
                prompt=prompt,
                n=1,
                size="1024x1024",
            )
            item = resp.data[0] if resp.data else None
            if item and item.b64_json:
                img_bytes = base64.b64decode(item.b64_json)
                filename = f"{uuid.uuid4().hex[:12]}.png"
                filepath = os.path.join(img_dir, filename)
                with open(filepath, "wb") as f:
                    f.write(img_bytes)
                logger.info("Saved image: %s (%d KB)", filepath, len(img_bytes) // 1024)
                return f"/static/images/{filename}"
            elif item and item.url:
                return item.url
        except Exception as e:
            logger.warning("Image generation failed for prompt: %s — %s", prompt[:60], e)
        return None

    # Run all 3 generations in parallel threads
    logger.info("Generating 3 images in parallel for: %s", headline[:80])
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [loop.run_in_executor(pool, _call_api, p) for p in prompts]
        results = await asyncio.gather(*futures)

    hero_url = results[0]
    if not hero_url:
        logger.error("Hero image generation failed, falling back to mock")
        return _mock_image(headline, draft)

    additional = []
    for i in (1, 2):
        if results[i]:
            additional.append({
                "url": results[i],
                "alt_text": f"{styles[i].replace('-', ' ').title()} view: {headline[:80]}",
                "style": styles[i],
            })

    return {
        "hero_image_url": hero_url,
        "thumbnail_url": hero_url,
        "alt_text": f"AI-generated news image: {headline[:100]}",
        "prompt_used": prompts[0][:200],
        "style": "cinematic-scene",
        "dimensions": "1024x1024",
        "additional_images": additional,
    }


def _mock_image(headline: str, draft) -> dict:
    """Generate realistic mock image results for demo.
    Uses a hash of the headline to pick different Unsplash images per story.
    """
    # Pool of diverse news-style Unsplash photo IDs
    _hero_pool = [
        "photo-1504711434969-e33886168d9c",   # emergency vehicles scene
        "photo-1495020689067-958852a7765e",   # city skyline dramatic
        "photo-1573164713988-8665fc963095",  # storm / weather
        "photo-1611532736597-de2d4265fba3",  # Capitol building
        "photo-1551135049-8a33b5883817",    # tech / digital
        "photo-1508739773434-c26b3d09e071",  # dramatic sunset landscape
        "photo-1470115636492-6d2b56f9b5d1",  # nature close-up
        "photo-1446776811953-b23d57bd21aa",  # wildfire landscape
        "photo-1527482937786-6c94007b14a3",  # flooded street
        "photo-1505322033502-1f4385692e6a",  # empty stadium
    ]
    _extra_pool = [
        ("photo-1553877522-43269d4ea984", "Aerial view of landscape and infrastructure", "aerial-overview"),
        ("photo-1518709268805-4e9042af9f23", "Close-up of weather-worn surface detail", "detail-closeup"),
        ("photo-1573164713988-8665fc963095", "Dramatic storm clouds over open terrain", "cinematic-scene"),
        ("photo-1559757148-5c350d0d3c56", "Helicopter view of coastal landscape", "aerial-overview"),
        ("photo-1470115636492-6d2b56f9b5d1", "Close-up of tangled debris and wreckage", "detail-closeup"),
        ("photo-1508739773434-c26b3d09e071", "Sunset over empty city skyline", "cinematic-scene"),
    ]

    # Deterministic pick based on headline text
    h = sum(ord(c) for c in headline) if headline else 0
    hero_id = _hero_pool[h % len(_hero_pool)]
    # Pick 2 extras that differ from the hero
    extra_start = (h // len(_hero_pool)) % len(_extra_pool)
    extras = [
        _extra_pool[(extra_start + i) % len(_extra_pool)]
        for i in range(2)
    ]

    base = "https://images.unsplash.com"
    return {
        "hero_image_url": f"{base}/{hero_id}?w=1024&h=1024&fit=crop",
        "thumbnail_url": f"{base}/{hero_id}?w=256&h=256&fit=crop",
        "alt_text": (
            f"Editorial news photograph depicting the developing story: "
            f"{headline[:80]}"
        ),
        "prompt_used": (
            f"Photojournalistic news image for a broadcast story about: "
            f"{headline[:120]}. Style: editorial photography, dramatic lighting."
        ),
        "style": "photojournalistic",
        "dimensions": "1024x1024",
        "additional_images": [
            {"url": f"{base}/{eid}?w=1024&h=1024&fit=crop", "alt_text": alt, "style": sty}
            for eid, alt, sty in extras
        ],
    }

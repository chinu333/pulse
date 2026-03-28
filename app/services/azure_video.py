"""
PULSE - Azure Video Indexer Service
Provides video analysis, scene detection, transcription, and content moderation.
Uses Azure RBAC (DefaultAzureCredential) for ARM-based token auth.
"""

import logging
from typing import Any, Optional

import httpx
from azure.identity import DefaultAzureCredential
from app.config import settings

logger = logging.getLogger("pulse.azure_video")

# Azure Video Indexer ARM scope
_credential = DefaultAzureCredential()
_VI_ARM_SCOPE = "https://management.azure.com/.default"
_VI_API_BASE = "https://api.videoindexer.ai"


async def _get_access_token() -> str:
    """
    Obtain a Video Indexer access token via ARM.
    Uses DefaultAzureCredential to get an ARM token, then exchanges it
    for a Video Indexer account-level access token.
    """
    arm_token = _credential.get_token(_VI_ARM_SCOPE).token
    account_id = settings.azure_video.account_id
    location = settings.azure_video.location
    resource_id = settings.azure_video.resource_id

    url = (
        f"https://management.azure.com{resource_id}"
        f"/generateAccessToken?api-version=2024-01-01"
    )

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url,
            headers={"Authorization": f"Bearer {arm_token}"},
            json={
                "permissionType": "Contributor",
                "scope": "Account",
            },
        )
        resp.raise_for_status()
        return resp.json().get("accessToken", "")


async def upload_video(
    video_bytes: bytes,
    name: str,
    description: str = "",
    language: str = "en-US",
) -> dict:
    """
    Upload a video to Azure Video Indexer for analysis.
    Returns the video ID and indexing status.
    """
    token = await _get_access_token()
    account_id = settings.azure_video.account_id
    location = settings.azure_video.location

    url = (
        f"{_VI_API_BASE}/{location}/Accounts/{account_id}"
        f"/Videos?name={name}&language={language}&accessToken={token}"
    )

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            url,
            content=video_bytes,
            headers={"Content-Type": "multipart/form-data"},
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "video_id": data.get("id", ""),
            "state": data.get("state", ""),
            "name": name,
        }


async def get_video_index(video_id: str) -> dict:
    """
    Get the full index/insights for a processed video.
    Returns scenes, topics, faces, OCR, transcript, etc.
    """
    token = await _get_access_token()
    account_id = settings.azure_video.account_id
    location = settings.azure_video.location

    url = (
        f"{_VI_API_BASE}/{location}/Accounts/{account_id}"
        f"/Videos/{video_id}/Index?accessToken={token}"
    )

    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


async def get_video_summary(video_id: str) -> dict:
    """
    Extract a summarized view of video insights:
    scenes, topics, people, key quotes, and content flags.
    """
    index = await get_video_index(video_id)

    # Extract structured insights
    insights = index.get("videos", [{}])[0].get("insights", {})

    return {
        "duration": index.get("durationInSeconds", 0),
        "topics": [
            {"name": t.get("name", ""), "confidence": t.get("confidence", 0)}
            for t in insights.get("topics", [])
        ],
        "scenes": [
            {
                "id": s.get("id", 0),
                "start": s.get("start", ""),
                "end": s.get("end", ""),
            }
            for s in insights.get("scenes", [])[:10]
        ],
        "faces": [
            {"name": f.get("name", "Unknown"), "appearances": len(f.get("appearances", []))}
            for f in insights.get("faces", [])
        ],
        "ocr_text": [
            o.get("text", "")
            for o in insights.get("ocr", [])
        ],
        "transcript_segments": [
            {
                "text": t.get("text", ""),
                "start": t.get("instances", [{}])[0].get("start", ""),
                "speaker": t.get("speakerId", ""),
                "confidence": t.get("confidence", 0),
            }
            for t in insights.get("transcript", [])[:20]
        ],
        "keywords": [
            k.get("text", "")
            for k in insights.get("keywords", [])
        ],
        "content_moderation": {
            "is_adult": insights.get("visualContentModeration", {}).get("adultScore", 0) > 0.5,
            "is_racy": insights.get("visualContentModeration", {}).get("racyScore", 0) > 0.5,
        },
    }

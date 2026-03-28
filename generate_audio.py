"""Generate a professional news broadcast audio clip using Azure AI Speech REST API."""

import os, httpx
from dotenv import load_dotenv
load_dotenv()

from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()
token = credential.get_token("https://cognitiveservices.azure.com/.default").token

region = os.getenv("AZURE_SPEECH_REGION", "eastus")

# Try to exchange AAD token for a Speech authorization token via STS
sts_url = f"https://{region}.api.cognitive.microsoft.com/sts/v1.0/issueToken"
print(f"Issuing Speech token via: {sts_url}")
sts_resp = httpx.post(sts_url, headers={"Authorization": f"Bearer {token}"}, content=b"", timeout=10)
if sts_resp.status_code == 200:
    speech_token = sts_resp.text
    print(f"Got Speech token ({len(speech_token)} chars)")
else:
    print(f"STS token exchange failed: HTTP {sts_resp.status_code} - {sts_resp.text[:300]}")
    exit(1)

tts_url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"
print(f"TTS endpoint: {tts_url}")

# SSML for a news broadcast reading using Dragon HD Omni (high-definition voice)
ssml = """<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis"
      xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="en-US">
  <voice name="en-us-ava:DragonHDOmniLatestNeural">
        Good evening. <break time="300ms"/>
        A fast-moving wildfire is threatening a suburban community tonight in Southern California,
        forcing thousands of residents to evacuate as flames race across hillsides near populated areas.
        <break time="400ms"/>

        The blaze, which officials are calling the Canyon Ridge Fire, has scorched more than
        three thousand acres since igniting early this afternoon. <break time="300ms"/>
        Fire crews from six counties are now on scene, with more than forty engine companies
        and eight air tankers deployed to battle the flames. <break time="400ms"/>

        CalFire Incident Commander David Reyes spoke to reporters just moments ago.
        <break time="200ms"/>

        Quote: "This fire is moving faster than anything we have seen this season.
        The combination of dry brush, low humidity, and Santa Ana winds has created
        extremely dangerous conditions. We are asking all residents in zones A through D
        to evacuate immediately." <break time="500ms"/>

        Mandatory evacuation orders are in effect for approximately twelve thousand residents.
        <break time="200ms"/>
        Three emergency shelters have been opened at local schools,
        and the Red Cross says they are prepared to house up to two thousand evacuees.
        <break time="300ms"/>

        Governor Newsom has declared a state of emergency for the region,
        unlocking fifteen million dollars in immediate disaster relief funding.
        <break time="300ms"/>

        No fatalities have been reported so far, though at least nine structures
        have been destroyed and dozens more are threatened. <break time="400ms"/>

        We will continue to bring you updates throughout the evening. <break time="200ms"/>
        Reporting live from the Canyon Ridge command post, this is PULSE News.
  </voice>
</speak>"""

headers = {
    "Authorization": f"Bearer {speech_token}",
    "Content-Type": "application/ssml+xml",
    "X-Microsoft-OutputFormat": "audio-16khz-32kbitrate-mono-mp3",
    "User-Agent": "PULSE-TTS/1.0",
}

print("Synthesizing news broadcast audio...")
resp = httpx.post(tts_url, content=ssml.encode("utf-8"), headers=headers, timeout=30)

if resp.status_code == 200:
    os.makedirs("static/audio", exist_ok=True)
    path = "static/audio/sample_news_broadcast.mp3"
    with open(path, "wb") as resp_file:
        resp_file.write(resp.content)
    size_kb = len(resp.content) / 1024
    duration_est = size_kb / 4  # rough: 32kbps mono ~ 4KB/sec
    print(f"Saved: {path} ({size_kb:.0f} KB, ~{duration_est:.0f}s)")
else:
    print(f"FAILED: HTTP {resp.status_code}")
    print(f"Response: {resp.text[:500]}")

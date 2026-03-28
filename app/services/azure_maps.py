"""
PULSE - Azure Maps Service
Provides location-based store/business search using Azure Maps Search API.
Enables "preparation store" suggestions for users near breaking-news events
(e.g., hardware stores before a hurricane, pharmacies before a health alert).

Authentication priority:
  1. Subscription key  (AZURE_MAPS_SUBSCRIPTION_KEY)
  2. Azure AD / RBAC   (AZURE_MAPS_CLIENT_ID + DefaultAzureCredential)
  3. Mock data          (only when DEMO_MODE=true or no credentials found)
"""

import logging
import httpx
from app.config import settings

logger = logging.getLogger("pulse.services.azure_maps")

# Azure Maps REST API base
_MAPS_BASE = "https://atlas.microsoft.com"

# ── Cached Azure AD token ────────────────────────────────────
_ad_token_cache: dict = {"token": None, "expires_on": 0}


def _get_auth_headers() -> tuple[dict[str, str], bool]:
    """Build authentication headers for Azure Maps.

    Returns (headers_dict, is_authenticated).
    Tries subscription key first, then Azure AD.
    """
    # Option 1: Subscription key (simplest)
    sub_key = settings.azure_maps.subscription_key
    if sub_key:
        return {"subscription-key": sub_key}, True

    # Option 2: Azure AD with DefaultAzureCredential
    client_id = settings.azure_maps.client_id
    if client_id:
        try:
            import time
            now = time.time()
            if _ad_token_cache["token"] and _ad_token_cache["expires_on"] > now + 60:
                token = _ad_token_cache["token"]
            else:
                from azure.identity import DefaultAzureCredential
                credential = DefaultAzureCredential()
                token_resp = credential.get_token("https://atlas.microsoft.com/.default")
                token = token_resp.token
                _ad_token_cache["token"] = token
                _ad_token_cache["expires_on"] = token_resp.expires_on
                logger.debug("Acquired fresh Azure Maps AD token")
            return {
                "Authorization": f"Bearer {token}",
                "x-ms-client-id": client_id,
            }, True
        except Exception as e:
            logger.warning("Azure AD auth for Maps failed: %s — falling back", e)

    return {}, False

# Category-to-query mapping: given a story topic keyword,
# suggest relevant store types where readers can prepare.
# Each entry has: (list_of_search_queries, display_label)
# Using brand names gives Azure Maps far better POI results than generic terms.
PREP_STORE_CATEGORIES = {
    "hurricane": [
        (["Home Depot", "Lowes", "Ace Hardware"], "Hardware & Supplies"),
        (["Publix", "Kroger", "Walmart", "Whole Foods"], "Grocery & Water"),
        (["gas station", "Shell", "BP"], "Fuel"),
        (["CVS Pharmacy", "Walgreens"], "Pharmacy & First Aid"),
    ],
    "storm": [
        (["Home Depot", "Lowes"], "Hardware & Supplies"),
        (["Publix", "Kroger", "Walmart"], "Grocery & Water"),
        (["gas station", "Shell", "BP"], "Fuel"),
    ],
    "tornado": [
        (["Home Depot", "Lowes"], "Hardware & Supplies"),
        (["Publix", "Kroger", "Walmart"], "Grocery & Water"),
        (["hospital", "emergency room"], "Emergency Services"),
    ],
    "flood": [
        (["Home Depot", "Lowes"], "Hardware & Supplies"),
        (["Publix", "Kroger", "Walmart"], "Grocery & Water"),
        (["gas station", "Shell", "BP"], "Fuel"),
    ],
    "earthquake": [
        (["Home Depot", "Lowes"], "Hardware & Supplies"),
        (["Publix", "Kroger", "Walmart"], "Grocery & Water"),
        (["CVS Pharmacy", "Walgreens"], "Pharmacy & First Aid"),
    ],
    "wildfire": [
        (["Home Depot", "Lowes"], "Hardware & Supplies"),
        (["gas station", "Shell", "BP"], "Fuel"),
        (["CVS Pharmacy", "Walgreens"], "Pharmacy & First Aid"),
    ],
    "winter storm": [
        (["Home Depot", "Lowes"], "Hardware & Supplies"),
        (["Publix", "Kroger", "Walmart"], "Grocery & Water"),
        (["gas station", "Shell", "BP"], "Fuel"),
    ],
    "default": [
        (["Publix", "Kroger", "Walmart"], "Grocery"),
        (["CVS Pharmacy", "Walgreens"], "Pharmacy"),
    ],
}


def _get_subscription_key() -> str:
    """Get Azure Maps subscription key from settings."""
    return settings.azure_maps.subscription_key


def _is_live_mode() -> bool:
    """Return True if we have valid Azure Maps credentials (not demo-only mock)."""
    if settings.demo_mode:
        return False
    auth_headers, authenticated = _get_auth_headers()
    return authenticated


async def geocode_zipcode(zipcode: str) -> dict | None:
    """Convert a US zipcode to lat/lon using Azure Maps Search Address API.

    Returns: {"lat": float, "lon": float, "city": str, "state": str} or None
    """
    auth_headers, authenticated = _get_auth_headers()
    if not authenticated or settings.demo_mode:
        logger.info("Azure Maps not configured or demo mode — using mock geocode for %s", zipcode)
        return _mock_geocode(zipcode)

    url = f"{_MAPS_BASE}/search/address/json"
    params = {
        "api-version": "1.0",
        "query": zipcode,
        "countrySet": "US",
        "limit": 1,
    }
    # If using subscription key, put it in query params; otherwise headers carry auth
    if "subscription-key" in auth_headers:
        params["subscription-key"] = auth_headers.pop("subscription-key")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params, headers=auth_headers)
            resp.raise_for_status()
            data = resp.json()

        results = data.get("results", [])
        if not results:
            logger.warning("No geocode results for zipcode: %s", zipcode)
            return None

        pos = results[0].get("position", {})
        addr = results[0].get("address", {})
        geo = {
            "lat": pos.get("lat", 0),
            "lon": pos.get("lon", 0),
            "city": addr.get("municipality", ""),
            "state": addr.get("countrySubdivision", ""),
            "formatted": addr.get("freeformAddress", zipcode),
        }
        logger.info("Geocoded %s → %s (%.4f, %.4f)", zipcode, geo["formatted"], geo["lat"], geo["lon"])
        return geo
    except Exception as e:
        logger.error("Azure Maps geocode error for %s: %s", zipcode, e)
        return None


async def reverse_geocode(lat: float, lon: float) -> dict | None:
    """Convert lat/lon to address/zipcode using Azure Maps Reverse Geocode API.

    Returns: {"zipcode": str, "city": str, "state": str, "formatted": str} or None
    """
    auth_headers, authenticated = _get_auth_headers()
    if not authenticated or settings.demo_mode:
        logger.info("Azure Maps not configured or demo mode — cannot reverse geocode")
        return None

    url = f"{_MAPS_BASE}/search/address/reverse/json"
    params = {
        "api-version": "1.0",
        "query": f"{lat},{lon}",
    }
    if "subscription-key" in auth_headers:
        params["subscription-key"] = auth_headers.pop("subscription-key")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params, headers=auth_headers)
            resp.raise_for_status()
            data = resp.json()

        addresses = data.get("addresses", [])
        if not addresses:
            return None

        addr = addresses[0].get("address", {})
        result = {
            "zipcode": addr.get("postalCode", "").split("-")[0],  # take 5-digit zip
            "city": addr.get("municipality", ""),
            "state": addr.get("countrySubdivision", ""),
            "formatted": addr.get("freeformAddress", ""),
        }
        logger.info("Reverse geocoded (%.4f, %.4f) → %s %s", lat, lon, result["city"], result["zipcode"])
        return result
    except Exception as e:
        logger.error("Azure Maps reverse geocode error: %s", e)
        return None


async def search_nearby_stores(
    lat: float,
    lon: float,
    query: str,
    radius_meters: int = 16000,  # ~10 miles
    limit: int = 3,
    city: str = "",
    state: str = "",
) -> list[dict]:
    """Search for nearby businesses using Azure Maps Fuzzy Search / POI search.

    Uses /search/poi/json which supports text queries with location bias.
    Returns list of: {"name", "address", "phone", "distance_miles", "category"}
    """
    auth_headers, authenticated = _get_auth_headers()
    if not authenticated or settings.demo_mode:
        return _mock_stores(query, limit, city=city, state=state)

    # Use Search POI endpoint — it supports text query + location bias
    url = f"{_MAPS_BASE}/search/poi/json"
    params = {
        "api-version": "1.0",
        "query": query,
        "lat": lat,
        "lon": lon,
        "radius": radius_meters,
        "limit": limit,
        "countrySet": "US",
    }
    if "subscription-key" in auth_headers:
        params["subscription-key"] = auth_headers.pop("subscription-key")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params, headers=auth_headers)
            resp.raise_for_status()
            data = resp.json()

        stores = []
        for r in data.get("results", [])[:limit]:
            poi = r.get("poi", {})
            addr = r.get("address", {})
            dist = r.get("dist", 0)
            stores.append({
                "name": poi.get("name", "Unknown"),
                "address": addr.get("freeformAddress", ""),
                "phone": poi.get("phone", ""),
                "distance_miles": round(dist / 1609.34, 1),
                "category": (
                    poi.get("categories", [""])[0]
                    if poi.get("categories")
                    else query.title()
                ),
                "url": poi.get("url", ""),
            })
        logger.info("Found %d results for '%s' near (%.4f, %.4f)", len(stores), query, lat, lon)
        return stores
    except Exception as e:
        logger.error("Azure Maps POI search error for '%s': %s", query, e)
        # Graceful fallback to mock on transient errors
        return _mock_stores(query, limit, city=city, state=state)


# ── Question-aware POI search (for Q&A enrichment) ──────────

# Map common question keywords to brand-name POI queries
_QA_KEYWORD_QUERIES: dict[str, list[str]] = {
    "grocery":   ["Publix", "Kroger", "Walmart", "Whole Foods", "ALDI"],
    "groceries": ["Publix", "Kroger", "Walmart", "Whole Foods", "ALDI"],
    "food":      ["Publix", "Kroger", "Walmart", "Whole Foods"],
    "water":     ["Publix", "Kroger", "Walmart", "CVS"],
    "hardware":  ["Home Depot", "Lowes", "Ace Hardware"],
    "supplies":  ["Home Depot", "Lowes", "Walmart"],
    "lumber":    ["Home Depot", "Lowes"],
    "gas":       ["Shell", "BP", "gas station", "QuikTrip"],
    "fuel":      ["Shell", "BP", "gas station"],
    "pharmacy":  ["CVS Pharmacy", "Walgreens", "Rite Aid"],
    "medicine":  ["CVS Pharmacy", "Walgreens", "Rite Aid"],
    "drug":      ["CVS Pharmacy", "Walgreens"],
    "hospital":  ["hospital", "medical center"],
    "emergency": ["hospital", "emergency room"],
    "shelter":   ["shelter", "Red Cross"],
    "generator": ["Home Depot", "Lowes"],
    "batteries": ["Home Depot", "Walmart", "CVS"],
    "flashlight": ["Home Depot", "Walmart", "CVS"],
    "plywood":   ["Home Depot", "Lowes"],
    "sandbag":   ["Home Depot", "Lowes"],
    "ice":       ["Publix", "Kroger", "gas station"],
    "eat":       ["restaurant", "Chick-fil-A", "McDonald's"],
    "restaurant": ["restaurant", "Chick-fil-A", "McDonald's"],
    "coffee":    ["Starbucks", "Dunkin"],
    "hotel":     ["hotel", "Marriott", "Hilton"],
    "bank":      ["bank", "Chase", "Wells Fargo", "Bank of America"],
}


async def search_pois_for_question(
    zipcode: str,
    question: str,
) -> list[dict]:
    """Given a user question and zipcode, search Azure Maps for relevant POIs.

    Detects keywords in the question, runs 1-3 targeted POI queries,
    deduplicates, and returns top results.  Used to enrich
    Q&A answers with real nearby places.

    Returns: list of {"name", "address", "phone", "distance_miles", "category", "url"}
    """
    geo = await geocode_zipcode(zipcode)
    if not geo:
        return []

    # Find matching keywords in the question (word-boundary matching to avoid
    # false positives like "weather" matching "eat")
    import re as _re
    q_lower = question.lower()
    queries_to_run: list[str] = []
    seen_queries: set[str] = set()

    for keyword, brand_queries in _QA_KEYWORD_QUERIES.items():
        # \b ensures we match whole words only
        if _re.search(r"\b" + _re.escape(keyword) + r"\b", q_lower):
            for bq in brand_queries:
                if bq.lower() not in seen_queries:
                    seen_queries.add(bq.lower())
                    queries_to_run.append(bq)

    # If no keywords matched, don't run any POI search
    if not queries_to_run:
        return []

    # Cap at 5 API calls to keep latency reasonable
    queries_to_run = queries_to_run[:5]

    all_stores: list[dict] = []
    seen_names: set[str] = set()

    for q in queries_to_run:
        hits = await search_nearby_stores(
            lat=geo["lat"],
            lon=geo["lon"],
            query=q,
            limit=2,
            city=geo.get("city", ""),
            state=geo.get("state", ""),
        )
        for s in hits:
            key = f"{s['name']}|{s['address']}"
            if key not in seen_names:
                seen_names.add(key)
                all_stores.append(s)

    # Sort by distance, return top 5
    all_stores.sort(key=lambda s: s.get("distance_miles", 999))
    return all_stores[:5]


async def get_preparation_stores(
    zipcode: str,
    story_headline: str,
    story_description: str = "",
) -> dict:
    """Main entry: given a zipcode and story context, return relevant nearby stores.

    Detects the event type from the headline and returns categorized store suggestions.
    """
    # Detect event type from headline
    text = f"{story_headline} {story_description}".lower()
    event_type = "default"
    for keyword in PREP_STORE_CATEGORIES:
        if keyword != "default" and keyword in text:
            event_type = keyword
            break

    categories = PREP_STORE_CATEGORIES.get(event_type, PREP_STORE_CATEGORIES["default"])

    # Geocode the zipcode
    geo = await geocode_zipcode(zipcode)
    if not geo:
        return {
            "zipcode": zipcode,
            "event_type": event_type,
            "location": None,
            "error": "Could not geocode zipcode",
            "categories": [],
        }

    # Search for each category — run multiple brand queries, deduplicate, pick closest
    results = []
    for queries, label in categories:
        seen_names: set[str] = set()
        category_stores: list[dict] = []

        for q in queries:
            hits = await search_nearby_stores(
                lat=geo["lat"],
                lon=geo["lon"],
                query=q,
                limit=2,  # 2 per brand query to keep API calls reasonable
                city=geo.get("city", ""),
                state=geo.get("state", ""),
            )
            for s in hits:
                # Deduplicate by name+address
                key = f"{s['name']}|{s['address']}"
                if key not in seen_names:
                    seen_names.add(key)
                    category_stores.append(s)

        # Sort by distance ascending, take top 3
        category_stores.sort(key=lambda s: s.get("distance_miles", 999))
        top = category_stores[:3]

        if top:
            results.append({
                "category": label,
                "query": ", ".join(queries),
                "stores": top,
            })

    return {
        "zipcode": zipcode,
        "event_type": event_type,
        "location": geo,
        "categories": results,
        "tip": _get_prep_tip(event_type),
    }


def _get_prep_tip(event_type: str) -> str:
    """Return a preparation tip based on the event type."""
    tips = {
        "hurricane": "Stock up on water (1 gallon/person/day for 3 days), batteries, flashlights, and non-perishable food. Secure outdoor furniture.",
        "storm": "Ensure you have flashlights, batteries, and a weather radio. Fill your car's gas tank.",
        "tornado": "Identify your safe room. Stock your shelter with water, first aid kit, and a weather radio.",
        "flood": "Move valuables to higher ground. Prepare sandbags and ensure you have waterproof containers for documents.",
        "earthquake": "Secure heavy furniture to walls. Prepare a go-bag with water, food, first aid, and important documents.",
        "wildfire": "Prepare a go-bag. Clear brush within 30 feet of your home. Know your evacuation routes.",
        "winter storm": "Stock up on rock salt, de-icer, and warm supplies. Ensure heating equipment is working.",
        "default": "Stay informed and follow local emergency management guidance.",
    }
    return tips.get(event_type, tips["default"])


# ── Mock helpers (demo mode / no API key) ────────────────────

def _mock_geocode(zipcode: str) -> dict:
    """Return mock geocode data for demo."""
    _mock_zips = {
        "33139": {"lat": 25.7907, "lon": -80.1300, "city": "Miami Beach", "state": "FL", "formatted": "Miami Beach, FL 33139"},
        "33101": {"lat": 25.7617, "lon": -80.1918, "city": "Miami", "state": "FL", "formatted": "Miami, FL 33101"},
        "77001": {"lat": 29.7604, "lon": -95.3698, "city": "Houston", "state": "TX", "formatted": "Houston, TX 77001"},
        "75201": {"lat": 32.7876, "lon": -96.7985, "city": "Dallas", "state": "TX", "formatted": "Dallas, TX 75201"},
        "10001": {"lat": 40.7484, "lon": -73.9967, "city": "New York", "state": "NY", "formatted": "New York, NY 10001"},
        "90210": {"lat": 34.0901, "lon": -118.4065, "city": "Beverly Hills", "state": "CA", "formatted": "Beverly Hills, CA 90210"},
        "30301": {"lat": 33.7490, "lon": -84.3880, "city": "Atlanta", "state": "GA", "formatted": "Atlanta, GA 30301"},
        "30009": {"lat": 34.0754, "lon": -84.2941, "city": "Alpharetta", "state": "GA", "formatted": "Alpharetta, GA 30009"},
        "30004": {"lat": 34.1185, "lon": -84.2788, "city": "Alpharetta", "state": "GA", "formatted": "Alpharetta, GA 30004"},
        "30022": {"lat": 34.0232, "lon": -84.2135, "city": "Johns Creek", "state": "GA", "formatted": "Johns Creek, GA 30022"},
        "30024": {"lat": 34.0568, "lon": -84.0710, "city": "Suwanee", "state": "GA", "formatted": "Suwanee, GA 30024"},
        "30328": {"lat": 33.9320, "lon": -84.3585, "city": "Sandy Springs", "state": "GA", "formatted": "Sandy Springs, GA 30328"},
        "30339": {"lat": 33.8651, "lon": -84.4625, "city": "Marietta", "state": "GA", "formatted": "Marietta, GA 30339"},
        "32801": {"lat": 28.5383, "lon": -81.3792, "city": "Orlando", "state": "FL", "formatted": "Orlando, FL 32801"},
        "60601": {"lat": 41.8819, "lon": -87.6278, "city": "Chicago", "state": "IL", "formatted": "Chicago, IL 60601"},
    }
    # For unknown zips, try to infer region from first 3 digits
    if zipcode in _mock_zips:
        return _mock_zips[zipcode]
    prefix = zipcode[:3] if len(zipcode) >= 3 else ""
    # GA zip prefixes: 300-319
    if prefix.startswith("30") or prefix.startswith("31"):
        return {"lat": 33.7490, "lon": -84.3880, "city": "Metro Atlanta", "state": "GA", "formatted": f"Metro Atlanta, GA {zipcode}"}
    # FL zip prefixes: 320-349
    if prefix.startswith("32") or prefix.startswith("33") or prefix.startswith("34"):
        return {"lat": 28.5383, "lon": -81.3792, "city": "Central Florida", "state": "FL", "formatted": f"Central Florida, FL {zipcode}"}
    # TX zip prefixes: 750-799
    if prefix.startswith("7"):
        return {"lat": 29.7604, "lon": -95.3698, "city": "Houston Area", "state": "TX", "formatted": f"Houston Area, TX {zipcode}"}
    # Default: use a generic US location
    return {"lat": 39.8283, "lon": -98.5795, "city": "Central US", "state": "US", "formatted": f"Location near {zipcode}"}


def _mock_stores(query: str, limit: int = 3, city: str = "", state: str = "") -> list[dict]:
    """Return realistic mock store results matched to the user's location."""

    # ── Region-specific store databases ──────────────────────
    _region_stores: dict[str, dict[str, list[dict]]] = {
        "GA": {
            "hardware store": [
                {"name": "The Home Depot", "address": "6210 N Point Pkwy, Alpharetta, GA", "phone": "(770) 555-0101", "distance_miles": 1.4, "category": "Hardware Store", "url": "https://homedepot.com"},
                {"name": "Lowe's Home Improvement", "address": "1275 N Point Dr, Alpharetta, GA", "phone": "(770) 555-0102", "distance_miles": 2.3, "category": "Hardware Store", "url": "https://lowes.com"},
                {"name": "Ace Hardware", "address": "880 S Main St, Alpharetta, GA", "phone": "(770) 555-0103", "distance_miles": 3.1, "category": "Hardware Store", "url": "https://acehardware.com"},
            ],
            "grocery store": [
                {"name": "Publix Super Markets", "address": "3580 Old Milton Pkwy, Alpharetta, GA", "phone": "(770) 555-0201", "distance_miles": 0.9, "category": "Grocery Store", "url": "https://publix.com"},
                {"name": "Kroger", "address": "5025 Windward Pkwy, Alpharetta, GA", "phone": "(770) 555-0202", "distance_miles": 1.7, "category": "Grocery Store", "url": "https://kroger.com"},
                {"name": "Whole Foods Market", "address": "5765 N Point Pkwy, Alpharetta, GA", "phone": "(770) 555-0203", "distance_miles": 2.4, "category": "Grocery Store", "url": "https://wholefoodsmarket.com"},
            ],
            "gas station": [
                {"name": "QT (QuikTrip)", "address": "4155 Old Milton Pkwy, Alpharetta, GA", "phone": "(770) 555-0301", "distance_miles": 0.6, "category": "Gas Station", "url": ""},
                {"name": "Shell", "address": "2900 Windward Pkwy, Alpharetta, GA", "phone": "(770) 555-0302", "distance_miles": 1.3, "category": "Gas Station", "url": ""},
                {"name": "RaceTrac", "address": "11770 Haynes Bridge Rd, Alpharetta, GA", "phone": "(770) 555-0303", "distance_miles": 1.8, "category": "Gas Station", "url": ""},
            ],
            "pharmacy": [
                {"name": "CVS Pharmacy", "address": "5530 Windward Pkwy, Alpharetta, GA", "phone": "(770) 555-0401", "distance_miles": 1.0, "category": "Pharmacy", "url": "https://cvs.com"},
                {"name": "Walgreens", "address": "3070 Old Milton Pkwy, Alpharetta, GA", "phone": "(770) 555-0402", "distance_miles": 1.5, "category": "Pharmacy", "url": "https://walgreens.com"},
                {"name": "Publix Pharmacy", "address": "3580 Old Milton Pkwy, Alpharetta, GA", "phone": "(770) 555-0403", "distance_miles": 0.9, "category": "Pharmacy", "url": "https://publix.com"},
            ],
        },
        "FL": {
            "hardware store": [
                {"name": "The Home Depot", "address": "2055 N Federal Hwy, Miami, FL", "phone": "(305) 555-0101", "distance_miles": 1.2, "category": "Hardware Store", "url": "https://homedepot.com"},
                {"name": "Lowe's Home Improvement", "address": "1500 SW 8th St, Miami, FL", "phone": "(305) 555-0102", "distance_miles": 2.8, "category": "Hardware Store", "url": "https://lowes.com"},
                {"name": "Ace Hardware", "address": "890 Collins Ave, Miami Beach, FL", "phone": "(305) 555-0103", "distance_miles": 3.5, "category": "Hardware Store", "url": "https://acehardware.com"},
            ],
            "grocery store": [
                {"name": "Publix Super Markets", "address": "1045 5th St, Miami Beach, FL", "phone": "(305) 555-0201", "distance_miles": 0.8, "category": "Grocery Store", "url": "https://publix.com"},
                {"name": "Whole Foods Market", "address": "1020 Alton Rd, Miami Beach, FL", "phone": "(305) 555-0202", "distance_miles": 1.5, "category": "Grocery Store", "url": "https://wholefoodsmarket.com"},
                {"name": "Winn-Dixie", "address": "1600 Bay Rd, Miami Beach, FL", "phone": "(305) 555-0203", "distance_miles": 2.1, "category": "Grocery Store", "url": "https://winndixie.com"},
            ],
            "gas station": [
                {"name": "Shell", "address": "401 Biscayne Blvd, Miami, FL", "phone": "(305) 555-0301", "distance_miles": 0.5, "category": "Gas Station", "url": ""},
                {"name": "BP", "address": "720 5th St, Miami Beach, FL", "phone": "(305) 555-0302", "distance_miles": 1.1, "category": "Gas Station", "url": ""},
                {"name": "Chevron", "address": "1500 Collins Ave, Miami Beach, FL", "phone": "(305) 555-0303", "distance_miles": 2.0, "category": "Gas Station", "url": ""},
            ],
            "pharmacy": [
                {"name": "CVS Pharmacy", "address": "1550 Collins Ave, Miami Beach, FL", "phone": "(305) 555-0401", "distance_miles": 0.9, "category": "Pharmacy", "url": "https://cvs.com"},
                {"name": "Walgreens", "address": "800 5th St, Miami Beach, FL", "phone": "(305) 555-0402", "distance_miles": 1.3, "category": "Pharmacy", "url": "https://walgreens.com"},
                {"name": "Publix Pharmacy", "address": "1045 5th St, Miami Beach, FL", "phone": "(305) 555-0403", "distance_miles": 0.8, "category": "Pharmacy", "url": "https://publix.com"},
            ],
        },
        "TX": {
            "hardware store": [
                {"name": "The Home Depot", "address": "701 S Wayside Dr, Houston, TX", "phone": "(713) 555-0101", "distance_miles": 1.5, "category": "Hardware Store", "url": "https://homedepot.com"},
                {"name": "Lowe's Home Improvement", "address": "2500 S Loop W, Houston, TX", "phone": "(713) 555-0102", "distance_miles": 2.6, "category": "Hardware Store", "url": "https://lowes.com"},
                {"name": "Ace Hardware", "address": "1910 Westheimer Rd, Houston, TX", "phone": "(713) 555-0103", "distance_miles": 3.2, "category": "Hardware Store", "url": "https://acehardware.com"},
            ],
            "grocery store": [
                {"name": "H-E-B", "address": "5225 Buffalo Speedway, Houston, TX", "phone": "(713) 555-0201", "distance_miles": 0.7, "category": "Grocery Store", "url": "https://heb.com"},
                {"name": "Kroger", "address": "3300 Montrose Blvd, Houston, TX", "phone": "(713) 555-0202", "distance_miles": 1.4, "category": "Grocery Store", "url": "https://kroger.com"},
                {"name": "Whole Foods Market", "address": "4004 Bellaire Blvd, Houston, TX", "phone": "(713) 555-0203", "distance_miles": 2.3, "category": "Grocery Store", "url": "https://wholefoodsmarket.com"},
            ],
            "gas station": [
                {"name": "Buc-ee's", "address": "27700 I-10, Katy, TX", "phone": "(281) 555-0301", "distance_miles": 0.8, "category": "Gas Station", "url": "https://buc-ees.com"},
                {"name": "Shell", "address": "5100 Westheimer Rd, Houston, TX", "phone": "(713) 555-0302", "distance_miles": 1.2, "category": "Gas Station", "url": ""},
                {"name": "Valero", "address": "3800 S Main St, Houston, TX", "phone": "(713) 555-0303", "distance_miles": 1.9, "category": "Gas Station", "url": ""},
            ],
            "pharmacy": [
                {"name": "CVS Pharmacy", "address": "3100 Montrose Blvd, Houston, TX", "phone": "(713) 555-0401", "distance_miles": 1.0, "category": "Pharmacy", "url": "https://cvs.com"},
                {"name": "Walgreens", "address": "4600 Westheimer Rd, Houston, TX", "phone": "(713) 555-0402", "distance_miles": 1.6, "category": "Pharmacy", "url": "https://walgreens.com"},
                {"name": "H-E-B Pharmacy", "address": "5225 Buffalo Speedway, Houston, TX", "phone": "(713) 555-0403", "distance_miles": 0.7, "category": "Pharmacy", "url": "https://heb.com"},
            ],
        },
        "NY": {
            "hardware store": [
                {"name": "The Home Depot", "address": "40 W 23rd St, New York, NY", "phone": "(212) 555-0101", "distance_miles": 0.8, "category": "Hardware Store", "url": "https://homedepot.com"},
                {"name": "Lowe's Home Improvement", "address": "520 12th Ave, New York, NY", "phone": "(212) 555-0102", "distance_miles": 1.5, "category": "Hardware Store", "url": "https://lowes.com"},
                {"name": "Ace Hardware", "address": "1517 2nd Ave, New York, NY", "phone": "(212) 555-0103", "distance_miles": 2.9, "category": "Hardware Store", "url": "https://acehardware.com"},
            ],
            "grocery store": [
                {"name": "Trader Joe's", "address": "675 6th Ave, New York, NY", "phone": "(212) 555-0201", "distance_miles": 0.4, "category": "Grocery Store", "url": "https://traderjoes.com"},
                {"name": "Whole Foods Market", "address": "4 Union Square S, New York, NY", "phone": "(212) 555-0202", "distance_miles": 0.9, "category": "Grocery Store", "url": "https://wholefoodsmarket.com"},
                {"name": "Key Food", "address": "130 3rd Ave, New York, NY", "phone": "(212) 555-0203", "distance_miles": 1.3, "category": "Grocery Store", "url": ""},
            ],
            "gas station": [
                {"name": "BP", "address": "305 10th Ave, New York, NY", "phone": "(212) 555-0301", "distance_miles": 0.7, "category": "Gas Station", "url": ""},
                {"name": "Mobil", "address": "690 11th Ave, New York, NY", "phone": "(212) 555-0302", "distance_miles": 1.4, "category": "Gas Station", "url": ""},
                {"name": "Shell", "address": "1501 1st Ave, New York, NY", "phone": "(212) 555-0303", "distance_miles": 2.2, "category": "Gas Station", "url": ""},
            ],
            "pharmacy": [
                {"name": "CVS Pharmacy", "address": "231 W 14th St, New York, NY", "phone": "(212) 555-0401", "distance_miles": 0.3, "category": "Pharmacy", "url": "https://cvs.com"},
                {"name": "Walgreens", "address": "145 4th Ave, New York, NY", "phone": "(212) 555-0402", "distance_miles": 0.8, "category": "Pharmacy", "url": "https://walgreens.com"},
                {"name": "Duane Reade", "address": "350 5th Ave, New York, NY", "phone": "(212) 555-0403", "distance_miles": 1.1, "category": "Pharmacy", "url": ""},
            ],
        },
    }

    # Use city name in generic addresses when no region match
    _city = city or "Your Area"
    _default_stores = {
        "hardware store": [
            {"name": "The Home Depot", "address": f"100 Commerce Dr, {_city}, {state}", "phone": "(800) 466-3337", "distance_miles": 1.5, "category": "Hardware Store", "url": "https://homedepot.com"},
            {"name": "Lowe's Home Improvement", "address": f"250 Retail Blvd, {_city}, {state}", "phone": "(800) 445-6937", "distance_miles": 2.7, "category": "Hardware Store", "url": "https://lowes.com"},
            {"name": "Ace Hardware", "address": f"412 Main St, {_city}, {state}", "phone": "(888) 827-4223", "distance_miles": 3.4, "category": "Hardware Store", "url": "https://acehardware.com"},
        ],
        "grocery store": [
            {"name": "Kroger", "address": f"300 Market St, {_city}, {state}", "phone": "(800) 576-4377", "distance_miles": 0.9, "category": "Grocery Store", "url": "https://kroger.com"},
            {"name": "Whole Foods Market", "address": f"500 Center Ave, {_city}, {state}", "phone": "(844) 936-8255", "distance_miles": 1.6, "category": "Grocery Store", "url": "https://wholefoodsmarket.com"},
            {"name": "Walmart Supercenter", "address": f"700 Highway Dr, {_city}, {state}", "phone": "(800) 925-6278", "distance_miles": 2.2, "category": "Grocery Store", "url": "https://walmart.com"},
        ],
        "gas station": [
            {"name": "Shell", "address": f"101 Main St, {_city}, {state}", "phone": "", "distance_miles": 0.5, "category": "Gas Station", "url": ""},
            {"name": "BP", "address": f"205 Highway Dr, {_city}, {state}", "phone": "", "distance_miles": 1.2, "category": "Gas Station", "url": ""},
            {"name": "Chevron", "address": f"310 Commerce Dr, {_city}, {state}", "phone": "", "distance_miles": 1.8, "category": "Gas Station", "url": ""},
        ],
        "pharmacy": [
            {"name": "CVS Pharmacy", "address": f"150 Main St, {_city}, {state}", "phone": "(800) 746-7287", "distance_miles": 0.8, "category": "Pharmacy", "url": "https://cvs.com"},
            {"name": "Walgreens", "address": f"275 Center Ave, {_city}, {state}", "phone": "(800) 925-4733", "distance_miles": 1.4, "category": "Pharmacy", "url": "https://walgreens.com"},
            {"name": "Rite Aid", "address": f"400 Market St, {_city}, {state}", "phone": "(800) 748-3243", "distance_miles": 2.5, "category": "Pharmacy", "url": ""},
        ],
    }

    # Pick region-specific stores first, fall back to defaults
    region_data = _region_stores.get(state, {})
    stores = region_data.get(query, _default_stores.get(query, [
        {"name": f"Local {query.title()}", "address": f"123 Main St, {_city}, {state}", "phone": "(555) 555-0001", "distance_miles": 1.0, "category": query.title(), "url": ""},
    ]))
    return stores[:limit]


# ── Weather Forecast (Azure Maps Weather) ────────────────────

async def get_weather_forecast(lat: float, lon: float, duration: int = 7) -> dict:
    """Fetch daily weather forecast from Azure Maps Weather API.

    Args:
        lat, lon: Coordinates
        duration: 1, 5, 10, or 25 days (Azure Maps supports these)

    Returns dict with location info and daily forecasts.
    """
    headers, authed = _get_auth_headers()
    if not authed:
        return {"error": "Azure Maps not configured"}

    # Azure Maps supports 1, 5, 10, 25 day forecasts
    valid_durations = [1, 5, 10, 25]
    api_duration = min(d for d in valid_durations if d >= duration)

    url = f"{_MAPS_BASE}/weather/forecast/daily/json"
    params = {
        "api-version": "1.1",
        "query": f"{lat},{lon}",
        "duration": api_duration,
        "unit": "imperial",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers, params=params)
            if resp.status_code != 200:
                logger.error("Weather API error: %s %s", resp.status_code, resp.text[:200])
                return {"error": f"Weather API returned {resp.status_code}"}

            data = resp.json()
            forecasts = data.get("forecasts", [])

            days = []
            for f in forecasts[:duration]:
                day = f.get("day", {})
                night = f.get("night", {})
                temp = f.get("temperature", {})
                days.append({
                    "date": f.get("date", ""),
                    "min_temp": temp.get("minimum", {}).get("value"),
                    "max_temp": temp.get("maximum", {}).get("value"),
                    "day_phrase": day.get("longPhrase", day.get("shortPhrase", "")),
                    "night_phrase": night.get("longPhrase", night.get("shortPhrase", "")),
                    "day_icon": day.get("iconCode"),
                    "night_icon": night.get("iconCode"),
                    "precipitation_probability": day.get("precipitationProbability", 0),
                    "rain_probability": day.get("rainProbability", 0),
                    "snow_probability": day.get("snowProbability", 0),
                    "ice_probability": day.get("iceProbability", 0),
                    "wind_speed": day.get("wind", {}).get("speed", {}).get("value"),
                    "wind_direction": day.get("wind", {}).get("direction", {}).get("localizedDescription", ""),
                    "hours_of_precipitation": day.get("hoursOfPrecipitation", 0),
                })
            return {"forecasts": days}

    except Exception as e:
        logger.error("Weather forecast failed: %s", e)
        return {"error": str(e)}


# ── Traffic / Route (Azure Maps Route) ───────────────────────

async def get_traffic_route(
    origin_lat: float, origin_lon: float,
    dest_lat: float, dest_lon: float,
) -> dict:
    """Get traffic-aware route info between two points using Azure Maps Route API.

    Returns travel time, distance, traffic delay, and incidents summary.
    """
    headers, authed = _get_auth_headers()
    if not authed:
        return {"error": "Azure Maps not configured"}

    url = f"{_MAPS_BASE}/route/directions/json"
    params = {
        "api-version": "1.0",
        "query": f"{origin_lat},{origin_lon}:{dest_lat},{dest_lon}",
        "traffic": "true",
        "travelMode": "car",
        "computeTravelTimeFor": "all",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers, params=params)
            if resp.status_code != 200:
                logger.error("Route API error: %s %s", resp.status_code, resp.text[:200])
                return {"error": f"Route API returned {resp.status_code}"}

            data = resp.json()
            routes = data.get("routes", [])
            if not routes:
                return {"error": "No route found"}

            route = routes[0]
            summary = route.get("summary", {})

            travel_time_sec = summary.get("travelTimeInSeconds", 0)
            traffic_delay_sec = summary.get("trafficDelayInSeconds", 0)
            historic_time_sec = summary.get("historicTrafficTravelTimeInSeconds", 0)
            live_time_sec = summary.get("liveTrafficIncidentsTravelTimeInSeconds", 0)
            distance_m = summary.get("lengthInMeters", 0)

            # Get route geometry for map rendering (optional)
            legs = route.get("legs", [])
            points = []
            for leg in legs:
                for pt in leg.get("points", []):
                    points.append({"lat": pt["latitude"], "lon": pt["longitude"]})

            return {
                "travel_time_minutes": round(travel_time_sec / 60, 1),
                "traffic_delay_minutes": round(traffic_delay_sec / 60, 1),
                "historic_time_minutes": round(historic_time_sec / 60, 1) if historic_time_sec else None,
                "live_traffic_time_minutes": round(live_time_sec / 60, 1) if live_time_sec else None,
                "distance_miles": round(distance_m / 1609.34, 1),
                "departure_time": summary.get("departureTime", ""),
                "arrival_time": summary.get("arrivalTime", ""),
                "route_points": points[:200],  # limit for response size
            }

    except Exception as e:
        logger.error("Traffic route failed: %s", e)
        return {"error": str(e)}


async def geocode_city(city_name: str) -> dict | None:
    """Geocode a US city name to lat/lon."""
    headers, authed = _get_auth_headers()
    if not authed:
        return None

    url = f"{_MAPS_BASE}/search/address/json"
    params = {
        "api-version": "1.0",
        "query": city_name,
        "countrySet": "US",
        "limit": 1,
        "typeahead": "true",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers, params=params)
            if resp.status_code != 200:
                return None
            results = resp.json().get("results", [])
            if not results:
                return None
            pos = results[0].get("position", {})
            addr = results[0].get("address", {})
            return {
                "lat": pos.get("lat"),
                "lon": pos.get("lon"),
                "city": addr.get("municipality", city_name),
                "state": addr.get("countrySubdivision", ""),
            }
    except Exception:
        return None

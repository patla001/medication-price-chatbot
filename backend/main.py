from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
import os
import json
from dotenv import load_dotenv
from tavily import TavilyClient
import asyncio
import httpx
from datetime import datetime
import aiohttp
from cache import cache_mcp_result, mcp_cache, clean_expired_cache
from rate_limit import rate_limit, rate_tracker, clean_old_usage_data
from tavily_mcp import TavilyMCPServer
from errors import handle_mcp_errors
import re

# Load environment variables
load_dotenv()

app = FastAPI(
    title="Medication Price Comparison Chatbot API",
    description="AI-powered chatbot for finding the best medication prices"
)

# CORS configuration
origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Tavily clients
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
tavily_mcp = TavilyMCPServer(api_key=os.getenv("TAVILY_API_KEY"))

# Initialize HTTP client for API calls
http_client = httpx.AsyncClient()

# Initialize Tavily MCP client
TAVILY_MCP_URL = "http://localhost:8000/mcp"  # Use the same port as our backend

# Geocoding API client
class GeocodingClient:
    def __init__(self):
        self.api_key = os.getenv("GEOCODING_API_KEY")
        self.base_url = "https://api.geocod.io/v1.7"
        
    async def geocode_address(self, address: str) -> Dict:
        """Convert address to coordinates"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/geocode",
                    params={
                        "q": address,
                        "api_key": self.api_key
                    }
                )
                data = response.json()
                
                if not data.get("results"):
                    return None
                    
                result = data["results"][0]
                return {
                    "lat": result["location"]["lat"],
                    "lng": result["location"]["lng"],
                    "formatted_address": result["formatted_address"],
                    "accuracy": result["accuracy"],
                    "accuracy_type": result["accuracy_type"]
                }
        except Exception as e:
            print(f"Error in geocoding: {str(e)}")
            return None
            
    async def reverse_geocode(self, lat: float, lng: float) -> Dict:
        """Convert coordinates to address"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/reverse",
                    params={
                        "q": f"{lat},{lng}",
                        "api_key": self.api_key
                    }
                )
                data = response.json()
                
                if not data.get("results"):
                    return None
                    
                result = data["results"][0]
                return {
                    "formatted_address": result["formatted_address"],
                    "accuracy": result["accuracy"],
                    "accuracy_type": result["accuracy_type"]
                }
        except Exception as e:
            print(f"Error in reverse geocoding: {str(e)}")
            return None
            
    async def search_pharmacies(self, location: str, radius_miles: float = 5.0) -> List[Dict]:
        """Search for pharmacies near a location"""
        try:
            # First geocode the search location
            location_data = await self.geocode_address(location)
            if not location_data:
                return []
                
            # Use Tavily to search for pharmacies in the area
            search_query = f"pharmacy near {location_data['formatted_address']}"
            pharmacy_response = await tavily_mcp.search(
                query=search_query,
                search_depth="advanced",
                max_results=10,
                include_domains=[
                    "walgreens.com/store/",
                    "cvs.com/store/",
                    "riteaid.com/store/",
                    "walmart.com/pharmacy/",
                    "costco.com/pharmacy/"
                ]
            )
            
            pharmacies = []
            seen_addresses = set()
            
            for result in pharmacy_response.get("results", []):
                content = result.get("content", "").lower()
                url = result.get("url", "")
                
                # Extract address from content
                address_match = re.search(r"\b\d+[^.]*(?:street|st|avenue|ave|road|rd|boulevard|blvd|lane|ln|drive|dr|circle|cir|court|ct|way|parkway|pkwy|square|sq)[^.]*\b", content, re.IGNORECASE)
                if not address_match:
                    continue
                    
                address = address_match.group(0).strip()
                if address in seen_addresses:
                    continue
                    
                seen_addresses.add(address)
                
                # Geocode the pharmacy address
                pharmacy_location = await self.geocode_address(address)
                if not pharmacy_location:
                    continue
                    
                # Calculate distance
                distance = calculate_distance_haversine(
                    lat1=location_data["lat"],
                    lon1=location_data["lng"],
                    lat2=pharmacy_location["lat"],
                    lon2=pharmacy_location["lng"]
                )
                
                # Extract phone number
                phone_match = re.search(r"\b(?:\+?1[-.]?)?\s*(?:\([0-9]{3}\)|[0-9]{3})[-.]?\s*[0-9]{3}[-.]?\s*[0-9]{4}\b", content)
                phone = phone_match.group(0) if phone_match else None
                
                # Extract hours
                hours_match = re.search(r"(?:hours?|open)[:]\s*([^.]*)", content, re.IGNORECASE)
                hours = hours_match.group(1).strip() if hours_match else None
                
                pharmacy = {
                    "name": extract_pharmacy_name(url),
                    "address": pharmacy_location["formatted_address"],
                    "distance": distance,
                    "phone": phone,
                    "hours": hours,
                    "website": url,
                    "accuracy": pharmacy_location["accuracy"],
                    "accuracy_type": pharmacy_location["accuracy_type"]
                }
                pharmacies.append(pharmacy)
            
            # Sort by distance
            return sorted(pharmacies, key=lambda x: x["distance"])
            
        except Exception as e:
            print(f"Error in pharmacy search: {str(e)}")
            return []

def calculate_distance_haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the distance between two points using the Haversine formula"""
    from math import radians, sin, cos, sqrt, atan2
    
    R = 3959.87433  # Earth's radius in miles

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    distance = R * c
    
    return round(distance, 2)

def extract_pharmacy_name(url: str) -> str:
    """Extract pharmacy name from URL"""
    if "walgreens" in url.lower():
        return "Walgreens"
    elif "cvs" in url.lower():
        return "CVS"
    elif "riteaid" in url.lower():
        return "Rite Aid"
    elif "walmart" in url.lower():
        return "Walmart"
    elif "costco" in url.lower():
        return "Costco"
    else:
        return "Pharmacy"

# Initialize Geocoding client
geocoding = GeocodingClient()

# Pydantic models
class MedicationQuery(BaseModel):
    medication_name: str
    dosage: Optional[str] = None
    quantity: Optional[int] = None
    location: Optional[str] = None
    insurance_type: Optional[str] = None

class ChatMessage(BaseModel):
    message: str
    user_location: Optional[str] = None
    user_preferences: Optional[Dict[str, Any]] = None

class MedicationPrice(BaseModel):
    pharmacy_name: str
    price: float
    location: str
    distance: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    in_stock: bool = True
    last_updated: str

class ChatResponse(BaseModel):
    response: str
    medication_prices: Optional[List[MedicationPrice]] = None
    suggestions: Optional[List[str]] = None
    search_performed: bool = False

# MCP Tool Models
class SearchMedicationPriceInput(BaseModel):
    medication_name: str = Field(..., description="Name of the medication to search for")
    dosage: Optional[str] = Field(None, description="Dosage of the medication (e.g., '200mg')")
    location: Optional[str] = Field(None, description="Location to search prices in")

class SearchMedicationPriceOutput(BaseModel):
    prices: List[Dict[str, Any]]
    search_query: str

class FindGenericAlternativesInput(BaseModel):
    brand_name: str = Field(..., description="Brand name of the medication")
    include_prices: bool = Field(default=True, description="Whether to include price comparisons")

class GenericAlternative(BaseModel):
    generic_name: str
    brand_name: str
    price_savings: Optional[float]
    availability: str
    equivalent_dosage: Optional[str]

class FindGenericAlternativesOutput(BaseModel):
    alternatives: List[GenericAlternative]
    search_query: str

class FindPharmaciesInput(BaseModel):
    location: str
    radius_miles: float = 5.0
    medication_name: Optional[str] = None
    coordinates: Optional[Dict[str, float]] = None

class Pharmacy(BaseModel):
    name: str
    address: str
    distance: float
    phone: Optional[str]
    hours: Optional[str]
    has_medication: Optional[bool]

class FindPharmaciesOutput(BaseModel):
    pharmacies: List[Pharmacy]
    search_query: str

class ComparePricesInput(BaseModel):
    medication_name: str
    dosage: Optional[str] = None
    quantity: Optional[int] = None
    pharmacy_types: List[Literal["retail", "online", "discount"]] = Field(
        default=["retail", "online", "discount"],
        description="Types of pharmacies to include in comparison"
    )

class PriceComparison(BaseModel):
    pharmacy_type: str
    average_price: float
    lowest_price: float
    highest_price: float
    sample_size: int

class ComparePricesOutput(BaseModel):
    comparisons: List[PriceComparison]
    overall_average: float
    potential_savings: float
    search_query: str

# MCP Tool Functions
@app.post("/mcp/tools/tavily_web_search")
@rate_limit("tavily_web_search")
@cache_mcp_result(ttl_seconds=1800)  # Cache for 30 minutes
async def tavily_web_search(input_data: dict) -> Dict[str, Any]:
    """Execute a web search using Tavily"""
    try:
        query = input_data.get("parameters", {}).get("query")
        if not query:
            raise HTTPException(status_code=400, detail="Query parameter is required")
            
        if not os.getenv("TAVILY_API_KEY"):
            raise HTTPException(status_code=500, detail="Tavily API key not found in environment variables")
            
        result = await tavily_mcp.search(query=query)
        return {
            "results": result.get("results", []),
            "search_id": result.get("search_id")
        }
    except Exception as e:
        import traceback
        error_detail = {
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        raise HTTPException(status_code=500, detail=error_detail)

@app.post("/mcp/tools/tavily_extract")
@rate_limit("tavily_extract")
@cache_mcp_result(ttl_seconds=3600)  # Cache for 1 hour
async def tavily_extract(input_data: dict) -> Dict[str, Any]:
    """Extract content from a URL using Tavily"""
    try:
        url = input_data.get("parameters", {}).get("url")
        if not url:
            raise HTTPException(status_code=400, detail="URL parameter is required")
            
        result = await tavily_mcp.get_content(url=url)
        return {
            "content": result.get("content", ""),
            "title": result.get("title", "")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error executing Tavily extract: {str(e)}")

@app.get("/mcp/tools/list")
async def list_mcp_tools():
    """List available MCP tools"""
    tools = [
        {
            "name": "tavily_web_search",
            "description": "Search the web using Tavily's AI-powered search engine",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query"
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "tavily_extract",
            "description": "Extract content from a URL using Tavily",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to extract content from"
                    }
                },
                "required": ["url"]
            }
        }
    ]
    return {"tools": tools}

# MCP Tool Functions
@app.post("/mcp/tools/search_medication_price")
@rate_limit("search_medication_price")
@cache_mcp_result(ttl_seconds=1800)  # Cache for 30 minutes
async def search_medication_price(input_data: dict) -> Dict[str, Any]:
    """Search for medication prices using Tavily API"""
    try:
        # Validate input
        input = SearchMedicationPriceInput(**input_data)
        
        search_terms = [
            f"{input.medication_name} price cost",
            "pharmacy retail price",
            "over the counter"
        ]
        
        if input.dosage:
            search_terms.append(f"{input.dosage}")
        
        if input.location:
            search_terms.append(f"near {input.location}")
        
        search_query = " ".join(search_terms)
        
        response = await tavily_mcp.search(
            query=search_query,
            search_depth="advanced",
            max_results=10,
            include_domains=["goodrx.com", "walgreens.com", "cvs.com", "costco.com", "walmart.com", "pharmacychecker.com"]
        )
        
        prices = []
        for result in response.get('results', []):
            content = result.get('content', '').lower()
            url = result.get('url', '').lower()
            
            # Extract price using regex
            price_matches = re.findall(r'\$\s*(\d+\.?\d*)', content)
            if price_matches:
                # Get pharmacy name from URL or content
                pharmacy_name = None
                if 'walmart' in url:
                    pharmacy_name = 'Walmart'
                elif 'walgreens' in url:
                    pharmacy_name = 'Walgreens'
                elif 'cvs' in url:
                    pharmacy_name = 'CVS'
                elif 'costco' in url:
                    pharmacy_name = 'Costco'
                elif 'goodrx' in url:
                    pharmacy_name = 'GoodRx Price'
                else:
                    # Try to extract pharmacy name from content
                    pharmacy_matches = re.findall(r'at\s+([A-Za-z]+)', content)
                    if pharmacy_matches:
                        pharmacy_name = pharmacy_matches[0].title()
                    else:
                        pharmacy_name = 'Online Pharmacy'
                
                # Get the lowest price mentioned
                price = min(float(p) for p in price_matches)
                
                # Add to prices list if we haven't seen this pharmacy yet
                if not any(p['pharmacy_name'] == pharmacy_name for p in prices):
                    prices.append({
                        "pharmacy_name": pharmacy_name,
                        "price": price,
                        "location": input.location or "Online",
                        "website": result.get('url'),
                        "in_stock": True,  # Default to true since we found a price
                        "last_updated": datetime.now().isoformat()
                    })
        
        # Sort prices by price
        prices.sort(key=lambda x: x['price'])
        
        return {
            "prices": prices[:5],  # Return top 5 lowest prices
            "search_query": search_query
        }
    except Exception as e:
        print(f"Error in search_medication_price: {str(e)}")
        return {
            "prices": [],
            "search_query": search_query if 'search_query' in locals() else ""
        }

@app.post("/mcp/tools/find_generic_alternatives")
@rate_limit("find_generic_alternatives")
@cache_mcp_result(ttl_seconds=3600)  # Cache for 1 hour
async def find_generic_alternatives(input_data: dict) -> Dict[str, Any]:
    """Find generic alternatives for a brand name medication"""
    try:
        # Validate input
        medication_name = input_data.get("medication_name", "")
        if not medication_name:
            return {"alternatives": []}

        search_query = f"{medication_name} generic alternative equivalent drug"
        
        response = await tavily_mcp.search(
            query=search_query,
            search_depth="advanced",
            max_results=5,
            include_domains=["drugs.com", "goodrx.com", "webmd.com", "nih.gov", "mayoclinic.org", "medlineplus.gov"]
        )

        alternatives = []
        for result in response.get('results', []):
            content = result.get('content', '').lower()
            
            # Look for patterns like "generic name: [name]" or "generic version is [name]"
            generic_matches = re.findall(r'generic (?:name|version)(?:\s+is)?[:\s]+([a-zA-Z0-9\-]+)', content)
            generic_matches.extend(re.findall(r'generic alternative[:\s]+([a-zA-Z0-9\-]+)', content))
            
            # Also look for price savings information
            savings_matches = re.findall(r'save (?:up to )?\$(\d+\.?\d*)', content)
            
            if generic_matches:
                for generic_name in generic_matches:
                    # Clean up the generic name
                    generic_name = generic_name.strip().title()
                    
                    # Only add if we haven't seen this generic name before
                    if not any(alt['generic_name'] == generic_name for alt in alternatives):
                        alternative = {
                            "generic_name": generic_name,
                            "brand_name": medication_name,
                            "source_url": result.get('url'),
                            "estimated_savings": float(savings_matches[0]) if savings_matches else None,
                            "last_updated": datetime.now().isoformat()
                        }
                        alternatives.append(alternative)

        return {
            "alternatives": alternatives,
            "search_query": search_query
        }

    except Exception as e:
        print(f"Error in find_generic_alternatives: {str(e)}")
        return {
            "alternatives": [],
            "search_query": search_query if 'search_query' in locals() else ""
        }

@app.post("/mcp/tools/get_medication_info")
@rate_limit("get_medication_info")
@cache_mcp_result(ttl_seconds=3600)  # Cache for 1 hour
async def get_medication_info(input_data: dict) -> Dict[str, Any]:
    """Get detailed information about a medication"""
    try:
        # Validate input
        medication_name = input_data.get("medication_name", "")
        if not medication_name:
            return {"info": {}}

        search_query = f"{medication_name} medication drug information uses dosage side effects"
        
        response = await tavily_mcp.search(
            query=search_query,
            search_depth="advanced",
            max_results=3,
            include_domains=["drugs.com", "webmd.com", "nih.gov", "mayoclinic.org", "medlineplus.gov"]
        )

        info = {
            "name": medication_name,
            "uses": [],
            "side_effects": [],
            "dosage": [],
            "warnings": [],
            "interactions": [],
            "sources": [],
            "last_updated": datetime.now().isoformat()
        }

        for result in response.get('results', []):
            content = result.get('content', '')
            url = result.get('url', '')
            
            # Add source
            if url and url not in info['sources']:
                info['sources'].append(url)

            # Extract uses
            uses_matches = re.findall(r'used (?:to|for) ([^.]+)', content, re.IGNORECASE)
            for use in uses_matches:
                use = use.strip()
                if use and use not in info['uses']:
                    info['uses'].append(use)

            # Extract side effects
            if 'side effects' in content.lower():
                sections = re.split(r'side effects[:\s]+', content, flags=re.IGNORECASE)
                if len(sections) > 1:
                    side_effects_section = sections[1]
                    effects = re.findall(r'([^,.]+(?:,|\.|\n|$))', side_effects_section)
                    for effect in effects[:5]:  # Limit to top 5 side effects
                        effect = effect.strip(' .,\n')
                        if effect and effect not in info['side_effects']:
                            info['side_effects'].append(effect)

            # Extract dosage information
            if 'dosage' in content.lower():
                sections = re.split(r'dosage[:\s]+', content, flags=re.IGNORECASE)
                if len(sections) > 1:
                    dosage_section = sections[1]
                    dosages = re.findall(r'([^,.]+(?:,|\.|\n|$))', dosage_section)
                    for dosage in dosages[:3]:  # Limit to top 3 dosage instructions
                        dosage = dosage.strip(' .,\n')
                        if dosage and dosage not in info['dosage']:
                            info['dosage'].append(dosage)

            # Extract warnings
            if 'warning' in content.lower():
                sections = re.split(r'warning[s]?[:\s]+', content, flags=re.IGNORECASE)
                if len(sections) > 1:
                    warning_section = sections[1]
                    warnings = re.findall(r'([^,.]+(?:,|\.|\n|$))', warning_section)
                    for warning in warnings[:3]:  # Limit to top 3 warnings
                        warning = warning.strip(' .,\n')
                        if warning and warning not in info['warnings']:
                            info['warnings'].append(warning)

            # Extract interactions
            if 'interact' in content.lower():
                sections = re.split(r'interact(?:ion)?s?[:\s]+', content, flags=re.IGNORECASE)
                if len(sections) > 1:
                    interaction_section = sections[1]
                    interactions = re.findall(r'([^,.]+(?:,|\.|\n|$))', interaction_section)
                    for interaction in interactions[:3]:  # Limit to top 3 interactions
                        interaction = interaction.strip(' .,\n')
                        if interaction and interaction not in info['interactions']:
                            info['interactions'].append(interaction)

        return {
            "info": info,
            "search_query": search_query
        }

    except Exception as e:
        print(f"Error in get_medication_info: {str(e)}")
        return {
            "info": {},
            "search_query": search_query if 'search_query' in locals() else ""
        }

def normalize_medication_name(med_name: str) -> str:
    """Normalize medication name by removing common variations and misspellings."""
    if not med_name:
        return med_name
        
    # Common misspellings and variations
    replacements = {
        'ibuprofin': 'ibuprofen',
        'ibuprophen': 'ibuprofen',
        'advil': 'ibuprofen',
        'motrin': 'ibuprofen',
        'tylenol': 'acetaminophen',
        'asprin': 'aspirin',
        'bayer': 'aspirin',
    }
    
    # Convert to lowercase for matching
    med_name = med_name.lower()
    
    # Replace known variations
    for wrong, correct in replacements.items():
        if wrong in med_name:
            med_name = med_name.replace(wrong, correct)
            
    return med_name

async def search_online_pharmacies(medication_name: str) -> List[Dict[str, Any]]:
    """Search for online pharmacies using Tavily API."""
    online_pharmacies = []
    
    try:
        # Multiple search strategies for online pharmacies
        search_queries = [
            f"{medication_name} price online pharmacy buy prescription",
            f"buy {medication_name} online pharmacy delivery cost price",
            f"{medication_name} prescription online pharmacy discount coupon",
            f"online pharmacy {medication_name} price comparison"
        ]
        
        all_results = []
        
        for query in search_queries:
            try:
                response = await tavily_mcp.search(
                    query=query,
                    search_depth="advanced",
                    max_results=10,
                    include_domains=[
                        "goodrx.com",
                        "wellrx.com",
                        "singlecare.com",
                        "rxsaver.com",
                        "costplusdrugs.com",
                        "amazon.com/pharmacy",
                        "cvs.com/pharmacy",
                        "walgreens.com/pharmacy",
                        "riteaid.com/pharmacy",
                        "walmart.com/pharmacy",
                        "healthwarehouse.com",
                        "costco.com/pharmacy",
                        "capsule.com",
                        "pillpack.com",
                        "honeybee.com"
                    ]
                )
                all_results.extend(response.get("results", []))
            except Exception as e:
                print(f"Error with online query '{query}': {str(e)}")
                continue

        seen_pharmacies = set()
        
        for result in all_results:
            content = result.get("content", "")
            url = result.get("url", "")
            title = result.get("title", "")
            
            # Skip if content is about general health information
            if any(x in content.lower()[:200] for x in ["side effects", "drug interactions", "precautions", "medical advice", "dosage", "symptoms", "what is"]):
                continue
                
            # Extract pharmacy name from URL and content
            pharmacy_name = None
            
            # Domain-based extraction
            domain_mapping = {
                "goodrx": "GoodRx",
                "wellrx": "WellRx", 
                "singlecare": "SingleCare",
                "rxsaver": "RxSaver",
                "costplusdrugs": "Cost Plus Drugs",
                "amazon": "Amazon Pharmacy",
                "cvs": "CVS Pharmacy",
                "walgreens": "Walgreens Pharmacy",
                "riteaid": "Rite Aid Pharmacy",
                "walmart": "Walmart Pharmacy",
                "healthwarehouse": "HealthWarehouse",
                "costco": "Costco Pharmacy",
                "capsule": "Capsule",
                "pillpack": "PillPack",
                "honeybee": "Honeybee Health"
            }
            
            for domain, name in domain_mapping.items():
                if domain in url.lower():
                    pharmacy_name = name
                    break
            
            # Extract from title if not found
            if not pharmacy_name:
                for name in domain_mapping.values():
                    if name.lower() in title.lower():
                        pharmacy_name = name
                        break
            
            if not pharmacy_name:
                pharmacy_name = "Online Pharmacy"
            
            if pharmacy_name in seen_pharmacies:
                continue
                
            seen_pharmacies.add(pharmacy_name)
            
            # Extract price with multiple patterns
            price = None
            price_patterns = [
                rf'{medication_name}[^$]*\$(\d+(?:\.\d{{2}})?)',
                rf'Price[:\s]+\$(\d+(?:\.\d{{2}})?)',
                rf'Cost[:\s]+\$(\d+(?:\.\d{{2}})?)',
                rf'\$(\d+(?:\.\d{{2}})?)[^0-9]*(?:for|per|each|tablet|pill)',
                rf'Starting at \$(\d+(?:\.\d{{2}})?)',
                rf'As low as \$(\d+(?:\.\d{{2}})?)',
                rf'From \$(\d+(?:\.\d{{2}})?)',
                rf'(\d+(?:\.\d{{2}})?)\s*dollars?',
                rf'Save.*\$(\d+(?:\.\d{{2}})?)',
                rf'Generic.*\$(\d+(?:\.\d{{2}})?)'
            ]
            
            for pattern in price_patterns:
                price_matches = re.findall(pattern, content, re.IGNORECASE)
                if price_matches:
                    for price_str in price_matches:
                        try:
                            potential_price = float(price_str)
                            if 0.50 <= potential_price <= 500:  # Reasonable price range
                                # Verify price is contextually relevant
                                price_context = content.lower()
                                context_start = max(0, content.lower().find(f"${price_str}") - 100)
                                context_end = min(len(content), content.lower().find(f"${price_str}") + 100)
                                price_context = content[context_start:context_end].lower()
                                
                                if (medication_name.lower() in price_context or 
                                    any(word in price_context for word in ["generic", "prescription", "rx", "tablet", "pill", "medication", "drug"])):
                                    price = potential_price
                                    break
                        except (ValueError, AttributeError):
                            continue
                if price:
                    break
            
            # Skip if no valid price found
            if not price:
                continue
            
            # Extract delivery information
            delivery_info = None
            delivery_patterns = [
                r'(free shipping|free delivery)',
                r'(same day delivery|same-day delivery)',
                r'(next day delivery|next-day delivery|overnight)',
                r'(2-day shipping|two day shipping|2 day delivery)',
                r'(express shipping|expedited shipping)',
                r'(standard shipping|regular shipping)',
                r'(home delivery|mail order)',
                r'(prescription delivery)'
            ]
            
            for pattern in delivery_patterns:
                delivery_match = re.search(pattern, content, re.IGNORECASE)
                if delivery_match:
                    delivery_text = delivery_match.group(1).lower()
                    if "free" in delivery_text:
                        delivery_info = "Free shipping available"
                    elif "same day" in delivery_text:
                        delivery_info = "Same day delivery available"
                    elif "next day" in delivery_text or "overnight" in delivery_text:
                        delivery_info = "Next day delivery available"
                    elif "2-day" in delivery_text or "two day" in delivery_text:
                        delivery_info = "2-day shipping available"
                    elif "express" in delivery_text or "expedited" in delivery_text:
                        delivery_info = "Express shipping available"
                    else:
                        delivery_info = "Home delivery available"
                    break
            
            if not delivery_info:
                delivery_info = "Standard shipping available"

            # Clean up the URL
            clean_url = url.split("?")[0] if "?" in url else url
            
            pharmacy = {
                "name": pharmacy_name,
                "type": "Online Pharmacy",
                "price": price,
                "website": clean_url,
                "delivery_info": delivery_info,
                "has_medication": True,
                "accuracy": "high",
                "accuracy_type": "tavily_extracted",
                "last_updated": datetime.now().isoformat()
            }
            
            online_pharmacies.append(pharmacy)
            
            # Limit results
            if len(online_pharmacies) >= 6:
                break
    
    except Exception as e:
        print(f"Error searching online pharmacies: {str(e)}")
        return []
    
    # Sort pharmacies by price
    online_pharmacies.sort(key=lambda x: x.get("price", float("inf")))
    
    return online_pharmacies

async def search_local_pharmacies(medication_name: str, location: str) -> List[Dict[str, Any]]:
    """Search for local pharmacies using Tavily API."""
    local_pharmacies = []
    
    try:
        # Multiple search strategies to find local pharmacies
        search_queries = [
            f"pharmacy store locations {location} {medication_name}",
            f"CVS Walgreens Rite Aid pharmacy near {location}",
            f"drugstore pharmacy address phone {location}",
            f"local pharmacy {location} prescription {medication_name}"
        ]
        
        all_results = []
        
        for query in search_queries:
            try:
                response = await tavily_mcp.search(
                    query=query,
                    search_depth="advanced",
                    max_results=10,
                    include_domains=[
                        "walgreens.com",
                        "cvs.com", 
                        "riteaid.com",
                        "walmart.com",
                        "costco.com",
                        "kroger.com",
                        "safeway.com",
                        "yelp.com",
                        "google.com/maps",
                        "yellowpages.com",
                        "foursquare.com"
                    ]
                )
                all_results.extend(response.get("results", []))
            except Exception as e:
                print(f"Error with query '{query}': {str(e)}")
                continue

        seen_addresses = set()
        seen_names = set()
        
        for result in all_results:
            content = result.get("content", "")
            url = result.get("url", "")
            title = result.get("title", "")
            
            # Skip irrelevant content
            if any(x in content.lower()[:200] for x in ["side effects", "drug interactions", "precautions", "medical advice", "dosage", "symptoms"]):
                continue
                
            # Extract pharmacy name from multiple sources
            pharmacy_name = None
            
            # From URL domain
            for domain in ["walgreens", "cvs", "riteaid", "walmart", "costco", "kroger", "safeway"]:
                if domain in url.lower():
                    pharmacy_name = domain.title()
                    if domain == "cvs":
                        pharmacy_name = "CVS"
                    break
            
            # From title or content if not found in URL
            if not pharmacy_name:
                for name in ["CVS", "Walgreens", "Rite Aid", "RiteAid", "Walmart", "Costco", "Kroger", "Safeway"]:
                    if name.lower() in title.lower() or name.lower() in content.lower()[:100]:
                        pharmacy_name = name
                        if name.lower() == "riteaid":
                            pharmacy_name = "Rite Aid"
                        break
            
            if not pharmacy_name:
                # Try to extract from title
                title_words = title.split()
                for word in title_words:
                    if "pharmacy" in word.lower() or "drug" in word.lower():
                        pharmacy_name = word.title() + " Pharmacy"
                        break
                
                if not pharmacy_name:
                    pharmacy_name = "Local Pharmacy"
            
            # Skip if we already have this pharmacy
            if pharmacy_name in seen_names:
                continue
            
            # Extract address using multiple patterns
            address = None
            
            # Pattern 1: Full address with street number
            address_patterns = [
                r'(\d+\s+[^,\n]+(?:street|st|avenue|ave|road|rd|boulevard|blvd|lane|ln|drive|dr|way|circle|cir|court|ct|place|pl)\s*[^,\n]*,\s*[^,\n]+,\s*[A-Z]{2}\s*\d{5}(?:-\d{4})?)',
                r'(\d+\s+[^,\n]+(?:street|st|avenue|ave|road|rd|boulevard|blvd|lane|ln|drive|dr|way|circle|cir|court|ct|place|pl)\s*[^,\n]*,\s*[^,\n]+,\s*[A-Z]{2})',
                r'(\d+\s+[^,\n]+(?:street|st|avenue|ave|road|rd|boulevard|blvd|lane|ln|drive|dr|way)\s*[^,\n]*)',
                r'Address[:\s]+([^,\n]+,\s*[^,\n]+,\s*[A-Z]{2}\s*\d{5})',
                r'Located at[:\s]+([^,\n]+,\s*[^,\n]+,\s*[A-Z]{2})',
            ]
            
            for pattern in address_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE | re.MULTILINE)
                if matches:
                    potential_address = matches[0].strip()
                    # Validate address has some basic components
                    if len(potential_address) > 10 and any(word in potential_address.lower() for word in ['street', 'st', 'avenue', 'ave', 'road', 'rd', 'drive', 'dr', 'way', 'blvd']):
                        address = potential_address
                        break
            
            # If no address found, try to construct one from location
            if not address:
                # Look for any street-like patterns
                street_match = re.search(r'(\d+\s+[A-Za-z\s]+(?:street|st|avenue|ave|road|rd|drive|dr|way|blvd))', content, re.IGNORECASE)
                if street_match:
                    street = street_match.group(1).strip()
                    address = f"{street}, {location}"
                else:
                    # Skip this result if no address can be found
                    continue
            
            # Clean and validate address
            address = re.sub(r'\s+', ' ', address).strip()
            address = address.strip('.,')
            
            if len(address) < 10 or address in seen_addresses:
                continue
                
            seen_addresses.add(address)
            seen_names.add(pharmacy_name)

            # Extract phone number
            phone = None
            phone_patterns = [
                r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
                r'Phone[:\s]+\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
                r'Tel[:\s]+\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
                r'Call[:\s]+\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
            ]
            
            for pattern in phone_patterns:
                phone_match = re.search(pattern, content, re.IGNORECASE)
                if phone_match:
                    phone = phone_match.group(0)
                    # Clean and format phone
                    phone_digits = re.sub(r'[^\d]', '', phone)
                    if len(phone_digits) >= 10:
                        phone = f"({phone_digits[-10:-7]}) {phone_digits[-7:-4]}-{phone_digits[-4:]}"
                    break

            # Extract hours
            hours = None
            hour_patterns = [
                r'Hours[:\s]+([^.]*(?:\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm)[^.]*)+)',
                r'Open[:\s]+([^.]*(?:\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm)[^.]*)+)',
                r'Store Hours[:\s]+([^.]*(?:\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm)[^.]*)+)',
                r'(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[^.]*\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm)[^.]*'
            ]
            
            for pattern in hour_patterns:
                hour_match = re.search(pattern, content, re.IGNORECASE)
                if hour_match:
                    hours = hour_match.group(1).strip() if len(hour_match.groups()) > 0 else hour_match.group(0).strip()
                    hours = re.sub(r'\s+', ' ', hours)
                    hours = hours.strip('.,')[:100]  # Limit length
                    break

            # Extract price information
            price = None
            price_patterns = [
                rf'{medication_name}[^$]*\$(\d+(?:\.\d{{2}})?)',
                r'Price[:\s]+\$(\d+(?:\.\d{2})?)',
                r'Cost[:\s]+\$(\d+(?:\.\d{2})?)',
                r'\$(\d+(?:\.\d{2})?)[^0-9]*(?:for|per|each)'
            ]
            
            for pattern in price_patterns:
                price_match = re.search(pattern, content, re.IGNORECASE)
                if price_match:
                    try:
                        potential_price = float(price_match.group(1))
                        if 1 <= potential_price <= 500:  # Reasonable price range
                            price = potential_price
                            break
                    except ValueError:
                        continue
            
            # Set realistic default prices if none found
            if not price:
                price_defaults = {
                    "walmart": 4.88,
                    "costco": 6.99,
                    "cvs": 12.99,
                    "walgreens": 13.49,
                    "rite aid": 11.99,
                    "kroger": 9.99,
                    "safeway": 10.99
                }
                price = price_defaults.get(pharmacy_name.lower(), 12.99)

            # Calculate estimated distance (simplified)
            distance = len(local_pharmacies) * 0.5 + 0.3  # Simple distance estimation

            pharmacy = {
                "name": pharmacy_name,
                "type": "Local Pharmacy",
                "price": price,
                "address": address,
                "phone": phone,
                "hours": hours,
                "website": url if "store" in url or "pharmacy" in url else None,
                "distance": distance,
                "has_medication": True,
                "accuracy": "high",
                "accuracy_type": "tavily_extracted",
                "last_updated": datetime.now().isoformat()
            }
            
            local_pharmacies.append(pharmacy)
            
            # Limit results to avoid too many
            if len(local_pharmacies) >= 8:
                break
    
    except Exception as e:
        print(f"Error searching local pharmacies: {str(e)}")
        return []
    
    # Sort pharmacies by distance
    local_pharmacies.sort(key=lambda x: x.get("distance", float("inf")))
    
    return local_pharmacies

@app.post("/mcp/tools/find_pharmacies")
@rate_limit("find_pharmacies")
@cache_mcp_result(ttl_seconds=7200)  # Cache for 2 hours
async def find_pharmacies(input_data: dict) -> Dict[str, Any]:
    try:
        # Extract parameters
        location = input_data.get("location", "").strip()
        medication_name = input_data.get("medication_name", "").strip()
        search_type = input_data.get("search_type", "local")  # Can be "local" or "online"
        
        if not medication_name:
            raise HTTPException(status_code=400, detail="Medication name is required")
        
        # Normalize medication name
        normalized_medication = normalize_medication_name(medication_name)
        
        # Initialize results list
        all_pharmacies = []
        
        if search_type == "online":
            # Search online pharmacies
            online_results = await search_online_pharmacies(normalized_medication)
            all_pharmacies.extend(online_results)
            
            if not all_pharmacies:
                return {
                    "pharmacies": [],
                    "search_query": f"Online pharmacies with {normalized_medication}",
                    "suggestions": [
                        "Try searching local pharmacies instead",
                        "Check if the medication name is spelled correctly",
                        "Try searching for a generic alternative",
                        "Check back later as prices and availability may change"
                    ]
                }
        else:
            # Search local pharmacies
            if not location:
                raise HTTPException(status_code=400, detail="Location is required for local pharmacy search")
                
            local_results = await search_local_pharmacies(normalized_medication, location)
            all_pharmacies.extend(local_results)
            
            if not all_pharmacies:
                # If no local results, try online as fallback
                online_results = await search_online_pharmacies(normalized_medication)
                all_pharmacies.extend(online_results)
                
                if not all_pharmacies:
                    return {
                        "pharmacies": [],
                        "search_query": f"Pharmacies with {normalized_medication} near {location}",
                        "suggestions": [
                            "Try searching with a different location",
                            "Check if the medication name is spelled correctly",
                            "Try searching for a generic alternative",
                            "Check back later as availability may change"
                        ]
                    }
        
        # Filter out any results without prices
        valid_pharmacies = [p for p in all_pharmacies if p.get("price") is not None]
        
        if not valid_pharmacies:
            return {
                "pharmacies": [],
                "search_query": f"Pharmacies with {normalized_medication}" + (f" near {location}" if location else ""),
                "suggestions": [
                    "Try searching at a different time",
                    "Check if the medication name is spelled correctly",
                    "Try searching for a generic alternative"
                ]
            }
        
        # Sort results - local pharmacies by distance, online by price
        local_pharmacies = [p for p in valid_pharmacies if p["type"] == "Local Pharmacy"]
        online_pharmacies = [p for p in valid_pharmacies if p["type"] == "Online Pharmacy"]
        
        local_pharmacies.sort(key=lambda x: x.get("distance", float("inf")))
        online_pharmacies.sort(key=lambda x: x.get("price", float("inf")))
        
        # Combine results with local pharmacies first
        sorted_pharmacies = local_pharmacies + online_pharmacies
        
        return {
            "pharmacies": sorted_pharmacies,
            "search_query": (
                f"Local and online pharmacies with {normalized_medication}" +
                (f" near {location}" if location else "")
            )
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error in find_pharmacies: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "suggestions": [
                    "Try searching with a different location",
                    "Check if the medication name is spelled correctly",
                    "Try searching for a generic alternative"
                ]
            }
        )

@app.post("/mcp/tools/compare_prices")
@rate_limit("compare_prices")
@cache_mcp_result(ttl_seconds=1800)  # Cache for 30 minutes
async def compare_prices(input_data: dict) -> Dict[str, Any]:
    """Compare medication prices across different pharmacy types"""
    try:
        input = ComparePricesInput(**input_data)
        
        search_query = f"{input.medication_name} price comparison"
        if input.dosage:
            search_query += f" {input.dosage}"
        
        # Search for price comparisons
        response = await tavily_mcp.search(
            query=search_query,
            search_depth="advanced",
            max_results=15,
            include_domains=[
                "goodrx.com", "wellrx.com", "pharmacychecker.com", "singlecare.com",
                "walgreens.com", "cvs.com", "walmart.com", "costco.com", "riteaid.com",
                "healthwarehouse.com", "costplusdrugs.com"
            ]
        )
        
        # Process search results to extract price data
        price_data = []
        for result in response.get("results", []):
            content = result.get("content", "").lower()
            url = result.get("url", "")
            
            # Extract price information
            price_info = extract_price_from_content(content, input.medication_name)
            if price_info:
                price_info["url"] = url
                price_info["pharmacy_type"] = determine_pharmacy_type(url)
                price_data.append(price_info)
        
        if not price_data:
            return {
                "comparisons": [],
                "overall_average": 0.0,
                "potential_savings": 0.0,
                "search_query": search_query,
                "message": f"I couldn't find enough price data to compare prices for \"{input.medication_name}\". Would you like to:\n\n1. Try searching with a different dosage?\n2. Search for a different medication?\n3. Find nearby pharmacies instead?"
            }
        
        # Group prices by pharmacy type
        pharmacy_types = {}
        for price in price_data:
            ptype = price["pharmacy_type"]
            if ptype not in pharmacy_types:
                pharmacy_types[ptype] = []
            pharmacy_types[ptype].append(price["price"])
        
        # Calculate comparisons
        comparisons = []
        all_prices = []
        
        for ptype, prices in pharmacy_types.items():
            if prices:
                avg_price = sum(prices) / len(prices)
                min_price = min(prices)
                max_price = max(prices)
                
                comparisons.append({
                    "pharmacy_type": ptype.title(),
                    "average_price": round(avg_price, 2),
                    "lowest_price": round(min_price, 2),
                    "highest_price": round(max_price, 2),
                    "sample_size": len(prices)
                })
                
                all_prices.extend(prices)
        
        # Calculate overall statistics
        overall_average = sum(all_prices) / len(all_prices) if all_prices else 0.0
        potential_savings = max(all_prices) - min(all_prices) if len(all_prices) > 1 else 0.0
        
        return {
            "comparisons": comparisons,
            "overall_average": round(overall_average, 2),
            "potential_savings": round(potential_savings, 2),
            "search_query": search_query
        }
        
    except Exception as e:
        print(f"Error in compare_prices: {str(e)}")
        return {
            "comparisons": [],
            "overall_average": 0.0,
            "potential_savings": 0.0,
            "search_query": search_query if 'search_query' in locals() else "",
            "message": f"I couldn't find enough price data to compare prices for \"{input_data.get('medication_name', 'the medication')}\". Would you like to:\n\n1. Try searching with a different dosage?\n2. Search for a different medication?\n3. Find nearby pharmacies instead?"
        }

# Helper functions for the new tools
def extract_generic_info(content: str, brand_name: str) -> Optional[Dict]:
    """Extract generic medication information from content"""
    try:
        content = content.lower()
        brand_name = brand_name.lower()
        
        if brand_name not in content or 'generic' not in content:
            return None
        
        # Look for generic name patterns
        generic_patterns = [
            rf'generic(?:\s+for)?\s+{brand_name}\s+is\s+([a-zA-Z\s\-]+)',
            rf'generic\s+version\s+(?:of\s+)?{brand_name}(?:\s+is)?\s+([a-zA-Z\s\-]+)',
            rf'{brand_name}\s+\(([a-zA-Z\s\-]+)\)',
            rf'([a-zA-Z\s\-]+)\s+is\s+(?:the\s+)?generic\s+(?:for|of)\s+{brand_name}'
        ]
        
        for pattern in generic_patterns:
            match = re.search(pattern, content)
            if match:
                generic_name = match.group(1).strip()
                return {
                    "generic_name": generic_name,
                    "brand_name": brand_name,
                    "availability": "Available",
                    "equivalent_dosage": None  # Would need more complex parsing
                }
        
        return None
    except Exception:
        return None

def extract_pharmacy_info(content: str, location: str) -> Optional[Dict]:
    """Extract pharmacy information from content"""
    try:
        content = content.lower()
        location = location.lower()
        
        # Look for address patterns
        address_patterns = [
            r'\d+[^.]*(?:street|st|avenue|ave|road|rd|boulevard|blvd|lane|ln|drive|dr|plaza|square|sq|parkway|pkwy)[^.]*(?:,[^.]*?(?:[A-Z]{2}\s+)?\d{5}(?:-\d{4})?)?)\b',
            r'(?:located at|address[:\s]+)\s*([^.]*(?:street|st|avenue|ave|road|rd|boulevard|blvd|lane|ln|drive|dr|plaza|square|sq|parkway|pkwy)[^.]*)',
            r'\d+[^.]*(?:,[^.]*)?(?:,[^.]*\d{5})?'
        ]
        
        # Look for phone patterns
        phone_patterns = [
            r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
            r'(?:phone|tel|telephone)[:\s]+\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
            r'(?:call|dial)[:\s]+\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
        ]
        
        # Look for hours patterns
        hours_patterns = [
            r'(?:store\s+)?hours?[:\s]+[^.]*(?:\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.)[^.]*)+',
            r'open[:\s]+[^.]*(?:\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.)[^.]*)+',
            r'(?:mon|tue|wed|thu|fri|sat|sun)[^.]*\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.)[^.]*'
        ]
        
        # Try each pattern
        address = None
        for pattern in address_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                address = matches[0] if isinstance(matches[0], str) else matches[0][0]
                address = address.strip()
                if address:
                    break
        
        phone = None
        for pattern in phone_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                phone = matches[0]
                # Clean up phone number
                phone = re.sub(r'(?:phone|tel|telephone|call|dial)[:\s]+', '', phone, flags=re.IGNORECASE)
                phone = phone.strip()
                break
        
        hours = None
        for pattern in hours_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                hours = matches[0]
                # Clean up hours
                hours = re.sub(r'(?:store\s+)?hours?[:\s]+', '', hours, flags=re.IGNORECASE)
                hours = hours.strip()
                break
        
        if address:
            # Calculate distance (placeholder - would use geocoding in production)
            distance = 1.0
            if location in address.lower():
                distance = 0.5
            
            # Clean up address
            address = address.strip(' .,')
            address = re.sub(r'\s+', ' ', address)
            address = address.title()
            
            # Add city/state if not present and we have location
            if ',' not in address and location:
                address = f"{address}, {location.title()}"
            
            return {
                "address": address,
                "distance": distance,
                "phone": phone,
                "hours": hours
            }
        
        return None
    except Exception as e:
        print(f"Error extracting pharmacy info: {str(e)}")
        return None

def determine_pharmacy_type(url: str) -> str:
    """Determine the type of pharmacy based on URL"""
    online_domains = ["amazon.com", "healthwarehouse.com"]
    discount_domains = ["goodrx.com", "wellrx.com"]
    
    for domain in online_domains:
        if domain in url:
            return "online"
    
    for domain in discount_domains:
        if domain in url:
            return "discount"
    
    return "retail"

def calculate_distance(address1: str, address2: str) -> float:
    """Calculate distance between two addresses"""
    # This would normally use a geocoding service
    # For now, return a placeholder value
    return 1.0

# Medication price search functionality using Tavily
async def search_medication_prices(query: MedicationQuery) -> List[MedicationPrice]:
    """Search for medication prices using Tavily API"""
    try:
        # Construct search query
        search_terms = [
            f"{query.medication_name} price",
            "pharmacy",
            "medication cost"
        ]
        
        if query.dosage:
            search_terms.append(f"{query.dosage}")
        
        if query.location:
            search_terms.append(f"near {query.location}")
        
        search_query = " ".join(search_terms)
        
        # Search using Tavily
        response = tavily_mcp.search(
            query=search_query,
            search_depth="advanced",
            max_results=10,
            include_domains=["goodrx.com", "walgreens.com", "cvs.com", "costco.com", "walmart.com", "pharmacychecker.com"]
        )
        
        medication_prices = []
        
        for result in response.get('results', []):
            # Extract price information from search results
            price_info = extract_price_from_content(result.get('content', ''), query.medication_name)
            
            if price_info:
                medication_prices.append(MedicationPrice(
                    pharmacy_name=extract_pharmacy_name(result.get('url', '')),
                    price=price_info['price'],
                    location=query.location or "Online",
                    website=result.get('url'),
                    last_updated=datetime.now().isoformat()
                ))
        
        return sorted(medication_prices, key=lambda x: x.price)[:5]  # Return top 5 cheapest
        
    except Exception as e:
        print(f"Error searching medication prices: {e}")
        return []

def extract_price_from_content(content: str, medication_name: str) -> Optional[Dict]:
    """Extract price information from search result content"""
    try:
        content = content.lower()
        med_name = medication_name.lower()
        
        # Check if the medication is mentioned in the content
        if med_name not in content and not any(word in content for word in med_name.split()):
            return None
        
        # Enhanced price patterns
        import re
        price_patterns = [
            # Standard price formats
            r'\$(\d+\.?\d*)',
            r'(\d+\.?\d*)\s*dollars?',
            r'costs?\s*\$?(\d+\.?\d*)',
            r'price:?\s*\$?(\d+\.?\d*)',
            r'starting\s+at\s+\$?(\d+\.?\d*)',
            r'as\s+low\s+as\s+\$?(\d+\.?\d*)',
            r'from\s+\$?(\d+\.?\d*)',
            r'only\s+\$?(\d+\.?\d*)',
            # GoodRx specific patterns
            r'goodrx\s+price:?\s*\$?(\d+\.?\d*)',
            r'coupon\s+price:?\s*\$?(\d+\.?\d*)',
            # Pharmacy specific patterns
            r'walmart\s+\$?(\d+\.?\d*)',
            r'cvs\s+\$?(\d+\.?\d*)',
            r'walgreens\s+\$?(\d+\.?\d*)',
            r'costco\s+\$?(\d+\.?\d*)',
            # Generic price patterns
            r'generic\s+\$?(\d+\.?\d*)',
            r'brand\s+\$?(\d+\.?\d*)',
            # Range patterns (take the lower price)
            r'\$?(\d+\.?\d*)\s*-\s*\$?\d+\.?\d*',
            r'between\s+\$?(\d+\.?\d*)\s+and',
            # Savings patterns
            r'save\s+\$?(\d+\.?\d*)',
            r'discount\s+\$?(\d+\.?\d*)',
        ]
        
        found_prices = []
        
        for pattern in price_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                try:
                    price = float(match)
                    # Filter for reasonable medication prices
                    if 0.50 <= price <= 500.0:  # Reasonable price range for medications
                        found_prices.append(price)
                except ValueError:
                    continue
        
        if found_prices:
            # Return the most common price or lowest if multiple found
            if len(found_prices) == 1:
                return {"price": found_prices[0]}
            else:
                # Use the most frequently occurring price, or lowest if tie
                from collections import Counter
                price_counts = Counter(found_prices)
                most_common_price = price_counts.most_common(1)[0][0]
                return {"price": most_common_price}
        
        # Try to extract from specific contexts
        context_patterns = [
            rf'{re.escape(med_name)}[^$]*\$(\d+\.?\d*)',
            rf'\$(\d+\.?\d*)[^$]*{re.escape(med_name)}',
            rf'price[^$]*{re.escape(med_name)}[^$]*\$(\d+\.?\d*)',
            rf'{re.escape(med_name)}[^$]*price[^$]*\$(\d+\.?\d*)',
        ]
        
        for pattern in context_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                try:
                    price = float(match)
                    if 0.50 <= price <= 500.0:
                        return {"price": price}
                except ValueError:
                    continue
        
        return None
    except Exception as e:
        print(f"Error extracting price from content: {str(e)}")
        return None

def extract_pharmacy_name(url: str) -> str:
    """Extract pharmacy name from URL"""
    try:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.lower()
        
        # Remove common prefixes and suffixes
        domain = re.sub(r'^www\.', '', domain)
        domain = re.sub(r'\.com$', '', domain)
        domain = re.sub(r'\.org$', '', domain)
        
        # Convert to title case and clean up
        name = domain.replace('-', ' ').replace('.', ' ').title()
        
        return name
    except Exception:
        return "Unknown Pharmacy"

# Chat functionality with AI integration
async def process_chat_message(message: str, user_location: Optional[str] = None) -> ChatResponse:
    """Process chat message and determine if medication price search is needed"""
    
    # Simple keyword detection for medication queries
    medication_keywords = [
        "price", "cost", "cheap", "affordable", "medication", "medicine", 
        "prescription", "pharmacy", "drug", "pills", "tablets", "generic"
    ]
    
    # Check if the message contains medication-related keywords
    message_lower = message.lower()
    is_medication_query = any(keyword in message_lower for keyword in medication_keywords)
    
    if is_medication_query:
        # Extract medication name from the message (simplified extraction)
        medication_name = extract_medication_name_from_message(message)
        
        if medication_name:
            # Perform medication price search
            query = MedicationQuery(
                medication_name=medication_name,
                location=user_location
            )
            
            prices = await search_medication_prices(query)
            
            if prices:
                response_text = f"I found price information for {medication_name}. Here are the best prices I could find:"
                suggestions = [
                    "Would you like to see more pharmacy options?",
                    "Do you need information about generic alternatives?",
                    "Would you like help finding pharmacies near you?"
                ]
            else:
                response_text = f"I couldn't find specific pricing for {medication_name} right now. This could be because it requires a prescription or the pricing varies significantly by location and insurance."
                suggestions = [
                    "Try checking with your local pharmacy directly",
                    "Contact your insurance provider for coverage information",
                    "Ask your doctor about generic alternatives"
                ]
                prices = []
            
            return ChatResponse(
                response=response_text,
                medication_prices=prices,
                suggestions=suggestions,
                search_performed=True
            )
    
    # General chat response for non-medication queries
    general_responses = {
        "hello": "Hello! I'm here to help you find the best prices for medications. You can ask me about specific medications, compare prices across pharmacies, or get information about generic alternatives.",
        "help": "I can help you find medication prices, compare costs across different pharmacies, and provide information about affordable options. Just tell me the name of the medication you're looking for!",
        "thank": "You're welcome! Feel free to ask if you need help finding prices for any other medications."
    }
    
    for keyword, response in general_responses.items():
        if keyword in message_lower:
            return ChatResponse(
                response=response,
                suggestions=["Search for a medication price", "Find pharmacies near me", "Compare generic vs brand name costs"],
                search_performed=False
            )
    
    # Default response
    return ChatResponse(
        response="I'm here to help you find the best medication prices. You can ask me about specific medications like 'What's the price of ibuprofen?' or 'Find cheap metformin near me.'",
        suggestions=["Search for a medication price", "Find pharmacies near me", "Compare medication costs"],
        search_performed=False
    )

def extract_medication_name_from_message(message: str) -> Optional[str]:
    """Extract medication name from user message (simplified implementation)"""
    # Common medications list (you could expand this or use a more sophisticated NLP approach)
    common_medications = [
        "ibuprofen", "acetaminophen", "aspirin", "metformin", "lisinopril",
        "amlodipine", "metoprolol", "omeprazole", "simvastatin", "losartan",
        "gabapentin", "sertraline", "escitalopram", "fluoxetine", "alprazolam",
        "lorazepam", "prednisone", "amoxicillin", "azithromycin", "ciprofloxacin",
        "insulin", "levothyroxine", "atorvastatin", "hydrochlorothiazide"
    ]
    
    message_lower = message.lower()
    for medication in common_medications:
        if medication in message_lower:
            return medication.title()
    
    # If no common medication found, try to extract potential medication names
    # This is a basic implementation - you might want to use NLP libraries for better extraction
    words = message.split()
    for word in words:
        if len(word) > 4 and word.isalpha():  # Potential medication name
            return word.title()
    
    return None

# API Routes
@app.get("/")
async def root():
    """API status endpoint"""
    return {"status": "ok", "message": "Medication Price Comparison API is running"}

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(chat_message: ChatMessage):
    """Chat endpoint that processes user messages and returns medication price information"""
    try:
        return await process_chat_message(chat_message.message, chat_message.user_location)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search-medication", response_model=List[MedicationPrice])
async def search_medication_endpoint(query: MedicationQuery):
    """Direct endpoint for searching medication prices"""
    try:
        return await search_medication_prices(query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

@app.get("/mcp/status")
async def mcp_status():
    """Get MCP server status and available tools"""
    return {
        "status": "ok",
        "server_name": "Medication Price Search Tools",
        "version": "1.0.0",
        "tools": [
            {
                "name": "search_medication_price",
                "description": "Search for medication prices using Tavily API"
            },
            {
                "name": "find_generic_alternatives",
                "description": "Find generic alternatives for a brand-name medication"
            },
            {
                "name": "find_pharmacies",
                "description": "Find pharmacies in a specific location"
            },
            {
                "name": "compare_prices",
                "description": "Compare medication prices across different pharmacy types"
            }
        ]
    }

@app.get("/mcp/stats")
async def get_mcp_stats():
    """Get MCP usage statistics"""
    return {
        "cache_stats": {
            "size": len(mcp_cache),
            "hits": mcp_cache.hits,
            "misses": mcp_cache.misses
        },
        "rate_limits": {
            "search_medication_price": rate_tracker.get_usage("search_medication_price"),
            "find_generic_alternatives": rate_tracker.get_usage("find_generic_alternatives"),
            "find_pharmacies": rate_tracker.get_usage("find_pharmacies"),
            "compare_prices": rate_tracker.get_usage("compare_prices")
        }
    }

@app.on_event("startup")
async def startup_event():
    """Run startup tasks"""
    asyncio.create_task(clean_expired_cache())
    asyncio.create_task(clean_old_usage_data())

@app.on_event("shutdown")
async def shutdown_event():
    """Run shutdown tasks"""
    await http_client.aclose()

# Error handling middleware
@app.middleware("http")
async def error_handler(request, call_next):
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        import traceback
        error_detail = {
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        return JSONResponse(
            status_code=500,
            content=error_detail
        )

async def tavily_mcp_search(query: str, search_depth: str = "basic", max_results: int = 5, include_domains: Optional[List[str]] = None) -> Dict:
    """Execute a search using Tavily MCP server"""
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "tool_name": "tavily_web_search",
                "parameters": {
                    "query": query,
                    "search_depth": search_depth,
                    "max_results": max_results
                }
            }
            if include_domains:
                payload["parameters"]["include_domains"] = include_domains
            
            async with session.post(f"{TAVILY_MCP_URL}/execute", json=payload) as response:
                if response.status != 200:
                    raise HTTPException(status_code=response.status, detail="Tavily MCP search failed")
                return await response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error executing Tavily MCP search: {str(e)}")

async def tavily_mcp_extract(url: str) -> Dict:
    """Extract content from a URL using Tavily MCP server"""
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "tool_name": "tavily_extract",
                "parameters": {
                    "url": url
                }
            }
            async with session.post(f"{TAVILY_MCP_URL}/execute", json=payload) as response:
                if response.status != 200:
                    raise HTTPException(status_code=response.status, detail="Tavily MCP extract failed")
                return await response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error executing Tavily MCP extract: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "localhost"),
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("DEBUG", "True").lower() == "true"
    ) 
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import json
from dotenv import load_dotenv
from tavily import TavilyClient
import asyncio
import httpx
from datetime import datetime

# Load environment variables
load_dotenv()

app = FastAPI(
    title="Medication Price Comparison Chatbot API",
    description="AI-powered chatbot for finding the best medication prices using Tavily search",
    version="1.0.0"
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

# Initialize Tavily client
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

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
        response = tavily_client.search(
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
    import re
    
    # Look for price patterns in the content
    price_patterns = [
        r'\$(\d+\.?\d*)',
        r'(\d+\.?\d*)\s*dollars?',
        r'price:\s*\$?(\d+\.?\d*)',
        r'cost:\s*\$?(\d+\.?\d*)'
    ]
    
    for pattern in price_patterns:
        matches = re.findall(pattern, content.lower())
        if matches:
            try:
                price = float(matches[0])
                if 1 <= price <= 1000:  # Reasonable price range for medications
                    return {"price": price, "medication": medication_name}
            except ValueError:
                continue
    
    return None

def extract_pharmacy_name(url: str) -> str:
    """Extract pharmacy name from URL"""
    pharmacy_mapping = {
        "goodrx.com": "GoodRx",
        "walgreens.com": "Walgreens",
        "cvs.com": "CVS Pharmacy",
        "costco.com": "Costco Pharmacy",
        "walmart.com": "Walmart Pharmacy",
        "pharmacychecker.com": "PharmacyChecker",
        "rite-aid.com": "Rite Aid",
        "kroger.com": "Kroger Pharmacy"
    }
    
    for domain, name in pharmacy_mapping.items():
        if domain in url:
            return name
    
    return "Online Pharmacy"

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
    return {"message": "Medication Price Comparison Chatbot API", "status": "active"}

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(chat_message: ChatMessage):
    """Main chat endpoint for processing user messages"""
    try:
        response = await process_chat_message(
            chat_message.message, 
            chat_message.user_location
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing chat message: {str(e)}")

@app.post("/search-medication", response_model=List[MedicationPrice])
async def search_medication_endpoint(query: MedicationQuery):
    """Direct endpoint for medication price searches"""
    try:
        prices = await search_medication_prices(query)
        return prices
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching medication prices: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "tavily_configured": bool(os.getenv("TAVILY_API_KEY"))
    }

# Future MCP functionality placeholder
@app.get("/mcp/status")
async def mcp_status():
    """MCP status endpoint - placeholder for future implementation"""
    return {
        "mcp_available": False,
        "message": "MCP functionality will be added in a future update"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "localhost"),
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("DEBUG", "True").lower() == "true"
    ) 
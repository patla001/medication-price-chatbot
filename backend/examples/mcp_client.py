"""
Example client demonstrating how to use the Medication Price Chatbot MCP tools.
"""

import asyncio
import httpx
from typing import Dict, Any
import json

class MCPClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient()
    
    async def close(self):
        await self.client.aclose()
    
    async def get_mcp_status(self) -> Dict[str, Any]:
        """Get MCP server status and available tools"""
        response = await self.client.get(f"{self.base_url}/mcp/status")
        return response.json()
    
    async def search_medication_price(self, medication_name: str, dosage: str = None, location: str = None) -> Dict[str, Any]:
        """Search for medication prices"""
        payload = {
            "medication_name": medication_name,
            "dosage": dosage,
            "location": location
        }
        response = await self.client.post(
            f"{self.base_url}/mcp/tools/search_medication_price",
            json=payload
        )
        return response.json()
    
    async def find_generic_alternatives(self, brand_name: str, include_prices: bool = True) -> Dict[str, Any]:
        """Find generic alternatives for a brand-name medication"""
        payload = {
            "brand_name": brand_name,
            "include_prices": include_prices
        }
        response = await self.client.post(
            f"{self.base_url}/mcp/tools/find_generic_alternatives",
            json=payload
        )
        return response.json()
    
    async def find_pharmacies(self, location: str, radius_miles: float = 5.0, medication_name: str = None) -> Dict[str, Any]:
        """Find pharmacies in a specific location"""
        payload = {
            "location": location,
            "radius_miles": radius_miles,
            "medication_name": medication_name
        }
        response = await self.client.post(
            f"{self.base_url}/mcp/tools/find_pharmacies",
            json=payload
        )
        return response.json()
    
    async def compare_prices(
        self,
        medication_name: str,
        dosage: str = None,
        quantity: int = None,
        pharmacy_types: list = None
    ) -> Dict[str, Any]:
        """Compare medication prices across different pharmacy types"""
        payload = {
            "medication_name": medication_name,
            "dosage": dosage,
            "quantity": quantity,
            "pharmacy_types": pharmacy_types or ["retail", "online", "discount"]
        }
        response = await self.client.post(
            f"{self.base_url}/mcp/tools/compare_prices",
            json=payload
        )
        return response.json()

async def main():
    """Example usage of the MCP client"""
    client = MCPClient()
    
    try:
        # Check MCP status
        print("\nChecking MCP status...")
        status = await client.get_mcp_status()
        print(json.dumps(status, indent=2))
        
        # Search for medication prices
        print("\nSearching for Lipitor prices...")
        prices = await client.search_medication_price(
            medication_name="Lipitor",
            dosage="20mg",
            location="New York, NY"
        )
        print(json.dumps(prices, indent=2))
        
        # Find generic alternatives
        print("\nFinding generic alternatives for Lipitor...")
        alternatives = await client.find_generic_alternatives("Lipitor")
        print(json.dumps(alternatives, indent=2))
        
        # Find pharmacies
        print("\nFinding pharmacies in San Francisco...")
        pharmacies = await client.find_pharmacies(
            location="San Francisco, CA",
            radius_miles=3.0,
            medication_name="Lipitor"
        )
        print(json.dumps(pharmacies, indent=2))
        
        # Compare prices
        print("\nComparing Lipitor prices across pharmacy types...")
        comparison = await client.compare_prices(
            medication_name="Lipitor",
            dosage="20mg",
            quantity=30,
            pharmacy_types=["retail", "online"]
        )
        print(json.dumps(comparison, indent=2))
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main()) 
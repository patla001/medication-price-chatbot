"""
Test script to demonstrate MCP functionality with caching and rate limiting.
"""

import asyncio
import json
from datetime import datetime
import aiohttp
from fastmcp import Client as MCPClient
from fastmcp.client.transports import AiohttpTransport

async def test_mcp_tools():
    """Test all MCP tools with various scenarios"""
    async with aiohttp.ClientSession() as session:
        transport = AiohttpTransport(session)
        client = MCPClient(transport=transport)
        client.base_url = "http://localhost:8000"
        
        try:
            print("\n=== Testing MCP Tools ===\n")
            
            # 1. Test search_medication_price
            print("1. Testing medication price search...")
            medications = [
                {"name": "Lipitor", "dosage": "20mg"},
                {"name": "Metformin", "dosage": "500mg"},
                {"name": "Amoxicillin", "dosage": "500mg"}
            ]
            
            for med in medications:
                print(f"\nSearching prices for {med['name']} {med['dosage']}...")
                try:
                    result = await client.execute_tool(
                        "search_medication_price",
                        {
                            "medication_name": med["name"],
                            "dosage": med["dosage"],
                            "location": "San Diego, CA"
                        }
                    )
                    print("Success! Found prices:")
                    for price in result["prices"][:3]:  # Show top 3 prices
                        print(f"- {price['pharmacy_name']}: ${price['price']:.2f}")
                except Exception as e:
                    print(f"Error: {str(e)}")
            
            # 2. Test find_generic_alternatives
            print("\n2. Testing generic alternatives search...")
            brand_names = ["Lipitor", "Prozac", "Nexium"]
            
            for brand in brand_names:
                print(f"\nFinding generic alternatives for {brand}...")
                try:
                    result = await client.execute_tool(
                        "find_generic_alternatives",
                        {"brand_name": brand}
                    )
                    print("Success! Found alternatives:")
                    for alt in result["alternatives"]:
                        print(f"- {alt['generic_name']} ({alt['manufacturer']})")
                except Exception as e:
                    print(f"Error: {str(e)}")
            
            # 3. Test find_pharmacies
            print("\n3. Testing pharmacy search...")
            locations = ["San Diego, CA", "Los Angeles, CA"]
            
            for location in locations:
                print(f"\nFinding pharmacies in {location}...")
                try:
                    result = await client.execute_tool(
                        "find_pharmacies",
                        {
                            "location": location,
                            "radius_miles": 5.0,
                            "medication_name": "Lipitor"
                        }
                    )
                    print("Success! Found pharmacies:")
                    for pharmacy in result["pharmacies"][:3]:  # Show top 3 pharmacies
                        print(f"- {pharmacy['name']} ({pharmacy['distance']:.1f} miles)")
                except Exception as e:
                    print(f"Error: {str(e)}")
            
            # 4. Test compare_prices
            print("\n4. Testing price comparison...")
            try:
                result = await client.execute_tool(
                    "compare_prices",
                    {
                        "medication_name": "Lipitor",
                        "dosage": "20mg",
                        "pharmacy_types": ["retail", "online", "discount"]
                    }
                )
                print("\nPrice comparison results:")
                for comparison in result["comparisons"]:
                    print(f"\n{comparison['pharmacy_type'].title()} Pharmacies:")
                    print(f"- Average: ${comparison['average_price']:.2f}")
                    print(f"- Lowest: ${comparison['lowest_price']:.2f}")
                    print(f"- Highest: ${comparison['highest_price']:.2f}")
                print(f"\nPotential savings: ${result['potential_savings']:.2f}")
            except Exception as e:
                print(f"Error: {str(e)}")
            
            # 5. Test caching
            print("\n5. Testing caching...")
            print("Making repeated requests to test cache...")
            
            for _ in range(3):
                try:
                    start_time = datetime.now()
                    result = await client.execute_tool(
                        "search_medication_price",
                        {
                            "medication_name": "Lipitor",
                            "dosage": "20mg",
                            "location": "San Diego, CA"
                        }
                    )
                    duration = (datetime.now() - start_time).total_seconds()
                    print(f"Request completed in {duration:.3f} seconds")
                except Exception as e:
                    print(f"Error: {str(e)}")
                await asyncio.sleep(0.1)
            
            # 6. Test rate limiting
            print("\n6. Testing rate limiting...")
            print("Making rapid requests to trigger rate limit...")
            
            tasks = []
            for _ in range(10):
                tasks.append(
                    client.execute_tool(
                        "search_medication_price",
                        {
                            "medication_name": "Lipitor",
                            "dosage": "20mg",
                            "location": "San Diego, CA"
                        }
                    )
                )
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            success_count = sum(1 for r in results if not isinstance(r, Exception))
            rate_limited = sum(1 for r in results if isinstance(r, Exception))
            
            print(f"Successful requests: {success_count}")
            print(f"Rate limited requests: {rate_limited}")
            
            # 7. Get MCP stats
            print("\n7. Getting MCP statistics...")
            try:
                async with session.get("http://localhost:8000/mcp/stats") as response:
                    stats = await response.json()
                    print("\nMCP Statistics:")
                    print(json.dumps(stats, indent=2))
            except Exception as e:
                print(f"Error getting stats: {str(e)}")
            
        finally:
            await session.close()

if __name__ == "__main__":
    asyncio.run(test_mcp_tools()) 
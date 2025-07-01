"""
Advanced usage examples for the Medication Price Comparison MCP tools.
"""

import asyncio
import json
from datetime import datetime
from typing import List, Dict, Any
from mcp_client import MCPClient
from errors import MCPToolError, MCPValidationError

async def find_best_price_with_alternatives(
    medication: str,
    location: str,
    max_price: float = None
) -> Dict[str, Any]:
    """
    Find the best price for a medication, including generic alternatives,
    and filter by maximum price if specified.
    """
    client = MCPClient()
    try:
        # Get brand name prices
        brand_results = await client.search_medication_price(
            medication_name=medication,
            location=location
        )
        
        # Get generic alternatives
        generic_results = await client.find_generic_alternatives(medication)
        
        # Compile all prices
        all_prices = []
        
        # Add brand name prices
        for price in brand_results["prices"]:
            if max_price is None or price["price"] <= max_price:
                all_prices.append({
                    "type": "brand",
                    "name": medication,
                    **price
                })
        
        # Add generic prices
        for alt in generic_results["alternatives"]:
            try:
                generic_prices = await client.search_medication_price(
                    medication_name=alt["generic_name"],
                    location=location
                )
                for price in generic_prices["prices"]:
                    if max_price is None or price["price"] <= max_price:
                        all_prices.append({
                            "type": "generic",
                            "name": alt["generic_name"],
                            **price
                        })
            except Exception:
                continue
        
        return {
            "all_options": sorted(all_prices, key=lambda x: x["price"]),
            "best_price": min(all_prices, key=lambda x: x["price"]) if all_prices else None,
            "total_options": len(all_prices),
            "search_timestamp": datetime.now().isoformat()
        }
    finally:
        await client.close()

async def analyze_pharmacy_coverage(location: str, radius_miles: float = 5.0) -> Dict[str, Any]:
    """
    Analyze pharmacy coverage in an area for common medications.
    """
    common_medications = [
        "Lisinopril",
        "Metformin",
        "Amlodipine",
        "Metoprolol",
        "Omeprazole"
    ]
    
    client = MCPClient()
    try:
        # Find pharmacies in the area
        pharmacies = await client.find_pharmacies(
            location=location,
            radius_miles=radius_miles
        )
        
        # Check medication availability
        coverage_data = {
            "pharmacies": len(pharmacies["pharmacies"]),
            "medications_checked": len(common_medications),
            "availability": {},
            "location": location,
            "radius_miles": radius_miles,
            "timestamp": datetime.now().isoformat()
        }
        
        for med in common_medications:
            try:
                prices = await client.search_medication_price(
                    medication_name=med,
                    location=location
                )
                
                coverage_data["availability"][med] = {
                    "available": len(prices["prices"]) > 0,
                    "pharmacy_count": len(prices["prices"]),
                    "price_range": {
                        "min": min(p["price"] for p in prices["prices"]) if prices["prices"] else None,
                        "max": max(p["price"] for p in prices["prices"]) if prices["prices"] else None
                    }
                }
            except Exception as e:
                coverage_data["availability"][med] = {
                    "error": str(e),
                    "available": False
                }
        
        return coverage_data
    finally:
        await client.close()

async def price_trend_analysis(
    medication: str,
    pharmacy_types: List[str] = ["retail", "online", "discount"]
) -> Dict[str, Any]:
    """
    Analyze price trends across different pharmacy types.
    """
    client = MCPClient()
    try:
        # Get price comparisons
        comparison = await client.compare_prices(
            medication_name=medication,
            pharmacy_types=pharmacy_types
        )
        
        # Calculate statistics
        analysis = {
            "medication": medication,
            "overall_statistics": {
                "average_price": comparison["overall_average"],
                "potential_savings": comparison["potential_savings"],
                "price_spread": max(
                    c["highest_price"] - c["lowest_price"]
                    for c in comparison["comparisons"]
                )
            },
            "by_pharmacy_type": {},
            "recommendations": []
        }
        
        # Analyze each pharmacy type
        for comp in comparison["comparisons"]:
            analysis["by_pharmacy_type"][comp["pharmacy_type"]] = {
                "average_price": comp["average_price"],
                "price_range": {
                    "low": comp["lowest_price"],
                    "high": comp["highest_price"]
                },
                "sample_size": comp["sample_size"]
            }
        
        # Generate recommendations
        cheapest_type = min(
            comparison["comparisons"],
            key=lambda x: x["average_price"]
        )
        
        analysis["recommendations"].append(
            f"Best prices found at {cheapest_type['pharmacy_type']} pharmacies "
            f"(average ${cheapest_type['average_price']:.2f})"
        )
        
        if analysis["overall_statistics"]["potential_savings"] > 50:
            analysis["recommendations"].append(
                f"High potential savings of ${analysis['overall_statistics']['potential_savings']:.2f} "
                "available by comparing prices"
            )
        
        return analysis
    finally:
        await client.close()

async def main():
    """Run example scenarios"""
    try:
        # Scenario 1: Find best price with alternatives
        print("\n1. Finding best price for Lipitor including generics...")
        best_price = await find_best_price_with_alternatives(
            medication="Lipitor",
            location="Chicago, IL",
            max_price=200.0
        )
        print(json.dumps(best_price, indent=2))
        
        # Scenario 2: Analyze pharmacy coverage
        print("\n2. Analyzing pharmacy coverage in San Francisco...")
        coverage = await analyze_pharmacy_coverage(
            location="San Francisco, CA",
            radius_miles=3.0
        )
        print(json.dumps(coverage, indent=2))
        
        # Scenario 3: Price trend analysis
        print("\n3. Analyzing price trends for Metformin...")
        trends = await price_trend_analysis(
            medication="Metformin",
            pharmacy_types=["retail", "online"]
        )
        print(json.dumps(trends, indent=2))
        
    except MCPToolError as e:
        print(f"Tool error: {e.message}")
    except MCPValidationError as e:
        print(f"Validation error: {e.message}")
        if e.validation_errors:
            print("Details:", json.dumps(e.validation_errors, indent=2))
    except Exception as e:
        print(f"Unexpected error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main()) 
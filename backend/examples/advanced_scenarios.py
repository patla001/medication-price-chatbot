"""
Advanced usage scenarios for the Medication Price Comparison MCP tools.
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any
from mcp_client import MCPClient
from errors import MCPToolError, MCPValidationError, MCPRateLimitError

async def medication_savings_analyzer(
    medications: List[Dict[str, str]],
    location: str,
    max_distance: float = 10.0
) -> Dict[str, Any]:
    """
    Analyze potential savings for multiple medications across different pharmacies,
    including generic alternatives and insurance considerations.
    
    Args:
        medications: List of dictionaries with medication details
        location: User's location
        max_distance: Maximum distance to search for pharmacies
    """
    client = MCPClient()
    try:
        analysis = {
            "total_savings": 0.0,
            "medications": {},
            "best_pharmacies": {},
            "recommendations": []
        }
        
        # Analyze each medication
        for med in medications:
            med_name = med["name"]
            dosage = med.get("dosage")
            quantity = med.get("quantity", 30)
            
            # Get brand name prices
            brand_prices = await client.search_medication_price(
                medication_name=med_name,
                dosage=dosage,
                location=location
            )
            
            # Find generic alternatives
            generics = await client.find_generic_alternatives(med_name)
            
            # Get prices for each generic alternative
            generic_prices = {}
            for alt in generics["alternatives"]:
                try:
                    prices = await client.search_medication_price(
                        medication_name=alt["generic_name"],
                        dosage=dosage,
                        location=location
                    )
                    generic_prices[alt["generic_name"]] = prices
                except Exception:
                    continue
            
            # Find local pharmacies
            pharmacies = await client.find_pharmacies(
                location=location,
                radius_miles=max_distance,
                medication_name=med_name
            )
            
            # Calculate potential savings
            brand_min = min(p["price"] for p in brand_prices["prices"]) if brand_prices["prices"] else float("inf")
            generic_min = float("inf")
            best_generic = None
            
            for generic_name, prices in generic_prices.items():
                if prices["prices"]:
                    min_price = min(p["price"] for p in prices["prices"])
                    if min_price < generic_min:
                        generic_min = min_price
                        best_generic = generic_name
            
            savings = brand_min - generic_min if generic_min < float("inf") else 0
            monthly_savings = savings * quantity
            annual_savings = monthly_savings * 12
            
            # Store analysis
            analysis["medications"][med_name] = {
                "brand_price_range": {
                    "min": brand_min if brand_min < float("inf") else None,
                    "max": max(p["price"] for p in brand_prices["prices"]) if brand_prices["prices"] else None
                },
                "best_generic": {
                    "name": best_generic,
                    "price": generic_min if generic_min < float("inf") else None
                },
                "potential_savings": {
                    "per_unit": savings if savings > 0 else 0,
                    "monthly": monthly_savings if savings > 0 else 0,
                    "annual": annual_savings if savings > 0 else 0
                },
                "available_pharmacies": len(pharmacies["pharmacies"])
            }
            
            analysis["total_savings"] += annual_savings
            
            # Generate recommendations
            if savings > 0:
                analysis["recommendations"].append(
                    f"Switch from {med_name} to {best_generic} to save "
                    f"${monthly_savings:.2f} per month"
                )
        
        # Find optimal pharmacy combinations
        all_pharmacies = set()
        for med_name, med_data in analysis["medications"].items():
            if med_data["available_pharmacies"] > 0:
                all_pharmacies.update(
                    p["name"] for p in (await client.find_pharmacies(
                        location=location,
                        radius_miles=max_distance,
                        medication_name=med_name
                    ))["pharmacies"]
                )
        
        # Score pharmacies based on availability and prices
        pharmacy_scores = {}
        for pharmacy in all_pharmacies:
            score = 0
            available_meds = 0
            for med_name in analysis["medications"]:
                try:
                    prices = await client.search_medication_price(
                        medication_name=med_name,
                        location=location
                    )
                    pharmacy_prices = [p for p in prices["prices"] if p["pharmacy_name"] == pharmacy]
                    if pharmacy_prices:
                        available_meds += 1
                        # Score based on price competitiveness
                        min_price = min(p["price"] for p in prices["prices"])
                        pharmacy_price = pharmacy_prices[0]["price"]
                        score += (1 - (pharmacy_price - min_price) / min_price) * 100
                except Exception:
                    continue
            
            if available_meds > 0:
                pharmacy_scores[pharmacy] = {
                    "score": score / available_meds,
                    "medications_available": available_meds
                }
        
        # Find best pharmacies
        analysis["best_pharmacies"] = dict(
            sorted(
                pharmacy_scores.items(),
                key=lambda x: (x[1]["medications_available"], x[1]["score"]),
                reverse=True
            )[:3]
        )
        
        # Add pharmacy recommendations
        best_pharmacy = max(
            pharmacy_scores.items(),
            key=lambda x: (x[1]["medications_available"], x[1]["score"])
        )[0]
        
        analysis["recommendations"].append(
            f"{best_pharmacy} offers the best overall value with "
            f"{pharmacy_scores[best_pharmacy]['medications_available']} medications available"
        )
        
        return analysis
    finally:
        await client.close()

async def price_monitoring_service(
    medications: List[Dict[str, str]],
    location: str,
    threshold_percent: float = 10.0,
    check_interval_hours: int = 24
) -> None:
    """
    Monitor medication prices and alert on significant changes.
    
    Args:
        medications: List of medications to monitor
        location: Location to check prices in
        threshold_percent: Alert threshold for price changes
        check_interval_hours: How often to check prices
    """
    client = MCPClient()
    try:
        # Initialize price history
        price_history = {}
        
        while True:
            for med in medications:
                med_name = med["name"]
                try:
                    # Get current prices
                    current_prices = await client.search_medication_price(
                        medication_name=med_name,
                        dosage=med.get("dosage"),
                        location=location
                    )
                    
                    if med_name not in price_history:
                        price_history[med_name] = []
                    
                    # Calculate average price
                    if current_prices["prices"]:
                        avg_price = sum(p["price"] for p in current_prices["prices"]) / len(current_prices["prices"])
                        
                        # Check for significant changes
                        if price_history[med_name]:
                            last_avg = price_history[med_name][-1]["average_price"]
                            change_percent = ((avg_price - last_avg) / last_avg) * 100
                            
                            if abs(change_percent) >= threshold_percent:
                                print(f"Alert: {med_name} price changed by {change_percent:.1f}%")
                                print(f"Previous average: ${last_avg:.2f}")
                                print(f"Current average: ${avg_price:.2f}")
                                print("Best current prices:")
                                for p in sorted(current_prices["prices"], key=lambda x: x["price"])[:3]:
                                    print(f"- {p['pharmacy_name']}: ${p['price']:.2f}")
                                print()
                        
                        # Store price history
                        price_history[med_name].append({
                            "timestamp": datetime.now().isoformat(),
                            "average_price": avg_price,
                            "min_price": min(p["price"] for p in current_prices["prices"]),
                            "max_price": max(p["price"] for p in current_prices["prices"]),
                            "sample_size": len(current_prices["prices"])
                        })
                        
                        # Keep only last 30 days of history
                        cutoff = datetime.now() - timedelta(days=30)
                        price_history[med_name] = [
                            ph for ph in price_history[med_name]
                            if datetime.fromisoformat(ph["timestamp"]) > cutoff
                        ]
                    
                except Exception as e:
                    print(f"Error monitoring {med_name}: {str(e)}")
            
            # Wait for next check
            await asyncio.sleep(check_interval_hours * 3600)
    finally:
        await client.close()

async def insurance_coverage_optimizer(
    medications: List[Dict[str, str]],
    insurance_plans: List[Dict[str, Any]],
    location: str
) -> Dict[str, Any]:
    """
    Analyze and optimize medication costs across different insurance plans.
    
    Args:
        medications: List of medications
        insurance_plans: List of insurance plan details
        location: Location for price checking
    """
    client = MCPClient()
    try:
        analysis = {
            "plans": {},
            "best_plan": None,
            "potential_savings": 0.0,
            "recommendations": []
        }
        
        for plan in insurance_plans:
            plan_name = plan["name"]
            monthly_premium = plan["monthly_premium"]
            annual_deductible = plan["annual_deductible"]
            copays = plan["copays"]
            
            plan_costs = {
                "premium_annual": monthly_premium * 12,
                "deductible": annual_deductible,
                "medication_costs": {},
                "total_annual_cost": monthly_premium * 12 + annual_deductible
            }
            
            # Calculate costs for each medication
            for med in medications:
                med_name = med["name"]
                quantity = med.get("quantity", 30)
                monthly_supply = med.get("monthly_supply", True)
                
                try:
                    # Get medication prices
                    prices = await client.search_medication_price(
                        medication_name=med_name,
                        dosage=med.get("dosage"),
                        location=location
                    )
                    
                    # Find generic alternatives
                    generics = await client.find_generic_alternatives(med_name)
                    
                    # Calculate costs
                    brand_cost = min(p["price"] for p in prices["prices"]) if prices["prices"] else float("inf")
                    generic_cost = float("inf")
                    
                    for alt in generics["alternatives"]:
                        try:
                            generic_prices = await client.search_medication_price(
                                medication_name=alt["generic_name"],
                                dosage=med.get("dosage"),
                                location=location
                            )
                            if generic_prices["prices"]:
                                generic_cost = min(
                                    generic_cost,
                                    min(p["price"] for p in generic_prices["prices"])
                                )
                        except Exception:
                            continue
                    
                    # Apply insurance coverage
                    brand_copay = copays.get("brand", brand_cost)
                    generic_copay = copays.get("generic", generic_cost)
                    
                    best_cost = min(brand_copay, generic_copay)
                    annual_cost = best_cost * (12 if monthly_supply else quantity)
                    
                    plan_costs["medication_costs"][med_name] = {
                        "monthly_cost": best_cost,
                        "annual_cost": annual_cost,
                        "better_with_generic": generic_copay < brand_copay
                    }
                    
                    plan_costs["total_annual_cost"] += annual_cost
                    
                except Exception as e:
                    print(f"Error analyzing {med_name} for {plan_name}: {str(e)}")
            
            analysis["plans"][plan_name] = plan_costs
        
        # Find best plan
        best_plan = min(
            analysis["plans"].items(),
            key=lambda x: x[1]["total_annual_cost"]
        )
        
        analysis["best_plan"] = {
            "name": best_plan[0],
            "annual_cost": best_plan[1]["total_annual_cost"]
        }
        
        # Calculate potential savings
        worst_plan = max(
            analysis["plans"].items(),
            key=lambda x: x[1]["total_annual_cost"]
        )
        
        analysis["potential_savings"] = (
            worst_plan[1]["total_annual_cost"] -
            best_plan[1]["total_annual_cost"]
        )
        
        # Generate recommendations
        analysis["recommendations"].append(
            f"Choose {best_plan[0]} for lowest annual cost of "
            f"${best_plan[1]['total_annual_cost']:.2f}"
        )
        
        if analysis["potential_savings"] > 1000:
            analysis["recommendations"].append(
                f"Potential annual savings of ${analysis['potential_savings']:.2f} "
                f"by switching from {worst_plan[0]} to {best_plan[0]}"
            )
        
        # Add medication-specific recommendations
        for med_name, costs in best_plan[1]["medication_costs"].items():
            if costs["better_with_generic"]:
                analysis["recommendations"].append(
                    f"Use generic version of {med_name} to save on copay"
                )
        
        return analysis
    finally:
        await client.close()

async def main():
    """Run advanced scenarios"""
    try:
        # Scenario 1: Medication Savings Analysis
        print("\n1. Analyzing medication savings...")
        medications = [
            {"name": "Lipitor", "dosage": "20mg", "quantity": 30},
            {"name": "Metformin", "dosage": "500mg", "quantity": 60},
            {"name": "Lisinopril", "dosage": "10mg", "quantity": 30}
        ]
        savings = await medication_savings_analyzer(
            medications=medications,
            location="Boston, MA",
            max_distance=5.0
        )
        print(json.dumps(savings, indent=2))
        
        # Scenario 2: Price Monitoring (run in background)
        print("\n2. Starting price monitoring...")
        monitor_task = asyncio.create_task(
            price_monitoring_service(
                medications=medications,
                location="Boston, MA",
                threshold_percent=5.0,
                check_interval_hours=1  # Short interval for demo
            )
        )
        
        # Scenario 3: Insurance Coverage Optimization
        print("\n3. Optimizing insurance coverage...")
        insurance_plans = [
            {
                "name": "Basic Plan",
                "monthly_premium": 200,
                "annual_deductible": 1000,
                "copays": {"generic": 10, "brand": 30}
            },
            {
                "name": "Premium Plan",
                "monthly_premium": 400,
                "annual_deductible": 500,
                "copays": {"generic": 5, "brand": 15}
            },
            {
                "name": "High Deductible Plan",
                "monthly_premium": 150,
                "annual_deductible": 2500,
                "copays": {"generic": 0, "brand": 0}
            }
        ]
        
        coverage = await insurance_coverage_optimizer(
            medications=medications,
            insurance_plans=insurance_plans,
            location="Boston, MA"
        )
        print(json.dumps(coverage, indent=2))
        
        # Let price monitoring run for a bit
        await asyncio.sleep(3600)  # Run for 1 hour
        monitor_task.cancel()
        
    except MCPToolError as e:
        print(f"Tool error: {e.message}")
    except MCPValidationError as e:
        print(f"Validation error: {e.message}")
    except MCPRateLimitError as e:
        print(f"Rate limit error: {e.message}")
    except Exception as e:
        print(f"Unexpected error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main()) 
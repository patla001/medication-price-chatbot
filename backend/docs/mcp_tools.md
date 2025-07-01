# Medication Price Comparison MCP Tools

This document describes the Model Context Protocol (MCP) tools available in the Medication Price Comparison Chatbot.

## Table of Contents
- [Overview](#overview)
- [Authentication](#authentication)
- [Error Handling](#error-handling)
- [Tools](#tools)
  - [search_medication_price](#search_medication_price)
  - [find_generic_alternatives](#find_generic_alternatives)
  - [find_pharmacies](#find_pharmacies)
  - [compare_prices](#compare_prices)
- [Examples](#examples)

## Overview

The MCP tools provide standardized access to medication price comparison functionality. Each tool follows the MCP specification and returns structured data.

Base URL: `http://localhost:8000/mcp`

## Authentication

Currently, the API does not require authentication. Future versions may implement API key authentication.

## Error Handling

The API uses standard HTTP status codes and returns errors in the following format:

```json
{
  "error": "Error message",
  "type": "ErrorType"
}
```

Common error types:
- `MCPToolError`: Tool-specific errors (400)
- `ValidationError`: Invalid input data (422)
- `ServerError`: Internal server errors (500)

## Tools

### search_medication_price

Search for medication prices across multiple pharmacies.

**Endpoint**: `/tools/search_medication_price`

**Input**:
```json
{
  "medication_name": "string",
  "dosage": "string (optional)",
  "location": "string (optional)"
}
```

**Output**:
```json
{
  "prices": [
    {
      "pharmacy_name": "string",
      "price": "number",
      "location": "string",
      "website": "string (optional)",
      "last_updated": "string (ISO date)"
    }
  ],
  "search_query": "string"
}
```

**Example**:
```python
response = await client.search_medication_price(
    medication_name="Lipitor",
    dosage="20mg",
    location="New York, NY"
)
```

### find_generic_alternatives

Find generic alternatives for brand-name medications.

**Endpoint**: `/tools/find_generic_alternatives`

**Input**:
```json
{
  "brand_name": "string",
  "include_prices": "boolean (default: true)"
}
```

**Output**:
```json
{
  "alternatives": [
    {
      "generic_name": "string",
      "brand_name": "string",
      "price_savings": "number (optional)",
      "availability": "string",
      "equivalent_dosage": "string (optional)"
    }
  ],
  "search_query": "string"
}
```

**Example**:
```python
response = await client.find_generic_alternatives(
    brand_name="Lipitor",
    include_prices=True
)
```

### find_pharmacies

Find pharmacies in a specific location with optional medication availability check.

**Endpoint**: `/tools/find_pharmacies`

**Input**:
```json
{
  "location": "string",
  "radius_miles": "number (default: 5.0)",
  "medication_name": "string (optional)"
}
```

**Output**:
```json
{
  "pharmacies": [
    {
      "name": "string",
      "address": "string",
      "distance": "number",
      "phone": "string (optional)",
      "hours": "string (optional)",
      "has_medication": "boolean (optional)"
    }
  ],
  "search_query": "string"
}
```

**Example**:
```python
response = await client.find_pharmacies(
    location="San Francisco, CA",
    radius_miles=3.0,
    medication_name="Lipitor"
)
```

### compare_prices

Compare medication prices across different types of pharmacies.

**Endpoint**: `/tools/compare_prices`

**Input**:
```json
{
  "medication_name": "string",
  "dosage": "string (optional)",
  "quantity": "integer (optional)",
  "pharmacy_types": ["retail" | "online" | "discount"]
}
```

**Output**:
```json
{
  "comparisons": [
    {
      "pharmacy_type": "string",
      "average_price": "number",
      "lowest_price": "number",
      "highest_price": "number",
      "sample_size": "integer"
    }
  ],
  "overall_average": "number",
  "potential_savings": "number",
  "search_query": "string"
}
```

**Example**:
```python
response = await client.compare_prices(
    medication_name="Lipitor",
    dosage="20mg",
    quantity=30,
    pharmacy_types=["retail", "online"]
)
```

## Examples

### Complete Price Analysis

```python
async def analyze_medication_prices(medication: str, location: str):
    client = MCPClient()
    try:
        # Get brand name prices
        brand_prices = await client.search_medication_price(
            medication_name=medication,
            location=location
        )
        
        # Find generic alternatives
        generics = await client.find_generic_alternatives(medication)
        
        # Find local pharmacies
        pharmacies = await client.find_pharmacies(
            location=location,
            medication_name=medication
        )
        
        # Compare prices across pharmacy types
        comparison = await client.compare_prices(
            medication_name=medication,
            pharmacy_types=["retail", "online", "discount"]
        )
        
        return {
            "brand_prices": brand_prices,
            "generic_alternatives": generics,
            "local_pharmacies": pharmacies,
            "price_comparison": comparison
        }
    finally:
        await client.close()
```

### Error Handling Example

```python
async def safe_price_search(medication: str):
    client = MCPClient()
    try:
        return await client.search_medication_price(medication_name=medication)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400:
            print(f"Invalid request: {e.response.json()['error']}")
        elif e.response.status_code == 422:
            print(f"Validation error: {e.response.json()['error']}")
        else:
            print(f"Server error: {e.response.status_code}")
        return None
    except httpx.RequestError:
        print("Network error occurred")
        return None
    finally:
        await client.close()
```

### Batch Processing Example

```python
async def batch_price_check(medications: list, location: str):
    client = MCPClient()
    results = {}
    try:
        for med in medications:
            try:
                price_data = await client.search_medication_price(
                    medication_name=med,
                    location=location
                )
                results[med] = price_data
            except Exception as e:
                results[med] = {"error": str(e)}
        return results
    finally:
        await client.close()
``` 
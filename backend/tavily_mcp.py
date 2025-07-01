from tavily import TavilyClient
from typing import Optional, List, Dict, Any
import asyncio
import json

class TavilyMCPServer:
    """
    A wrapper around the Tavily API specifically for medication price comparison functionality.
    This class provides methods for searching medication prices, finding generic alternatives,
    and other medication-related information.
    """
    
    def __init__(self, api_key: str):
        self.client = TavilyClient(api_key=api_key)
        
    async def search(self, query: str, search_depth: str = "basic", max_results: int = 5,
                    include_domains: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Perform a medication-focused search using Tavily's API.
        
        Args:
            query: The search query string
            search_depth: The depth of the search ("basic" or "full")
            max_results: Maximum number of results to return
            include_domains: Optional list of domains to include in the search
            
        Returns:
            Dict containing search results and metadata
        """
        try:
            search_params = {
                "query": query,
                "search_depth": search_depth,
                "max_results": max_results,
                "include_answer": True,
                "include_raw_content": True,
            }
            
            if include_domains:
                search_params["include_domains"] = include_domains
                
            # Run the synchronous client in a thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: self.client.search(**search_params))
            return result
        except Exception as e:
            raise Exception(f"Error in Tavily search: {str(e)}")
            
    async def get_content(self, url: str) -> Dict[str, Any]:
        """
        Extract content from a URL using Tavily's API.
        
        Args:
            url: The URL to extract content from
            
        Returns:
            Dict containing the extracted content and metadata
        """
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: self.client.get_content(url=url))
            return result
        except Exception as e:
            raise Exception(f"Error in Tavily content extraction: {str(e)}")
            
    async def search_medication_prices(self, medication_name: str, location: Optional[str] = None,
                                     pharmacy_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Search for medication prices using a specialized query.
        
        Args:
            medication_name: Name of the medication
            location: Optional location to search in
            pharmacy_type: Optional type of pharmacy (retail, online, discount)
            
        Returns:
            Dict containing price information and search metadata
        """
        query_parts = [f"{medication_name} price"]
        if location:
            query_parts.append(f"in {location}")
        if pharmacy_type:
            query_parts.append(f"at {pharmacy_type} pharmacies")
            
        query = " ".join(query_parts)
        
        # Use pharmacy-specific domains for better results
        pharmacy_domains = [
            "goodrx.com",
            "wellrx.com",
            "drugs.com",
            "rxsaver.com",
            "singlecare.com",
            "needymeds.org"
        ]
        
        result = await self.search(
            query=query,
            search_depth="full",
            include_domains=pharmacy_domains
        )
        
        return result 
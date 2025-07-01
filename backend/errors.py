"""
Error handling utilities for the Medication Price Comparison Chatbot.
"""

from typing import Optional, Dict, Any
from fastapi import HTTPException
from pydantic import ValidationError

class MCPBaseError(Exception):
    """Base error class for MCP tools"""
    def __init__(self, message: str, error_type: str = "MCPError", status_code: int = 400):
        self.message = message
        self.error_type = error_type
        self.status_code = status_code
        super().__init__(self.message)

class MCPToolError(MCPBaseError):
    """Error raised by MCP tools during execution"""
    def __init__(self, message: str, tool_name: Optional[str] = None):
        super().__init__(
            message=message,
            error_type="MCPToolError",
            status_code=400
        )
        self.tool_name = tool_name

class MCPValidationError(MCPBaseError):
    """Error raised during input validation"""
    def __init__(self, message: str, validation_errors: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_type="MCPValidationError",
            status_code=422
        )
        self.validation_errors = validation_errors or {}

class MCPAuthenticationError(MCPBaseError):
    """Error raised during authentication"""
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            error_type="MCPAuthenticationError",
            status_code=401
        )

class MCPRateLimitError(MCPBaseError):
    """Error raised when rate limit is exceeded"""
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(
            message=message,
            error_type="MCPRateLimitError",
            status_code=429
        )

class MCPDependencyError(MCPBaseError):
    """Error raised when an external dependency fails"""
    def __init__(self, message: str, dependency_name: str):
        super().__init__(
            message=f"{dependency_name} error: {message}",
            error_type="MCPDependencyError",
            status_code=502
        )
        self.dependency_name = dependency_name

def handle_validation_error(error: ValidationError) -> MCPValidationError:
    """Convert Pydantic validation error to MCP validation error"""
    errors = {}
    for e in error.errors():
        location = " -> ".join(str(loc) for loc in e["loc"])
        errors[location] = e["msg"]
    
    return MCPValidationError(
        message="Validation error",
        validation_errors=errors
    )

def handle_http_error(status_code: int, detail: str) -> MCPBaseError:
    """Convert HTTP error to MCP error"""
    error_mappings = {
        400: MCPToolError,
        401: MCPAuthenticationError,
        422: MCPValidationError,
        429: MCPRateLimitError,
        502: MCPDependencyError
    }
    
    error_class = error_mappings.get(status_code, MCPBaseError)
    return error_class(message=detail)

def format_error_response(error: Exception) -> Dict[str, Any]:
    """Format error for API response"""
    if isinstance(error, MCPBaseError):
        response = {
            "error": error.message,
            "type": error.error_type
        }
        
        # Add additional error details if available
        if isinstance(error, MCPValidationError) and error.validation_errors:
            response["validation_errors"] = error.validation_errors
        elif isinstance(error, MCPToolError) and error.tool_name:
            response["tool"] = error.tool_name
        elif isinstance(error, MCPDependencyError):
            response["dependency"] = error.dependency_name
        
        return response
    
    # Handle unknown errors
    return {
        "error": str(error),
        "type": "ServerError"
    }

# Error handling decorators
def handle_mcp_errors(func):
    """Decorator to handle MCP errors in async functions"""
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except ValidationError as e:
            raise handle_validation_error(e)
        except HTTPException as e:
            raise handle_http_error(e.status_code, e.detail)
        except Exception as e:
            if not isinstance(e, MCPBaseError):
                raise MCPToolError(str(e))
            raise
    return wrapper 
"""
Unit tests for error handling module.
"""

import pytest
from pydantic import BaseModel, ValidationError
from fastapi import HTTPException
from errors import (
    MCPBaseError,
    MCPToolError,
    MCPValidationError,
    MCPAuthenticationError,
    MCPRateLimitError,
    MCPDependencyError,
    handle_validation_error,
    handle_http_error,
    format_error_response,
    handle_mcp_errors
)

# Test models
class TestInput(BaseModel):
    name: str
    age: int

# Test functions
@handle_mcp_errors
async def test_function_success():
    return {"status": "success"}

@handle_mcp_errors
async def test_function_validation_error():
    # This will raise a ValidationError
    TestInput(name="test", age="not_an_int")

@handle_mcp_errors
async def test_function_tool_error():
    raise MCPToolError("Tool failed")

# Tests
def test_mcp_base_error():
    """Test MCPBaseError creation and attributes"""
    error = MCPBaseError("Test error", "TestError", 400)
    assert error.message == "Test error"
    assert error.error_type == "TestError"
    assert error.status_code == 400
    assert str(error) == "Test error"

def test_mcp_tool_error():
    """Test MCPToolError creation and attributes"""
    error = MCPToolError("Tool failed", "test_tool")
    assert error.message == "Tool failed"
    assert error.tool_name == "test_tool"
    assert error.error_type == "MCPToolError"
    assert error.status_code == 400

def test_mcp_validation_error():
    """Test MCPValidationError creation and attributes"""
    validation_errors = {"field": "error message"}
    error = MCPValidationError("Validation failed", validation_errors)
    assert error.message == "Validation failed"
    assert error.validation_errors == validation_errors
    assert error.error_type == "MCPValidationError"
    assert error.status_code == 422

def test_mcp_authentication_error():
    """Test MCPAuthenticationError creation and attributes"""
    error = MCPAuthenticationError()
    assert error.message == "Authentication failed"
    assert error.error_type == "MCPAuthenticationError"
    assert error.status_code == 401

def test_mcp_rate_limit_error():
    """Test MCPRateLimitError creation and attributes"""
    error = MCPRateLimitError("Too many requests")
    assert error.message == "Too many requests"
    assert error.error_type == "MCPRateLimitError"
    assert error.status_code == 429

def test_mcp_dependency_error():
    """Test MCPDependencyError creation and attributes"""
    error = MCPDependencyError("API unavailable", "ExternalAPI")
    assert error.message == "ExternalAPI error: API unavailable"
    assert error.dependency_name == "ExternalAPI"
    assert error.error_type == "MCPDependencyError"
    assert error.status_code == 502

@pytest.mark.asyncio
async def test_handle_mcp_errors_success():
    """Test handle_mcp_errors decorator with successful function"""
    result = await test_function_success()
    assert result == {"status": "success"}

@pytest.mark.asyncio
async def test_handle_mcp_errors_validation():
    """Test handle_mcp_errors decorator with validation error"""
    with pytest.raises(MCPValidationError) as exc_info:
        await test_function_validation_error()
    assert exc_info.value.status_code == 422

@pytest.mark.asyncio
async def test_handle_mcp_errors_tool_error():
    """Test handle_mcp_errors decorator with tool error"""
    with pytest.raises(MCPToolError) as exc_info:
        await test_function_tool_error()
    assert exc_info.value.message == "Tool failed"

def test_handle_validation_error():
    """Test validation error handling"""
    try:
        TestInput(name="test", age="not_an_int")
    except ValidationError as e:
        error = handle_validation_error(e)
        assert isinstance(error, MCPValidationError)
        assert error.status_code == 422
        assert "validation_errors" in error.__dict__

def test_handle_http_error():
    """Test HTTP error handling"""
    http_error = HTTPException(status_code=400, detail="Bad request")
    error = handle_http_error(http_error.status_code, http_error.detail)
    assert isinstance(error, MCPToolError)
    assert error.status_code == 400
    assert error.message == "Bad request"

def test_format_error_response():
    """Test error response formatting"""
    # Test MCPToolError formatting
    tool_error = MCPToolError("Tool failed", "test_tool")
    response = format_error_response(tool_error)
    assert response == {
        "error": "Tool failed",
        "type": "MCPToolError",
        "tool": "test_tool"
    }
    
    # Test MCPValidationError formatting
    validation_error = MCPValidationError(
        "Validation failed",
        {"field": "error message"}
    )
    response = format_error_response(validation_error)
    assert response == {
        "error": "Validation failed",
        "type": "MCPValidationError",
        "validation_errors": {"field": "error message"}
    }
    
    # Test unknown error formatting
    unknown_error = Exception("Unknown error")
    response = format_error_response(unknown_error)
    assert response == {
        "error": "Unknown error",
        "type": "ServerError"
    }

def test_error_inheritance():
    """Test error class inheritance"""
    assert issubclass(MCPToolError, MCPBaseError)
    assert issubclass(MCPValidationError, MCPBaseError)
    assert issubclass(MCPAuthenticationError, MCPBaseError)
    assert issubclass(MCPRateLimitError, MCPBaseError)
    assert issubclass(MCPDependencyError, MCPBaseError) 
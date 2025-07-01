#!/bin/bash

# Start Tavily MCP server in the background
echo "Starting Tavily MCP server..."
env TAVILY_API_KEY="$TAVILY_API_KEY" npx -y tavily-mcp@0.1.3 --port 8000 &
TAVILY_PID=$!

# Wait a moment for Tavily MCP server to start
sleep 2

# Start the backend server
echo "Starting backend server..."
cd backend && uvicorn main:app --reload --port 8000

# Cleanup when the script is terminated
trap 'kill $TAVILY_PID' EXIT 
import { useState, useEffect } from 'react'
import { Beaker, ChevronDown, ChevronUp } from 'lucide-react'

interface McpTool {
  name: string
  description: string
  input_schema: any
  output_schema: any
}

export default function McpToolTester() {
  const [tools, setTools] = useState<McpTool[]>([])
  const [selectedTool, setSelectedTool] = useState<string>('')
  const [inputValues, setInputValues] = useState<Record<string, any>>({})
  const [result, setResult] = useState<any>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isExpanded, setIsExpanded] = useState(false)

  useEffect(() => {
    fetchTools()
  }, [])

  const fetchTools = async () => {
    try {
      const response = await fetch('http://localhost:8000/mcp/tools/list', {
        method: 'POST',
      })
      const data = await response.json()
      setTools(data.tools)
    } catch (error) {
      console.error('Error fetching MCP tools:', error)
    }
  }

  const handleToolSelect = (toolName: string) => {
    setSelectedTool(toolName)
    setInputValues({})
    setResult(null)
  }

  const handleInputChange = (key: string, value: any) => {
    setInputValues(prev => ({ ...prev, [key]: value }))
  }

  const executeTool = async () => {
    setIsLoading(true)
    try {
      const response = await fetch(`http://localhost:8000/mcp/tools/${selectedTool}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(inputValues),
      })
      const data = await response.json()
      setResult(data)
    } catch (error) {
      console.error('Error executing MCP tool:', error)
      setResult({ error: 'Failed to execute tool' })
    }
    setIsLoading(false)
  }

  const getInputFields = (tool: McpTool) => {
    const properties = tool.input_schema.properties
    return Object.entries(properties).map(([key, schema]: [string, any]) => (
      <div key={key} className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-1">
          {schema.title || key}
          {schema.description && (
            <span className="text-xs text-gray-500 ml-1">({schema.description})</span>
          )}
        </label>
        {schema.type === 'string' && (
          <input
            type="text"
            value={inputValues[key] || ''}
            onChange={(e) => handleInputChange(key, e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        )}
        {schema.type === 'number' && (
          <input
            type="number"
            value={inputValues[key] || ''}
            onChange={(e) => handleInputChange(key, parseFloat(e.target.value))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        )}
        {schema.type === 'boolean' && (
          <input
            type="checkbox"
            checked={inputValues[key] || false}
            onChange={(e) => handleInputChange(key, e.target.checked)}
            className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
          />
        )}
      </div>
    ))
  }

  if (!isExpanded) {
    return (
      <button
        onClick={() => setIsExpanded(true)}
        className="flex items-center space-x-2 bg-primary-50 text-primary-700 px-4 py-2 rounded-lg hover:bg-primary-100 transition-colors"
      >
        <Beaker className="w-4 h-4" />
        <span>Show MCP Tool Tester</span>
        <ChevronDown className="w-4 h-4" />
      </button>
    )
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-6 mb-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <Beaker className="w-5 h-5 text-primary-500" />
          <h2 className="text-lg font-semibold">MCP Tool Tester</h2>
        </div>
        <button
          onClick={() => setIsExpanded(false)}
          className="text-gray-500 hover:text-gray-700"
        >
          <ChevronUp className="w-4 h-4" />
        </button>
      </div>

      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Select Tool
        </label>
        <select
          value={selectedTool}
          onChange={(e) => handleToolSelect(e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
        >
          <option value="">Choose a tool...</option>
          {tools.map((tool) => (
            <option key={tool.name} value={tool.name}>
              {tool.name}
            </option>
          ))}
        </select>
      </div>

      {selectedTool && tools.length > 0 && (
        <div>
          <div className="mb-4">
            <p className="text-sm text-gray-600">
              {tools.find(t => t.name === selectedTool)?.description}
            </p>
          </div>

          {getInputFields(tools.find(t => t.name === selectedTool)!)}

          <button
            onClick={executeTool}
            disabled={isLoading}
            className="w-full bg-primary-500 text-white py-2 px-4 rounded-md hover:bg-primary-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isLoading ? 'Executing...' : 'Execute Tool'}
          </button>

          {result && (
            <div className="mt-4">
              <h3 className="text-sm font-medium text-gray-700 mb-2">Result:</h3>
              <pre className="bg-gray-50 p-4 rounded-md overflow-x-auto text-sm">
                {JSON.stringify(result, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
} 
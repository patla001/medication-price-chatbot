import React, { useState, useRef, useEffect } from 'react'
import { Send, Search, Pill, MapPin, RefreshCw, Lightbulb } from 'lucide-react'
import ChatMessage from './ChatMessage'
import PriceCard from './PriceCard'
import TypingIndicator from './TypingIndicator'

interface Pharmacy {
  name: string;
  type?: string;
  price?: number;
  address?: string;
  phone?: string;
  website?: string;
  delivery_info?: string;
  has_medication?: boolean;
  last_updated?: string;
  hours?: string;
  distance?: number;
  accuracy?: string;
  accuracy_type?: string;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
  pharmacies?: Pharmacy[];
}

interface Coordinates {
  latitude: number;
  longitude: number;
}

interface MedicationPrice {
  pharmacy_name: string
  price: number
  location: string
  distance?: string
  phone?: string
  website?: string
  in_stock: boolean
  last_updated: string
}

interface ErrorState {
  message: string;
  suggestions?: string[];
}

export default function McpChatbot() {
  const [messages, setMessages] = useState<Message[]>([{
    role: 'assistant',
    content: 'Hello! I can help you find medication prices and compare costs across different pharmacies. What medication would you like to search for?'
  }])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [userLocation, setUserLocation] = useState<Coordinates | null>(null)
  const [locationError, setLocationError] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const [lastSearchedMedication, setLastSearchedMedication] = useState('')
  const [error, setError] = useState<ErrorState | null>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    // Get user's location when component mounts
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          setUserLocation({
            latitude: position.coords.latitude,
            longitude: position.coords.longitude
          });
          setLocationError(null);
        },
        (error) => {
          console.error('Error getting location:', error);
          setLocationError('Unable to get your location. Please enter your location manually.');
        }
      );
    } else {
      setLocationError('Geolocation is not supported by your browser.');
    }
  }, []);

  const addMessage = (message: Message) => {
    setMessages(prev => [...prev, message])
  }

  const handleSearch = async (query: string) => {
    setIsLoading(true)
    setError(null)

    try {
      // Extract medication name and location from query with improved logic
      let medicationName = '';
      let location = '';
      
      // Handle different query patterns
      const lowerQuery = query.toLowerCase();
      
      if (lowerQuery.includes(' near ')) {
        const parts = lowerQuery.split(' near ');
        medicationName = parts[0].replace(/^find\s+/, '').trim();
        location = parts[1].trim();
      } else if (lowerQuery.includes(' in ')) {
        const parts = lowerQuery.split(' in ');
        medicationName = parts[0].replace(/^find\s+/, '').trim();
        location = parts[1].trim();
      } else if (lowerQuery.includes(' at ')) {
        const parts = lowerQuery.split(' at ');
        medicationName = parts[0].replace(/^find\s+/, '').trim();
        location = parts[1].trim();
      } else {
        // No location specified
        medicationName = lowerQuery.replace(/^find\s+/, '').trim();
        location = '';
      }
      
      // Determine if this is an online search
      const isOnlineSearch = !location || location === 'online' || query.toLowerCase().includes('online')
      
      const response = await fetch('/api/mcp/tools/find_pharmacies', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          medication_name: medicationName,
          location: location,
          search_type: isOnlineSearch ? 'online' : 'local'
        }),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail?.error || errorData.detail || 'Failed to find pharmacies')
      }

      const data = await response.json()
      
      // Filter pharmacies to only include those with addresses for local search
      const validPharmacies = isOnlineSearch 
        ? (data.pharmacies as Pharmacy[]) 
        : (data.pharmacies as Pharmacy[])?.filter((p: Pharmacy) => p.address) || []
      
      // Add pharmacy results to chat
      const newMessage: Message = {
        role: 'assistant',
        content: data.search_query,
      }

      if (validPharmacies.length > 0) {
        newMessage.content += `\n\nI found ${validPharmacies.length} pharmacies that may have ${medicationName}:`
        newMessage.pharmacies = validPharmacies
      } else {
        newMessage.content += '\n\nI couldn\'t find any pharmacies. Here are some suggestions:\n\n'
        newMessage.content += (data.suggestions || [
          'Try searching with a different location',
          'Search for online pharmacies instead',
          'Check if the medication name is spelled correctly'
        ]).map((s: string) => `- ${s}`).join('\n')
      }

      setMessages(prev => [...prev, { role: 'user', content: query }, newMessage])
    } catch (error) {
      console.error('Error in handleSearch:', error)
      setError({
        message: error instanceof Error ? error.message : 'An error occurred',
        suggestions: [
          'Please try again in a few moments',
          'Check your internet connection',
          'Try searching with different terms'
        ]
      })
    } finally {
      setIsLoading(false)
    }
  }

  const handleGenericAlternatives = async (medication: string) => {
    try {
      setIsLoading(true);
      const response = await fetch('/api/mcp/tools/find_generic_alternatives', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          medication_name: medication,
        }),
      });

      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.error || `Error: ${response.status}`);
      }

      if (!data.alternatives || data.alternatives.length === 0) {
        addMessage({
          role: 'assistant',
          content: `I couldn't find any generic alternatives for "${medication}". This might be because:

1. The medication is already a generic drug
2. The patent hasn't expired yet
3. No generic version is currently available

Would you like to:
1. Search for a different medication?
2. Compare prices for ${medication}?
3. Get more information about ${medication}?`,
        });
        return;
      }

      // Add a message with the alternatives
      let content = `Here are the generic alternatives I found for ${medication}:\n\n`;
      data.alternatives.forEach((alt: any) => {
        content += `• ${alt.generic_name}`;
        if (alt.estimated_savings) {
          content += ` (potential savings: $${alt.estimated_savings.toFixed(2)})`;
        }
        content += '\n';
      });

      content += '\nWould you like to:\n';
      content += '1. Compare prices for any of these alternatives?\n';
      content += '2. Get more information about a specific alternative?\n';
      content += '3. Search for a different medication?\n';

      addMessage({
        role: 'assistant',
        content,
      });

    } catch (error) {
      console.error('Error finding generic alternatives:', error);
      addMessage({
        role: 'assistant',
        content: `Sorry, I encountered an error while searching for generic alternatives: ${error instanceof Error ? error.message : 'Unknown error'}. Please try again.`,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleMedicationInfo = async (medication: string) => {
    try {
      setIsLoading(true);
      const response = await fetch('/api/mcp/tools/get_medication_info', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          medication_name: medication,
        }),
      });

      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.error || `Error: ${response.status}`);
      }

      if (!data.info || !data.info.uses) {
        addMessage({
          role: 'assistant',
          content: `I couldn't find detailed information about "${medication}". Would you like to:

1. Try searching with a different spelling?
2. Search for a different medication?
3. Compare prices for ${medication}?`,
        });
        return;
      }

      // Add a message with the medication information
      let content = `Here's what I found about ${medication}:\n\n`;
      
      if (data.info.uses.length > 0) {
        content += '**Uses:**\n';
        data.info.uses.forEach((use: string) => {
          content += `• ${use}\n`;
        });
        content += '\n';
      }

      if (data.info.dosage.length > 0) {
        content += '**Common Dosage:**\n';
        data.info.dosage.forEach((dose: string) => {
          content += `• ${dose}\n`;
        });
        content += '\n';
      }

      if (data.info.side_effects.length > 0) {
        content += '**Common Side Effects:**\n';
        data.info.side_effects.forEach((effect: string) => {
          content += `• ${effect}\n`;
        });
        content += '\n';
      }

      if (data.info.warnings.length > 0) {
        content += '**Important Warnings:**\n';
        data.info.warnings.forEach((warning: string) => {
          content += `• ${warning}\n`;
        });
        content += '\n';
      }

      if (data.info.sources.length > 0) {
        content += '\n*Information sourced from:*\n';
        data.info.sources.forEach((source: string) => {
          content += `• ${source}\n`;
        });
      }

      content += '\nWould you like to:\n';
      content += '1. Compare prices for this medication?\n';
      content += '2. Find generic alternatives?\n';
      content += '3. Search for a different medication?\n';

      addMessage({
        role: 'assistant',
        content,
      });

    } catch (error) {
      console.error('Error getting medication information:', error);
      addMessage({
        role: 'assistant',
        content: `Sorry, I encountered an error while getting medication information: ${error instanceof Error ? error.message : 'Unknown error'}. Please try again.`,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleFindPharmacies = async (medication: string, location: string) => {
    try {
      setIsLoading(true);
      const response = await fetch('/api/mcp/tools/find_pharmacies', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          location: location,
          radius_miles: 5.0,
          medication_name: medication,
          coordinates: userLocation
        }),
      });

      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.error || `Error: ${response.status}`);
      }

      if (!data.pharmacies || data.pharmacies.length === 0) {
        addMessage({
          role: 'assistant',
          content: `I couldn't find any pharmacies near "${location}" that have "${medication}". Would you like to:

1. Try a different location?
2. Search for a different medication?
3. Compare online pharmacy prices instead?`,
        });
        return;
      }

      // Add a message with the pharmacy information
      addMessage({
        role: 'assistant',
        content: `Here are the pharmacies near ${location} that have ${medication}, sorted by distance:`,
        pharmacies: data.pharmacies
      });

      addMessage({
        role: 'assistant',
        content: `Would you like to:
1. Find pharmacies in a different location?
2. Search for a different medication?
3. Get more information about this medication?
4. Compare prices at other pharmacies?`
      });

    } catch (error) {
      console.error('Error finding pharmacies:', error);
      addMessage({
        role: 'assistant',
        content: `Sorry, I encountered an error while finding pharmacies: ${error instanceof Error ? error.message : 'Unknown error'}. Please try again.`,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleComparePrices = async (medication: string, dosage?: string) => {
    try {
      setIsLoading(true);
      const response = await fetch('/api/mcp/tools/compare_prices', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          medication_name: medication,
          dosage: dosage,
          pharmacy_types: ["retail", "online", "discount"],
        }),
      });

      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.error || `Error: ${response.status}`);
      }

      if (!data.comparisons || data.comparisons.length === 0) {
        // Use the message from backend if available, otherwise use default
        const message = data.message || `I couldn't find enough price data to compare prices for "${medication}". Would you like to:

1. Try searching with a different dosage?
2. Search for a different medication?
3. Find nearby pharmacies instead?`;
        
        addMessage({
          role: 'assistant',
          content: message,
        });
        return;
      }

      // Add a message with the price comparison
      let content = `Here's a price comparison for ${medication}${dosage ? ` ${dosage}` : ''}:\n\n`;
      
      data.comparisons.forEach((comparison: any) => {
        content += `**${comparison.pharmacy_type.charAt(0).toUpperCase() + comparison.pharmacy_type.slice(1)} Pharmacies**\n`;
        content += `• Average price: $${comparison.average_price.toFixed(2)}\n`;
        content += `• Lowest price: $${comparison.lowest_price.toFixed(2)}\n`;
        content += `• Highest price: $${comparison.highest_price.toFixed(2)}\n`;
        content += `• Based on ${comparison.sample_size} pharmacies\n\n`;
      });

      if (data.potential_savings > 0) {
        content += `**Potential savings:** $${data.potential_savings.toFixed(2)} by choosing the lowest-cost option\n\n`;
      }

      content += 'Would you like to:\n';
      content += '1. Find specific pharmacies with these prices?\n';
      content += '2. Look for generic alternatives?\n';
      content += '3. Search for a different medication?\n';

      addMessage({
        role: 'assistant',
        content,
      });

    } catch (error) {
      console.error('Error comparing prices:', error);
      addMessage({
        role: 'assistant',
        content: `Sorry, I encountered an error while comparing prices: ${error instanceof Error ? error.message : 'Unknown error'}. Please try again.`,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleMenuOption = (input: string) => {
    const normalizedInput = input.toLowerCase().trim();
    
    // Handle location-based search
    if (normalizedInput.includes('find local') || normalizedInput.includes('near me') || normalizedInput.includes('nearby')) {
      if (!lastSearchedMedication) {
        addMessage({
          role: 'assistant',
          content: 'Please search for a medication first before finding local pharmacies.',
        });
        return true;
      }
      
      if (userLocation) {
        handleSearch(input);
      } else {
        addMessage({
          role: 'assistant',
          content: 'Please enter your location (city and state or zip code) to find nearby pharmacies.',
        });
      }
      return true;
    }
    
    // Check if user is providing location after being asked
    const lastMessage = messages[messages.length - 1]?.content || '';
    if (lastMessage.includes('enter your location') && lastSearchedMedication) {
      handleSearch(input);
      return true;
    }
    
    if (normalizedInput.includes('compare prices') || normalizedInput.includes('different pharmacies')) {
      if (!lastSearchedMedication) {
        addMessage({
          role: 'assistant',
          content: 'Please search for a medication first before comparing prices.',
        });
        return true;
      }
      handleComparePrices(lastSearchedMedication);
      return true;
    }
    
    if (normalizedInput.includes('generic alternatives') || normalizedInput.includes('generic version')) {
      if (!lastSearchedMedication) {
        addMessage({
          role: 'assistant',
          content: 'Please search for a medication first before looking for generic alternatives.',
        });
        return true;
      }
      handleGenericAlternatives(lastSearchedMedication);
      return true;
    }
    
    if (normalizedInput.includes('different medication') || normalizedInput.includes('search for a different')) {
      addMessage({
        role: 'assistant',
        content: 'Sure! What medication would you like to search for?',
      });
      return true;
    }
    
    if (normalizedInput.includes('more information about')) {
      if (!lastSearchedMedication) {
        addMessage({
          role: 'assistant',
          content: 'Please search for a medication first before requesting more information.',
        });
        return true;
      }
      handleMedicationInfo(lastSearchedMedication);
      return true;
    }
    
    return false;
  };

  const extractMedicationFromQuery = (query: string): string => {
    // Common patterns for location-based queries
    const patterns = [
      /find (?:the )?nearest (?:pharmacy|location) for (.+)/i,
      /where can i (?:find|get|buy) (.+)/i,
      /pharmacies (?:near|around|close to) me (?:that have|with|selling) (.+)/i,
      /locate (.+) near me/i,
      /find (.+?) (?:in|near|at) .+/i,  // find [medication] in/near/at [location]
      /(.+?) (?:in|near|at) .+/i,       // [medication] in/near/at [location]
    ];

    for (const pattern of patterns) {
      const match = query.match(pattern);
      if (match) {
        return match[1].trim();
      }
    }

    // If no pattern matches, try to extract just the medication name
    const lowerQuery = query.toLowerCase();
    if (lowerQuery.includes(' in ') || lowerQuery.includes(' near ') || lowerQuery.includes(' at ')) {
      // Extract everything before the location preposition
      const parts = lowerQuery.split(/ (?:in|near|at) /);
      if (parts.length > 1) {
        return parts[0].replace(/^find\s+/, '').trim();
      }
    }

    // If still no match, return the original query with "find" removed
    return query.replace(/^find\s+/i, '').trim();
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim()) return;

    // Add user message
    addMessage({
      role: 'user',
      content: inputValue,
    });

    // Check if input matches any menu options
    if (!handleMenuOption(inputValue)) {
      // Check if it's a location-based query
      const isLocationQuery = /find|nearest|location|near|close|around|where/i.test(inputValue);
      const medicationName = extractMedicationFromQuery(inputValue);
      
      setLastSearchedMedication(medicationName);
      
      if (isLocationQuery) {
        // If we have user's location, use it directly
        if (userLocation) {
          handleSearch(inputValue);
        } else {
          // Ask for location if we don't have it
          addMessage({
            role: 'assistant',
            content: `To find ${medicationName} near you, I'll need your location. Please enter your city and state or zip code.`,
          });
        }
      } else {
        // Regular medication search
        handleSearch(inputValue);
      }
    }

    setInputValue('');
  };

  // Suggestion chips for user guidance
  const suggestionChips = [
    "find ibuprofen in San Diego, CA",
    "find generic alternatives for Advil",
    "compare prices for acetaminophen",
    "get medication info for aspirin",
    "find pharmacies near me with Tylenol"
  ];

  const handleSuggestionClick = (suggestion: string) => {
    setInputValue(suggestion);
  };

  return (
    <div className="max-w-4xl mx-auto p-4 min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
        <div className="flex items-center gap-3 mb-2">
          <div className="bg-blue-500 rounded-lg p-2">
            <Pill className="w-6 h-6 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Medication Price Finder</h1>
        </div>
        <p className="text-gray-600">Find the best prices for your medications at pharmacies near you.</p>
      </div>

      {/* Messages */}
      <div className="space-y-4 mb-6">
        {messages.map((message, index) => (
          <div
            key={index}
            className={`${
              message.role === 'assistant' ? 'bg-white' : 'bg-blue-50'
            } rounded-lg shadow-sm p-4`}
          >
            <div className="flex items-start gap-3">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                  message.role === 'assistant' ? 'bg-blue-500' : 'bg-gray-500'
                } text-white`}
              >
                {message.role === 'assistant' ? '🤖' : '👤'}
              </div>
              <div className="flex-1 min-w-0">
                <div className="whitespace-pre-wrap text-gray-800 leading-relaxed">
                  {message.content}
                </div>
                {message.pharmacies && message.pharmacies.length > 0 && (
                  <div className="mt-4 space-y-3">
                    {message.pharmacies.map((pharmacy: Pharmacy, idx) => {
                      // Only render pharmacy card if it has an address for local search
                      // or if it's an online pharmacy
                      if (!pharmacy.address && pharmacy.type !== 'Online Pharmacy') {
                        return null;
                      }
                      
                      return (
                        <PriceCard
                          key={`${pharmacy.name}-${idx}`}
                          pharmacy_name={pharmacy.name}
                          type={pharmacy.type}
                          price={pharmacy.price}
                          address={pharmacy.address}
                          phone={pharmacy.phone}
                          website={pharmacy.website}
                          delivery_info={pharmacy.delivery_info}
                          in_stock={pharmacy.has_medication}
                          last_updated={pharmacy.last_updated}
                          hours={pharmacy.hours}
                          distance={pharmacy.distance}
                          accuracy={pharmacy.accuracy}
                          accuracy_type={pharmacy.accuracy_type}
                        />
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
        
        {/* Loading indicator */}
        {isLoading && (
          <div className="bg-white rounded-lg shadow-sm p-4">
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-full flex items-center justify-center bg-blue-500 text-white">
                🤖
              </div>
              <div className="flex-1">
                <TypingIndicator />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Error display */}
      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 text-red-700 rounded-lg">
          <div className="font-semibold">{error.message}</div>
          {error.suggestions && error.suggestions.length > 0 && (
            <ul className="mt-2 list-disc list-inside space-y-1">
              {error.suggestions.map((suggestion, idx) => (
                <li key={idx}>{suggestion}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Suggestion chips - show only when no messages or last message is from assistant */}
      {(messages.length === 1 || messages[messages.length - 1]?.role === 'assistant') && !isLoading && (
        <div className="mb-6 bg-white rounded-lg shadow-sm p-4">
          <div className="flex items-center gap-2 mb-3">
            <Lightbulb className="w-4 h-4 text-yellow-500" />
            <span className="text-sm font-medium text-gray-700">Try asking:</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {suggestionChips.map((suggestion, idx) => (
              <button
                key={idx}
                onClick={() => handleSuggestionClick(suggestion)}
                className="px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-full transition-colors duration-200 border border-gray-200 hover:border-gray-300"
              >
                {suggestion}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input form */}
      <div className="bg-white rounded-lg shadow-sm p-4 sticky bottom-4">
        <form onSubmit={handleSubmit} className="flex gap-3">
          <div className="flex-1">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Ask about medication prices (e.g., 'find ibuprofen near San Diego, CA')"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              disabled={isLoading}
            />
          </div>
          <button
            type="submit"
            disabled={!inputValue.trim() || isLoading}
            className="px-6 py-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors duration-200 flex items-center gap-2 font-medium"
          >
            {isLoading ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
            <span className="hidden sm:inline">
              {isLoading ? 'Searching...' : 'Send'}
            </span>
          </button>
        </form>
        
        {/* Quick tips */}
        <div className="mt-3 text-xs text-gray-500">
          <div className="flex flex-wrap gap-4">
            <span>💡 Include location for local pharmacies</span>
            <span>🔍 Try "compare prices" for price analysis</span>
            <span>📋 Ask for "generic alternatives" to save money</span>
          </div>
        </div>
      </div>

      <div ref={messagesEndRef} />
    </div>
  );
} 
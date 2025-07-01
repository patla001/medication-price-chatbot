# Medication Price Comparison Chatbot

A modern AI-powered chatbot that helps users find the best prices for medications across different pharmacies using **Tavily's search API**, **FastMCP**, and **Model Context Protocol (MCP)**.

## 🚀 Features

### Core Functionality
- **AI-Powered Chat Interface**: Natural language queries with intelligent medication name extraction
- **Real-Time Price Comparison**: Uses [Tavily API](https://www.tavily.com/) to search current medication prices across 15+ domains
- **Smart Query Processing**: Handles complex queries like "find ibuprofen in San Diego, CA" with proper medication/location parsing
- **Multiple Pharmacy Support**: Compares prices across GoodRx, Walgreens, CVS, Costco, Walmart, SingleCare, Cost Plus Drugs, and more
- **Location-Based Search**: Find pharmacies and prices near you with address validation and distance calculation
- **Generic Alternatives**: Find cost-effective generic versions of brand-name medications
- **Medication Information**: Get detailed information about uses, dosage, side effects, and warnings

### Enhanced User Experience
- **Modern UI/UX**: Built with Next.js 14 and Tailwind CSS with professional design
- **Interactive Suggestions**: Click-to-use suggestion chips for common queries
- **Smart Loading States**: Visual feedback with typing indicators and loading animations
- **Professional Header**: Medication-themed branding with clear navigation
- **Responsive Design**: Works seamlessly on desktop and mobile devices
- **Error Handling**: Comprehensive error messages with helpful suggestions

### Advanced Backend Features
- **FastMCP Integration**: High-performance Model Context Protocol implementation
- **Smart Caching System**: TTL-based caching with automatic cleanup (2-hour cache for pharmacy data)
- **Rate Limiting**: Token bucket algorithm for API protection
- **Enhanced Price Extraction**: 20+ regex patterns for comprehensive price detection
- **Pharmacy Type Classification**: Automatic categorization (retail, online, discount)
- **Data Validation**: Address validation, price range filtering, and duplicate detection
- **Background Processing**: Efficient handling of multiple search queries

## 🏗️ Architecture

- **Frontend**: Next.js 14 with TypeScript, Tailwind CSS, and Lucide React icons
- **Backend**: Python FastAPI with Tavily integration and FastMCP server
- **AI Search**: Tavily API for real-time web search optimized for LLMs
- **Protocol**: FastMCP for high-performance AI-tool standardization
- **Caching**: TTL-based caching system for optimized performance
- **Rate Limiting**: Token bucket algorithm for API protection

## 🔧 Recent Improvements (v2.0)

### 🎯 Query Processing Enhancements
- **Fixed Medication Name Extraction**: Now correctly extracts "ibuprofen" from "find ibuprofen in San Diego, CA"
- **Multiple Query Patterns**: Supports "find X in Y", "find X near Y", "find X at Y" formats
- **Smart Location Parsing**: Properly separates medication names from location data
- **Context-Aware Processing**: Better understanding of user intent and query structure

### 💰 Price Comparison Overhaul
- **Enhanced Price Extraction**: 20+ regex patterns for different price formats:
  - Standard: `$4.99`, `4.99 dollars`
  - Promotional: `as low as $3.50`, `starting at $2.99`
  - Pharmacy-specific: `Walmart $4.88`, `CVS $12.99`
  - Range patterns: `$5.00-$15.00` (takes lower price)
  - Context-aware: `ibuprofen price $6.99`
- **Real Data Processing**: No more mock data - all results from live API searches
- **Price Validation**: Filters for reasonable medication prices ($0.50-$500.00)
- **Statistical Analysis**: Calculates averages, ranges, and potential savings
- **Pharmacy Categorization**: Groups results by retail, online, and discount pharmacies

### 🏪 Pharmacy Search Improvements
- **Address Validation**: Ensures complete street addresses for local pharmacies
- **Distance Calculation**: Accurate distance measurements using Haversine formula
- **Multiple Search Strategies**: Different query patterns for comprehensive results
- **Expanded Domain Coverage**: 15+ pharmacy domains for better results
- **Duplicate Detection**: Filters out duplicate pharmacy listings
- **Enhanced Metadata**: Phone numbers, hours, accuracy ratings, and delivery info

### 🎨 User Interface Enhancements
- **Professional Design**: Clean, medical-themed interface with proper branding
- **Interactive Elements**: Suggestion chips, loading states, and visual feedback
- **Smart Suggestions**: Context-aware suggestions that appear at appropriate times
- **Error Messaging**: Clear error messages with actionable suggestions
- **Accessibility**: Improved keyboard navigation and screen reader support
- **Mobile Optimization**: Responsive design that works on all devices

## 📋 Prerequisites

- Node.js 18+ and npm/pnpm
- Python 3.9+
- Tavily API key (sign up at [tavily.com](https://www.tavily.com/))

## 🛠️ Installation

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd medication-price-chatbot
```

### 2. Install Dependencies

```bash
# Install root dependencies
npm install

# Install frontend dependencies
cd frontend && pnpm install && cd ..

# Install backend dependencies
cd backend && pip install -r requirements.txt && cd ..
```

### 3. Set Up Environment Variables

Create a `.env` file in the `backend` directory:

```bash
cd backend
cp env.example .env
```

Edit the `.env` file and add your API key:

```env
# API Keys
TAVILY_API_KEY=your_tavily_api_key_here

# Server Configuration
HOST=localhost
PORT=8000
DEBUG=True

# CORS
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Cache Configuration
CACHE_TTL=7200  # 2 hours for pharmacy data
CACHE_CLEANUP_INTERVAL=300  # 5 minutes

# Rate Limiting
RATE_LIMIT_TOKENS=100
RATE_LIMIT_INTERVAL=60  # 1 minute
```

### 4. Get Your Tavily API Key

1. Visit [tavily.com](https://www.tavily.com/)
2. Sign up for a free account
3. Get your API key from the dashboard
4. Add it to your `.env` file

## 🚦 Running the Application

### Quick Start (Recommended)

```bash
# Start both frontend and backend
npm run dev
```

This will start:
- Backend API server at `http://localhost:8000`
- Frontend Next.js app at `http://localhost:3000`

### Individual Services

**Backend only:**
```bash
cd backend
source .venv/bin/activate  # or source venv/bin/activate
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Frontend only:**
```bash
cd frontend
pnpm dev
```

## 📱 Usage Examples

### 1. **Location-Based Medication Search**:
```text
"find ibuprofen in San Diego, CA"
"find metformin near New York, NY"
"locate acetaminophen at Los Angeles"
```

### 2. **Price Comparison**:
```text
"compare prices for ibuprofen"
"show me price differences for metformin 500mg"
```

### 3. **Generic Alternatives**:
```text
"find generic alternatives for Advil"
"show me cheaper versions of Lipitor"
```

### 4. **Medication Information**:
```text
"get medication info for aspirin"
"tell me about ibuprofen side effects"
```

### 5. **Pharmacy Search**:
```text
"find pharmacies near me with Tylenol"
"locate CVS stores in Miami"
```

## 🔧 API Endpoints

### MCP Tool Endpoints

- **POST** `/mcp/tools/find_pharmacies` - Find pharmacies with medication
- **POST** `/mcp/tools/compare_prices` - Compare medication prices
- **POST** `/mcp/tools/find_generic_alternatives` - Find generic alternatives
- **POST** `/mcp/tools/get_medication_info` - Get medication information
- **POST** `/mcp/tools/search_medication_price` - Search medication prices

### System Endpoints

- **GET** `/` - API status
- **GET** `/health` - Health check
- **GET** `/mcp/status` - MCP server status
- **GET** `/mcp/stats` - Usage statistics

### Example API Usage

```bash
# Find pharmacies
curl -X POST "http://localhost:8000/mcp/tools/find_pharmacies" \
  -H "Content-Type: application/json" \
  -d '{"medication_name": "ibuprofen", "location": "San Diego, CA", "search_type": "local"}'

# Compare prices
curl -X POST "http://localhost:8000/mcp/tools/compare_prices" \
  -H "Content-Type: application/json" \
  -d '{"medication_name": "ibuprofen", "pharmacy_types": ["retail", "online", "discount"]}'
```

## 🧠 Advanced Features

### 1. **Smart Query Processing**
- Intelligent medication name extraction from complex queries
- Location parsing with multiple format support
- Context-aware query understanding
- Fallback mechanisms for ambiguous queries

### 2. **Enhanced Price Analysis**
- Multi-pattern price extraction (20+ regex patterns)
- Price range validation and filtering
- Statistical analysis (averages, ranges, savings)
- Pharmacy type categorization and comparison

### 3. **Comprehensive Pharmacy Search**
- Multiple search strategies for maximum coverage
- Address validation and geocoding
- Distance calculation and sorting
- Metadata extraction (phone, hours, delivery info)

### 4. **Real-Time Data Processing**
- Live API integration with Tavily search
- No mock or sample data - all real results
- Intelligent caching for performance
- Rate limiting for API protection

## 🛡️ Performance & Reliability

### Caching Strategy
- **Pharmacy Data**: 2-hour cache for location-based searches
- **Price Data**: 30-minute cache for price comparisons
- **Medication Info**: 1-hour cache for drug information
- **Automatic Cleanup**: Expired cache removal every 5 minutes

### Rate Limiting
- **Token Bucket Algorithm**: 100 tokens per minute per endpoint
- **Graceful Degradation**: Informative error messages when limits exceeded
- **Usage Tracking**: Analytics for monitoring and optimization

### Error Handling
- **Comprehensive Validation**: Input validation at all levels
- **Graceful Failures**: Meaningful error messages with suggestions
- **Fallback Mechanisms**: Alternative search strategies when primary fails
- **Logging**: Detailed logging for debugging and monitoring

## 🧪 Testing

```bash
# Run all tests
npm run test

# Backend tests
cd backend && python -m pytest tests/

# Frontend tests  
cd frontend && pnpm test

# Test specific functionality
cd backend && python -m pytest tests/test_cache_rate_limit.py
cd backend && python -m pytest tests/test_errors.py
```

## 📦 Production Deployment

1. **Build the Application**:
   ```bash
   npm run build
   ```

2. **Configure Production Environment**:
   - Set production environment variables
   - Configure reverse proxy (nginx recommended)
   - Set up SSL certificates
   - Configure monitoring and logging

3. **Start Production Server**:
   ```bash
   npm start
   ```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes with proper testing
4. Commit your changes (`git commit -m 'Add amazing feature'`)
5. Push to the branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

### Development Guidelines
- Follow TypeScript best practices
- Add tests for new functionality
- Update documentation for API changes
- Ensure responsive design for UI changes
- Test with various medication names and locations

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Tavily](https://www.tavily.com/) for providing the AI-optimized search API
- [FastAPI](https://fastapi.tiangolo.com/) for the robust backend framework
- [Next.js](https://nextjs.org/) for the powerful React framework
- [Tailwind CSS](https://tailwindcss.com/) for the utility-first CSS framework
- [Lucide React](https://lucide.dev/) for the beautiful icon library

## 📞 Support

For support and questions:

1. Check the [Issues](../../issues) page for known problems
2. Review the API documentation above
3. Test with the provided example queries
4. Ensure your Tavily API key is valid and has sufficient credits

## 🔮 Roadmap

### Immediate (Q1 2025)
- [ ] Prescription management integration
- [ ] Insurance coverage optimization
- [ ] Mobile app development
- [ ] Advanced analytics dashboard

### Near-term (Q2 2025)
- [ ] Multi-language support
- [ ] Healthcare provider integration
- [ ] AI-powered drug interaction checker
- [ ] Price alert notifications

### Long-term (Q3-Q4 2025)
- [ ] Telemedicine platform integration
- [ ] Blockchain prescription verification
- [ ] Advanced ML price prediction models
- [ ] Pharmacy inventory real-time tracking

---

**Version**: 2.0.0  
**Last Updated**: July 2025  
**Status**: Production Ready ✅ 
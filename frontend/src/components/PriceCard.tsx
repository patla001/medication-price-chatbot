import { DollarSign, MapPin, Phone, ExternalLink, Clock } from 'lucide-react'

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

interface PriceCardProps {
  price: MedicationPrice
}

export default function PriceCard({ price }: PriceCardProps) {
  const formatPrice = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount)
  }

  const formatDate = (dateString: string) => {
    try {
      const date = new Date(dateString)
      return date.toLocaleDateString()
    } catch {
      return 'Recently'
    }
  }

  const handleWebsiteClick = () => {
    if (price.website) {
      window.open(price.website, '_blank', 'noopener,noreferrer')
    }
  }

  return (
    <div className="price-card bg-white border border-gray-200 rounded-lg p-4 hover:shadow-lg transition-all duration-300">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-gray-800 text-lg">{price.pharmacy_name}</h3>
        <div className={`px-2 py-1 rounded-full text-xs ${
          price.in_stock 
            ? 'bg-green-100 text-green-800' 
            : 'bg-red-100 text-red-800'
        }`}>
          {price.in_stock ? 'In Stock' : 'Out of Stock'}
        </div>
      </div>

      {/* Price */}
      <div className="flex items-center mb-3">
        <DollarSign className="w-5 h-5 text-green-600 mr-1" />
        <span className="text-2xl font-bold text-green-600">
          {formatPrice(price.price)}
        </span>
      </div>

      {/* Location */}
      <div className="flex items-center text-gray-600 mb-2">
        <MapPin className="w-4 h-4 mr-2" />
        <span className="text-sm">
          {price.location}
          {price.distance && ` • ${price.distance}`}
        </span>
      </div>

      {/* Phone */}
      {price.phone && (
        <div className="flex items-center text-gray-600 mb-2">
          <Phone className="w-4 h-4 mr-2" />
          <a 
            href={`tel:${price.phone}`}
            className="text-sm hover:text-primary-600 transition-colors"
          >
            {price.phone}
          </a>
        </div>
      )}

      {/* Last Updated */}
      <div className="flex items-center text-gray-500 mb-3">
        <Clock className="w-4 h-4 mr-2" />
        <span className="text-xs">Updated {formatDate(price.last_updated)}</span>
      </div>

      {/* Website Link */}
      {price.website && (
        <button
          onClick={handleWebsiteClick}
          className="w-full flex items-center justify-center bg-primary-50 text-primary-700 py-2 px-4 rounded-md hover:bg-primary-100 transition-colors"
        >
          <ExternalLink className="w-4 h-4 mr-2" />
          <span className="text-sm font-medium">Visit Website</span>
        </button>
      )}
    </div>
  )
} 
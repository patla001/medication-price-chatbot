import React from 'react';
import { DollarSign, MapPin, Phone, ExternalLink, Clock, AlertCircle, Truck, Info } from 'lucide-react'

interface PriceCardProps {
  pharmacy_name: string;
  type?: string;
  price?: number;
  address?: string;
  phone?: string;
  website?: string;
  delivery_info?: string;
  in_stock?: boolean;
  last_updated?: string;
  hours?: string;
  distance?: number;
  accuracy?: string;
  accuracy_type?: string;
}

const PriceCard: React.FC<PriceCardProps> = ({
  pharmacy_name,
  type,
  price,
  address,
  phone,
  website,
  delivery_info,
  in_stock = true,
  last_updated,
  hours,
  distance,
  accuracy,
  accuracy_type,
}) => {
  const formatPrice = (amount: number | undefined) => {
    if (amount === undefined || amount === null) return 'Call for price'
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(amount)
  }

  const getMapLink = (addr: string) => {
    const encodedAddress = encodeURIComponent(addr)
    return `https://www.google.com/maps/search/?api=1&query=${encodedAddress}`
  }

  const formatPhone = (phoneNum: string) => {
    // Remove any non-digit characters
    const cleaned = phoneNum.replace(/\D/g, '')
    // Format as (XXX) XXX-XXXX
    if (cleaned.length === 10) {
      return `(${cleaned.slice(0, 3)}) ${cleaned.slice(3, 6)}-${cleaned.slice(6)}`
    }
    return phoneNum
  }

  const formatDistance = (dist: number | undefined) => {
    if (!dist) return null
    if (dist < 1) return `${(dist * 1000).toFixed(0)}m away`
    return `${dist.toFixed(1)} miles away`
  }

  const getAccuracyBadge = () => {
    if (!accuracy_type) return null
    
    const badgeColor = accuracy_type === 'tavily_extracted' ? 'bg-green-100 text-green-800' : 
                      accuracy_type === 'estimated' ? 'bg-yellow-100 text-yellow-800' : 
                      'bg-gray-100 text-gray-800'
    
    return (
      <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${badgeColor}`}>
        <Info className="w-3 h-3 mr-1" />
        {accuracy_type === 'tavily_extracted' ? 'Verified' : 
         accuracy_type === 'estimated' ? 'Estimated' : 'Sample'}
      </span>
    )
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-4 mb-4 border border-gray-200">
      <div className="flex justify-between items-start mb-3">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="text-lg font-semibold text-gray-900">{pharmacy_name}</h3>
            {getAccuracyBadge()}
          </div>
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <span>{type || 'Local Pharmacy'}</span>
            {distance && (
              <>
                <span>•</span>
                <span>{formatDistance(distance)}</span>
              </>
            )}
          </div>
        </div>
        <div className="text-xl font-bold text-green-600">
          {formatPrice(price)}
        </div>
      </div>

      <div className="space-y-3 text-sm text-gray-600">
        {/* Address - Always show if available, with improved styling */}
        {address && address.trim() && (
          <div className="flex items-start gap-2 p-2 bg-gray-50 rounded-md">
            <MapPin className="w-4 h-4 mt-0.5 flex-shrink-0 text-blue-600" />
            <div className="flex-1">
              <a
                href={getMapLink(address)}
                target="_blank"
                rel="noopener noreferrer"
                className="text-gray-800 hover:text-blue-600 hover:underline font-medium"
                title="Open in Google Maps"
              >
                {address}
              </a>
            </div>
          </div>
        )}

        {/* Show message if no address for local pharmacy */}
        {!address && type === 'Local Pharmacy' && (
          <div className="flex items-center gap-2 p-2 bg-yellow-50 rounded-md text-yellow-800">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span className="text-sm">Address not available - call for location details</span>
          </div>
        )}

        {/* Delivery info for online pharmacies */}
        {delivery_info && (
          <div className="flex items-center gap-2">
            <Truck className="w-4 h-4 text-green-600" />
            <span className="text-green-700 font-medium">{delivery_info}</span>
          </div>
        )}

        {/* Phone number */}
        {phone && (
          <div className="flex items-center gap-2">
            <Phone className="w-4 h-4 text-blue-600" />
            <a
              href={`tel:${phone.replace(/\D/g, '')}`}
              className="text-blue-600 hover:text-blue-800 hover:underline font-medium"
              title="Call pharmacy"
            >
              {formatPhone(phone)}
            </a>
          </div>
        )}

        {/* Hours */}
        {hours && (
          <div className="flex items-start gap-2">
            <Clock className="w-4 h-4 mt-0.5 text-gray-500" />
            <div className="text-gray-700">{hours}</div>
          </div>
        )}

        {/* Website */}
        {website && (
          <div className="flex items-center gap-2">
            <ExternalLink className="w-4 h-4 text-blue-600" />
            <a
              href={website}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:text-blue-800 hover:underline font-medium"
            >
              {type === 'Online Pharmacy' ? 'View Details & Order Online' : 'View Store Details'}
            </a>
          </div>
        )}

        {/* Stock status */}
        {!in_stock && (
          <div className="flex items-center gap-2 p-2 bg-amber-50 rounded-md text-amber-800">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>
              {type === 'Online Pharmacy'
                ? 'Check website for stock availability'
                : 'Call store to verify availability'}
            </span>
          </div>
        )}
      </div>

      {/* Last updated */}
      {last_updated && (
        <div className="mt-3 pt-2 border-t border-gray-100">
          <div className="text-xs text-gray-400">
            Last updated: {new Date(last_updated).toLocaleDateString()}
          </div>
        </div>
      )}
    </div>
  )
}

export default PriceCard 
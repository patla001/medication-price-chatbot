import { NextResponse } from 'next/server';

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
}

export async function POST(request: Request) {
  try {
    const data = await request.json();
    
    const response = await fetch('http://localhost:8000/mcp/tools/find_pharmacies', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const errorData = await response.json();
      return NextResponse.json(
        {
          error: errorData.detail?.error || errorData.detail || 'Failed to find pharmacies',
          suggestions: errorData.detail?.suggestions || [
            'Try searching with different terms',
            'Check if the medication name is spelled correctly',
            'Try again in a few moments'
          ]
        },
        { status: response.status }
      );
    }

    const responseData = await response.json();
    
    // Transform pharmacy data to match our interface
    if (responseData.pharmacies) {
      responseData.pharmacies = responseData.pharmacies.map((pharmacy: any) => ({
        name: pharmacy.name,
        type: pharmacy.type,
        price: pharmacy.price,
        address: pharmacy.address,
        phone: pharmacy.phone,
        website: pharmacy.website,
        delivery_info: pharmacy.delivery_info,
        has_medication: pharmacy.has_medication,
        last_updated: pharmacy.last_updated,
        hours: pharmacy.hours
      }));
    }

    return NextResponse.json(responseData);
  } catch (error) {
    console.error('Error in find_pharmacies route:', error);
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : 'An error occurred',
        suggestions: [
          'Please try again in a few moments',
          'Check your internet connection',
          'Try searching with different terms'
        ]
      },
      { status: 500 }
    );
  }
} 
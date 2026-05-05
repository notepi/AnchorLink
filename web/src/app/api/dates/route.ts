import { NextResponse } from 'next/server';
import { getAvailableDates } from '@/lib/data-reader';

export async function GET() {
  try {
    const dates = await getAvailableDates();
    return NextResponse.json({ dates });
  } catch (error) {
    console.error('Failed to fetch dates:', error);
    return NextResponse.json({ error: 'Failed to fetch dates' }, { status: 500 });
  }
}
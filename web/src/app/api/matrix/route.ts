import { NextRequest, NextResponse } from 'next/server';
import { getMatrix } from '@/lib/data-reader';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const date = searchParams.get('date');

    if (!date) {
      return NextResponse.json({ error: 'date is required' }, { status: 400 });
    }

    const matrix = await getMatrix(date);
    return NextResponse.json({ matrix });
  } catch (error) {
    console.error('Failed to fetch matrix:', error);
    return NextResponse.json({ error: 'Failed to fetch matrix' }, { status: 500 });
  }
}
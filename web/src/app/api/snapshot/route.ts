import { NextRequest, NextResponse } from 'next/server';
import { getSnapshot } from '@/lib/data-reader';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const date = searchParams.get('date');

    if (!date) {
      return NextResponse.json({ error: 'date is required' }, { status: 400 });
    }

    const snapshot = await getSnapshot(date);
    if (!snapshot) {
      return NextResponse.json({ error: 'Snapshot not found' }, { status: 404 });
    }

    return NextResponse.json(snapshot);
  } catch (error) {
    console.error('Failed to fetch snapshot:', error);
    return NextResponse.json({ error: 'Failed to fetch snapshot' }, { status: 500 });
  }
}
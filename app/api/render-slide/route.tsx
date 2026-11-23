import { ImageResponse } from 'next/og';
import { NextRequest } from 'next/server';

export const runtime = 'edge';

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const title = searchParams.get('title') || 'Judul Edukasi Leologi';
  const body = searchParams.get('body') || 'Isi penjelasan singkat dan padat akan muncul di sini.';
  const page = searchParams.get('page') || '1/4';
  const tag = searchParams.get('tag') || 'EDUKASI & TEKNOLOGI';

  return new ImageResponse(
    (
      <div
        style={{
          width: '1080px',
          height: '1350px',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          backgroundColor: '#0F172A',
          color: '#F8FAFC',
          padding: '84px',
          fontFamily: 'sans-serif',
          borderTop: '18px solid #FF7A00',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ fontSize: 30, color: '#00F0FF', fontWeight: 'bold', letterSpacing: '2px' }}>
            {tag}
          </div>
          <div
            style={{
              fontSize: 28,
              color: '#0F172A',
              backgroundColor: '#FF7A00',
              padding: '8px 24px',
              borderRadius: '999px',
              fontWeight: 'bold',
            }}
          >
            {page}
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '40px' }}>
          <div style={{ width: '120px', height: '10px', backgroundColor: '#00F0FF', borderRadius: '6px' }} />
          <div style={{ fontSize: 70, fontWeight: 'bold', lineHeight: 1.18, color: '#F8FAFC' }}>
            {title}
          </div>
          <div style={{ fontSize: 42, color: '#CBD5E1', lineHeight: 1.5 }}>
            {body}
          </div>
        </div>

        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            borderTop: '2px solid #1E293B',
            paddingTop: '32px',
          }}
        >
          <div style={{ fontSize: 32, fontWeight: 'bold', color: '#F8FAFC' }}>
            @leologi.id
          </div>
          <div style={{ fontSize: 28, color: '#00F0FF' }}>
            Geser & Simpan →
          </div>
        </div>
      </div>
    ),
    { width: 1080, height: 1350 }
  );
}

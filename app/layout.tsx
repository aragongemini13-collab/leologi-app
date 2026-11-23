import React from 'react';

export const metadata = {
  title: 'Leologi App',
  description: 'Mesin Konten Edukasi @leologi.id',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="id">
      <body style={{ margin: 0 }}>{children}</body>
    </html>
  );
}

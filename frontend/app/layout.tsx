import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'PageTrust Auditor',
  description: 'Pre-publish quality checker for AI-generated local business websites'
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

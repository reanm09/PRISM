import type { Metadata } from 'next';
import './globals.css';
import { AppProviders } from '@/components/app-providers';

export const metadata: Metadata = {
  icons: { icon: '/prism-mark.svg' },
  title: 'PRISM — Artifact Truth Engine',
  description: 'Evidence-first digital artifact analysis and semantic differential investigation.',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  );
}

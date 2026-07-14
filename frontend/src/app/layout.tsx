import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TBM Carriers Chat Pilot",
  description: "Standalone bilingual inbound freight sales chat pilot for TBM Carriers.",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}

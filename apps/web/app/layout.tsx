import type { Metadata } from "next";
import "./globals.css";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";

export const metadata: Metadata = {
  title: "Realty Alerts — Never miss a Dutch home listing",
  description:
    "Get instant notifications when new properties appear on Funda, Pararius, and more. Stay ahead in the Dutch housing market.",
  openGraph: {
    title: "Realty Alerts",
    description: "Instant notifications for Dutch real estate listings.",
    type: "website",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="scroll-smooth">
      <body className="min-h-screen flex flex-col bg-white text-gray-900 antialiased">
        <Header />
        <main className="flex-1">{children}</main>
        <Footer />
      </body>
    </html>
  );
}

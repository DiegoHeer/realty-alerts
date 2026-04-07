import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Realty Alerts — Never miss a Dutch home listing",
  description:
    "Get instant notifications when new properties appear on Funda, Pararius, and more. Stay ahead in the Dutch housing market.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

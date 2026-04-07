import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Terms of Service — Realty Alerts",
};

export default function Terms() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-16">
      <h1 className="text-3xl font-bold">Terms of Service</h1>
      <p className="mt-2 text-sm text-gray-500">Last updated: April 2026</p>

      <div className="mt-8 space-y-8 text-gray-700 leading-relaxed">
        <section>
          <h2 className="text-xl font-semibold text-gray-900">1. Service description</h2>
          <p className="mt-2">
            Realty Alerts is a notification service that monitors Dutch real estate websites for new
            property listings and alerts users when listings match their configured filters. We do
            not sell, rent, or broker properties.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-gray-900">2. Data accuracy</h2>
          <p className="mt-2">
            Listing data is scraped from third-party websites and may be incomplete, outdated, or
            inaccurate. We make no guarantees about the accuracy, availability, or timeliness of
            listing data. Always verify listing details on the original website before making
            decisions.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-gray-900">3. Service availability</h2>
          <p className="mt-2">
            We strive for high availability but cannot guarantee uninterrupted service. Scraping may
            be temporarily disrupted by changes to target websites, anti-bot measures, or
            infrastructure maintenance.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-gray-900">4. User responsibilities</h2>
          <p className="mt-2">
            You are responsible for keeping your account credentials secure. Do not share your
            account or use the service for automated bulk data collection beyond personal use.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-gray-900">5. Limitation of liability</h2>
          <p className="mt-2">
            Realty Alerts is provided &ldquo;as is&rdquo; without warranty. We are not liable for
            missed notifications, inaccurate listing data, or any decisions made based on
            information provided by the service.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-gray-900">6. Changes to terms</h2>
          <p className="mt-2">
            We may update these terms at any time. Continued use of the service after changes
            constitutes acceptance of the updated terms.
          </p>
        </section>
      </div>
    </div>
  );
}

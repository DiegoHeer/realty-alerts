import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy Policy — Realty Alerts",
};

export default function Privacy() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-16">
      <h1 className="text-3xl font-bold">Privacy Policy</h1>
      <p className="mt-2 text-sm text-gray-500">Last updated: April 2026</p>

      <div className="mt-8 space-y-8 text-gray-700 leading-relaxed">
        <section>
          <h2 className="text-xl font-semibold text-gray-900">1. What we collect</h2>
          <p className="mt-2">
            We collect the minimum data needed to operate the service: your email address (for
            authentication), your saved filter preferences, and your device push token (for
            notifications). We do not collect personal browsing data, location data, or sell any
            information to third parties.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-gray-900">2. How we use your data</h2>
          <p className="mt-2">
            Your filter preferences are used solely to match incoming real estate listings and send
            you relevant push notifications. Your email is used for account authentication. All data
            is processed on our self-hosted infrastructure.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-gray-900">3. Data storage</h2>
          <p className="mt-2">
            All data is stored on self-hosted servers within the European Union. We use Supabase
            (self-hosted) for authentication and PostgreSQL for data storage. Data is encrypted in
            transit (TLS) and at rest.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-gray-900">4. Third-party services</h2>
          <p className="mt-2">
            We use Expo Push Notifications (via Firebase Cloud Messaging and Apple Push Notification
            service) to deliver notifications to your device. No other third-party analytics or
            tracking services are used.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-gray-900">5. Web scraping</h2>
          <p className="mt-2">
            Realty Alerts scrapes publicly available real estate listings from Dutch websites. We
            respect robots.txt policies and implement rate limiting to minimize impact on target
            websites.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-gray-900">6. Your rights</h2>
          <p className="mt-2">
            You can delete your account and all associated data at any time through the app
            settings. For questions or data requests, contact us at privacy@realtyalerts.nl.
          </p>
        </section>
      </div>
    </div>
  );
}

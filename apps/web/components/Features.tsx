const features = [
  {
    title: "Real-time notifications",
    description:
      "Get push notifications the moment new listings match your criteria. No more refreshing pages.",
    icon: "🔔",
  },
  {
    title: "Multiple websites",
    description:
      "We scrape Funda, Pararius, and Vastgoed Nederland so you only need one app for all listings.",
    icon: "🌐",
  },
  {
    title: "Custom filters",
    description:
      "Set filters by city, price range, property type, bedrooms, and more. Only see what matters to you.",
    icon: "🎯",
  },
  {
    title: "Scrape status dashboard",
    description:
      "See exactly when each website was last scraped and how many new listings were found.",
    icon: "📊",
  },
  {
    title: "Fast and lightweight",
    description:
      "Built as a native mobile app. Smooth performance, minimal battery usage, works offline.",
    icon: "⚡",
  },
  {
    title: "Privacy first",
    description:
      "Self-hosted infrastructure. Your data stays on your servers. No tracking, no ads.",
    icon: "🔒",
  },
];

export function Features() {
  return (
    <section id="features" className="py-24">
      <div className="mx-auto max-w-6xl px-6">
        <div className="text-center">
          <h2 className="text-3xl font-bold sm:text-4xl">
            Everything you need to find your next home
          </h2>
          <p className="mt-4 text-lg text-gray-600">
            Stop manually checking multiple websites. Let us do the work.
          </p>
        </div>

        <div className="mt-16 grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((feature) => (
            <div
              key={feature.title}
              className="rounded-2xl border border-gray-100 bg-white p-8 shadow-sm hover:shadow-md transition-shadow"
            >
              <span className="text-3xl">{feature.icon}</span>
              <h3 className="mt-4 text-lg font-semibold">{feature.title}</h3>
              <p className="mt-2 text-gray-600">{feature.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

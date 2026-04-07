const steps = [
  {
    number: "1",
    title: "Create your filters",
    description:
      "Tell us what you are looking for: city, price range, property type, number of bedrooms. Create as many filters as you need.",
  },
  {
    number: "2",
    title: "We scrape for you",
    description:
      "Our scrapers automatically check Funda, Pararius, and Vastgoed Nederland multiple times per day for new listings.",
  },
  {
    number: "3",
    title: "Get notified instantly",
    description:
      "When a new listing matches your filters, you get a push notification. Tap to view the details and visit the website.",
  },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className="bg-gray-50 py-24">
      <div className="mx-auto max-w-6xl px-6">
        <div className="text-center">
          <h2 className="text-3xl font-bold sm:text-4xl">How it works</h2>
          <p className="mt-4 text-lg text-gray-600">Three simple steps to stay ahead.</p>
        </div>

        <div className="mt-16 grid gap-12 sm:grid-cols-3">
          {steps.map((step) => (
            <div key={step.number} className="text-center">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-blue-600 text-xl font-bold text-white">
                {step.number}
              </div>
              <h3 className="mt-6 text-lg font-semibold">{step.title}</h3>
              <p className="mt-2 text-gray-600">{step.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

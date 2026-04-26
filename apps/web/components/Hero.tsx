export function Hero() {
  return (
    <section className="relative overflow-hidden bg-gradient-to-b from-blue-50 to-white">
      <div className="mx-auto max-w-6xl px-6 py-24 sm:py-32 text-center">
        <h1 className="text-4xl font-extrabold tracking-tight sm:text-6xl">
          Never miss a Dutch
          <br />
          <span className="text-blue-600">home listing</span> again
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-gray-600">
          Get instant push notifications when new properties appear on Funda, Pararius, and
          Vastgoed Nederland. Set your filters once, and we do the rest.
        </p>
        <div className="mt-10 flex items-center justify-center gap-4">
          <a
            href="#cta"
            className="rounded-xl bg-blue-600 px-8 py-3.5 text-base font-semibold text-white shadow-lg shadow-blue-600/25 hover:bg-blue-700 transition-colors"
          >
            Get started free
          </a>
          <a
            href="#how-it-works"
            className="rounded-xl border border-gray-300 px-8 py-3.5 text-base font-semibold text-gray-700 hover:border-gray-400 transition-colors"
          >
            See how it works
          </a>
        </div>

        <div className="mt-16 flex items-center justify-center gap-8 opacity-60">
          <span className="text-sm font-medium text-gray-500">Works with</span>
          <span className="text-lg font-bold text-orange-500">funda</span>
          <span className="text-lg font-bold text-blue-800">Pararius</span>
          <span className="text-lg font-bold text-green-700">Vastgoed NL</span>
        </div>
      </div>
    </section>
  );
}

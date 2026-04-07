export function CTA() {
  return (
    <section id="cta" className="py-24">
      <div className="mx-auto max-w-4xl px-6 text-center">
        <div className="rounded-3xl bg-blue-600 px-8 py-16 shadow-2xl shadow-blue-600/20 sm:px-16">
          <h2 className="text-3xl font-bold text-white sm:text-4xl">
            Ready to find your dream home?
          </h2>
          <p className="mt-4 text-lg text-blue-100">
            Download the app and set up your first filter in under a minute.
          </p>
          <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <a
              href="#"
              className="rounded-xl bg-white px-8 py-3.5 text-base font-semibold text-blue-600 hover:bg-blue-50 transition-colors"
            >
              Download for iOS
            </a>
            <a
              href="#"
              className="rounded-xl border-2 border-white/30 px-8 py-3.5 text-base font-semibold text-white hover:border-white/60 transition-colors"
            >
              Download for Android
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}

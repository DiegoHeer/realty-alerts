import Link from "next/link";

export function Header() {
  return (
    <header className="sticky top-0 z-50 border-b border-gray-100 bg-white/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link href="/" className="text-xl font-bold text-blue-600">
          Realty Alerts
        </Link>
        <nav className="flex items-center gap-6">
          <Link href="#features" className="text-sm text-gray-600 hover:text-gray-900">
            Features
          </Link>
          <Link href="#how-it-works" className="text-sm text-gray-600 hover:text-gray-900">
            How it works
          </Link>
          <Link
            href="#cta"
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
          >
            Get started
          </Link>
        </nav>
      </div>
    </header>
  );
}

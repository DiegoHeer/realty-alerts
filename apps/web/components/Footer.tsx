import Link from "next/link";

export function Footer() {
  return (
    <footer className="border-t border-gray-100 bg-gray-50">
      <div className="mx-auto max-w-6xl px-6 py-12">
        <div className="flex flex-col items-center justify-between gap-6 sm:flex-row">
          <div>
            <p className="text-lg font-bold text-gray-900">Realty Alerts</p>
            <p className="mt-1 text-sm text-gray-500">
              Never miss a Dutch home listing again.
            </p>
          </div>
          <nav className="flex gap-6 text-sm text-gray-500">
            <Link href="/privacy" className="hover:text-gray-900">
              Privacy Policy
            </Link>
            <Link href="/terms" className="hover:text-gray-900">
              Terms of Service
            </Link>
          </nav>
        </div>
        <p className="mt-8 text-center text-xs text-gray-400">
          &copy; {new Date().getFullYear()} Realty Alerts. All rights reserved.
        </p>
      </div>
    </footer>
  );
}

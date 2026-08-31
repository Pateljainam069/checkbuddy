import type { Metadata, Viewport } from "next";
import Link from "next/link";
import { Archivo, IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";
import "./globals.css";

/*
  Type pairing. Archivo is a grotesque built for high-impact print signage — it
  carries the verdict, set black and tracked, and nothing else. IBM Plex Sans and
  Mono are an engineering superfamily rather than a product-marketing one, which
  is the register a regulatory tool should speak in. Mono is not stylistic here:
  everything it sets is machine-read data — OCR output, confidences, barcodes.
*/
const archivo = Archivo({
  variable: "--font-archivo",
  subsets: ["latin"],
  weight: ["600", "700", "900"],
});

const plexSans = IBM_Plex_Sans({
  variable: "--font-plex-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "CheckBuddy — Legal Metrology label check",
  description:
    "Photograph a packaged product label and check it against six declarations required by the Legal Metrology (Packaged Commodities) Rules, 2011.",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#e9ece6" },
    { media: "(prefers-color-scheme: dark)", color: "#14171a" },
  ],
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${archivo.variable} ${plexSans.variable} ${plexMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col">
        <header className="border-b border-(--rule-strong)">
          <div className="mx-auto flex max-w-2xl items-center justify-between gap-4 px-4 py-3.5 sm:px-6">
            <Link href="/" className="group">
              <span className="font-display block text-[1.0625rem] leading-none font-black tracking-[0.06em] uppercase">
                CheckBuddy
              </span>
              <span className="marker mt-1 block">Legal Metrology field check</span>
            </Link>
            <nav>
              <Link
                href="/history"
                className="marker underline decoration-(--rule-strong) underline-offset-4 hover:text-(--ink)"
              >
                History
              </Link>
            </nav>
          </div>
        </header>

        <main className="mx-auto w-full max-w-2xl flex-1 px-4 py-6 sm:px-6 sm:py-8">
          {children}
        </main>

        <footer className="border-t border-(--rule) px-4 py-5 sm:px-6">
          <p className="mx-auto max-w-2xl text-[0.75rem] leading-relaxed text-(--ink-3)">
            Prototype for SIH26034. Checks six declarations from the Legal Metrology
            (Packaged Commodities) Rules, 2011 — a scoped subset, not the full standard.
          </p>
        </footer>
      </body>
    </html>
  );
}

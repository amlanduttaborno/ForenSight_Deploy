import type { Metadata } from "next";
import "./globals.css";
import { Nav } from "@/components/nav";
import { Providers } from "@/components/providers";
import { PreferencesProvider } from "@/components/preferences";

export const metadata: Metadata = {
  title: "ForenSight — Initial Demo",
  description: "Explainable multimodal image forensics supervisor prototype",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <PreferencesProvider>
          <Providers>
            <div className="min-h-screen md:flex">
              <Nav />
              <main className="min-w-0 flex-1">{children}</main>
            </div>
          </Providers>
        </PreferencesProvider>
      </body>
    </html>
  );
}

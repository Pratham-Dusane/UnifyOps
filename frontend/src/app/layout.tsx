import type { Metadata } from "next";
import "./globals.css";
import Providers from "./providers";

export const metadata: Metadata = {
  title: "UnifyOps - AI Industrial Knowledge Intelligence",
  description:
    "Unified Asset & Operations Brain for industrial plants. Ingest, connect, and query your plant's entire documented history with AI-powered intelligence.",
  keywords: [
    "industrial knowledge",
    "knowledge graph",
    "maintenance intelligence",
    "compliance",
    "AI copilot",
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}

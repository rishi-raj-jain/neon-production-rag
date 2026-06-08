import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Neon Production RAG",
  description: "Hybrid RAG over Neon Postgres documentation",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

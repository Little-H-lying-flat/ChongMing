import type { Metadata } from "next";
import "./globals.css";
import Providers from "./providers";
import { Sidebar } from "@/components/Sidebar";
import { Toaster } from "sonner";

export const metadata: Metadata = {
  title: "ChongMing Test Platform",
  description: "Intelligent Agentic Testing",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="bg-slate-50 font-sans text-slate-900 antialiased">
        <Providers>
          <div className="flex h-screen overflow-hidden bg-[radial-gradient(circle_at_top_left,rgba(56,189,248,0.18),transparent_30%),radial-gradient(circle_at_top_right,rgba(168,85,247,0.14),transparent_28%),linear-gradient(135deg,#f8fafc_0%,#eef6ff_45%,#fff7ed_100%)]">
            <Sidebar />
            <main className="flex-1 overflow-y-auto p-8">
              {children}
            </main>
          </div>
          <Toaster theme="light" position="top-right" />
        </Providers>
      </body>
    </html>
  );
}

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
      <body className={`font-sans antialiased bg-slate-950 text-slate-100`}>
        <Providers>
          <div className="flex h-screen overflow-hidden">
            <Sidebar />
            <main className="flex-1 overflow-y-auto p-8 bg-slate-950">
              {children}
            </main>
          </div>
          <Toaster theme="dark" position="top-right" />
        </Providers>
      </body>
    </html>
  );
}

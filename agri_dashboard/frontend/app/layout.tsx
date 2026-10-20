import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "AgriSmart", description: "Adaptive irrigation decision-support simulator" };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en"><body>{children}</body></html>; }

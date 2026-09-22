import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Patient Test Caller — Dashboard",
  description: "Read-only dashboard of scenarios, calls, and bugs found by the AI patient test caller.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="wrap">
          <div className="topbar">
            <div className="brand">
              <span className="dot" />
              <span>Voicebot / Patient Test Caller</span>
            </div>
            <nav className="nav">
              <a className="chip" href="/">
                Scenarios
              </a>
              <a className="chip" href="/bug-report">
                Bug Report
              </a>
            </nav>
          </div>
          {children}
          <footer className="note">
            Read-only dashboard. No live calls are placed from this page — see the repo README for run.py / run_batch.py.
          </footer>
        </div>
      </body>
    </html>
  );
}

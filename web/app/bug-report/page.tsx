import { getBugsMarkdown } from "@/lib/data";

export const dynamic = "force-static";

export default function BugReportPage() {
  const markdown = getBugsMarkdown();

  return (
    <main>
      <a className="back-link" href="/">
        ← Back to scenarios
      </a>
      <section className="device">
        <div className="device-header">
          <span className="device-title">Bug Report</span>
          <span className="device-badge">bug_report/BUGS.md</span>
        </div>
        {markdown ? (
          <div className="markdown">{markdown}</div>
        ) : (
          <div className="empty-state">No bug report found.</div>
        )}
      </section>
    </main>
  );
}

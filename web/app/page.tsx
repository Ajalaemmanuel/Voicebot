import { latestCallForScenario, listScenarios } from "@/lib/data";

export const dynamic = "force-static";

function outcomeLabel(outcome: string | undefined) {
  switch (outcome) {
    case "completed":
      return "Completed";
    case "no_answer":
      return "No answer";
    case "timeout":
      return "Timeout";
    case "failed":
      return "Failed";
    default:
      return "Empty";
  }
}

export default function HomePage() {
  const scenarios = listScenarios();

  return (
    <main>
      <section className="device">
        <div className="device-header">
          <span className="device-title">Scenarios</span>
          <span className="device-badge">{scenarios.length} loaded</span>
        </div>

        {scenarios.length === 0 ? (
          <div className="empty-state">
            No scenarios found. Add YAML files under <code>scenarios/</code> and rebuild.
          </div>
        ) : (
          <div className="grid">
            {scenarios.map((scenario, i) => {
              const call = latestCallForScenario(scenario.slug);
              const outcome = call?.outcome ?? "unknown";
              const isEmpty = !call;
              const content = (
                <>
                  <span className="pad-index">P{i + 1}</span>
                  <div>
                    <div className="pad-name">{scenario.name}</div>
                    <div className="pad-goal">{scenario.goal}</div>
                  </div>
                  <div>
                    {scenario.hasPatientRecord && <span className="tag">RAG history</span>}
                    <div className="pad-footer">
                      <span className={`status-dot ${outcome}`} />
                      <span className="status-label">{isEmpty ? "Empty" : outcomeLabel(outcome)}</span>
                    </div>
                  </div>
                </>
              );

              return call ? (
                <a key={scenario.slug} className="pad" href={`/calls/${call.callId}`}>
                  {content}
                </a>
              ) : (
                <div key={scenario.slug} className="pad empty">
                  {content}
                </div>
              );
            })}
          </div>
        )}
      </section>
    </main>
  );
}

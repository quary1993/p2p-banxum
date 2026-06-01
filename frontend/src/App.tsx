const platformName = import.meta.env.VITE_PLATFORM_BRAND_NAME ?? "BANXUM";
const operatorName = import.meta.env.VITE_LEGAL_OPERATOR_NAME ?? "Garanta Finanzgruppe AG";

const shellItems = [
  "Investor portal",
  "Admin portal",
  "Primary marketplace",
  "Ledger and reconciliation"
];

export function App() {
  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Platform implementation</p>
          <h1>{platformName}</h1>
        </div>
        <span className="operator">{operatorName}</span>
      </header>

      <section className="workspace" aria-label="Implementation workspace">
        <aside className="nav-panel" aria-label="Module navigation preview">
          {shellItems.map((item) => (
            <button key={item} type="button" className="nav-item">
              {item}
            </button>
          ))}
        </aside>

        <section className="content-panel">
          <p className="eyebrow">First slice</p>
          <h2>Agent-ready scaffold</h2>
          <p>
            The first implementation slice establishes the backend, frontend, API contract, command
            surface, and module boundaries before domain workflows are added.
          </p>

          <dl className="status-grid">
            <div>
              <dt>Backend</dt>
              <dd>Django modular monolith</dd>
            </div>
            <div>
              <dt>Frontend</dt>
              <dd>React + TypeScript portal shell</dd>
            </div>
            <div>
              <dt>API</dt>
              <dd>OpenAPI generated client path</dd>
            </div>
            <div>
              <dt>Timezone</dt>
              <dd>Europe/Zurich business rules</dd>
            </div>
          </dl>
        </section>
      </section>
    </main>
  );
}

import { useEffect, useMemo, useState } from "react";

// Every number on the page comes from public/data/*.json (written by `python -I -m fineval.export`).
// Prose in this file deliberately contains no figures; tests/test_site.py checks that.

type Row = {
  task: string; model: string; value: number; kind: "published" | "reproduced";
  track?: string; setting?: string | null; ci95?: [number, number]; n?: number; metric: string;
  scope?: string; relation?: string; citation?: string; page?: number; table?: string; source_name?: string;
  judge?: string; run?: string; seed?: number; counts?: Record<string, number>;
  by_subset?: Record<string, number | null>; status?: Record<string, number>;
};
type TaskInfo = { title: string; metric: string; sources: string[] };
type Data = {
  tasks: Record<string, TaskInfo>;
  datasets: any;
  published: Row[];
  reproduced: Row[];
  retrieval: any;
};

const PAGES = ["leaderboard", "compare", "tasks", "methodology", "datasets", "reproduce"] as const;
type Page = (typeof PAGES)[number];
const LABEL: Record<Page, string> = {
  leaderboard: "Leaderboard", compare: "Compare", tasks: "Tasks", methodology: "Methodology",
  datasets: "Datasets", reproduce: "Reproduce",
};

const pct = (v: number) => `${(v * 100).toFixed(1)}%`;
const int = (v: number) => v.toLocaleString("en-US");

function usePage(): Page {
  const read = () => (PAGES as readonly string[]).includes(location.hash.slice(1)) ? (location.hash.slice(1) as Page) : "leaderboard";
  const [p, setP] = useState<Page>(read);
  useEffect(() => {
    const f = () => { setP(read()); window.scrollTo(0, 0); };
    addEventListener("hashchange", f);
    return () => removeEventListener("hashchange", f);
  }, []);
  return p;
}

async function load(): Promise<Data> {
  const get = (n: string) => fetch(`./data/${n}.json`).then((r) => r.json());
  const [tasks, datasets, published, reproduced, retrieval] = await Promise.all(
    ["tasks", "datasets", "published", "reproduced", "retrieval"].map(get));
  return { tasks, datasets, published, reproduced, retrieval };
}

function Seg<T extends string>({ value, options, onChange, label }:
  { value: T; options: [T, string][]; onChange: (v: T) => void; label: string }) {
  return (
    <span>
      <span className="ctl-label">{label}</span>
      <span className="seg" role="group" aria-label={label}>
        {options.map(([v, l]) => (
          <button key={v} className={v === value ? "on" : ""} aria-pressed={v === value} onClick={() => onChange(v)}>{l}</button>
        ))}
      </span>
    </span>
  );
}

function Bar({ v, pub }: { v: number; pub?: boolean }) {
  return <div className={`bar${pub ? " pub" : ""}`}><i style={{ width: `${Math.max(0, Math.min(1, v)) * 100}%` }} /></div>;
}

// ------------------------------------------------------------------ leaderboard
function Leaderboard({ d }: { d: Data }) {
  const [track, setTrack] = useState<"closed" | "tools">("closed");
  const [kind, setKind] = useState<"both" | "reproduced" | "published">("both");
  return (
    <>
      <h1>Leaderboard</h1>
      <p className="lede">
        Scores on FinEval's de-duplicated items. <span className="badge ours">reproduced</span> rows were run by us
        under one common setup; <span className="badge pub">published</span> rows are copied from papers, with
        their evaluation set stated, and are often not directly comparable.
      </p>
      {d.reproduced.length === 0 && (
        <div className="notice">
          No reproduced runs yet: model evaluation is waiting for GPU time. Published scores and all dataset
          statistics below are final.
        </div>
      )}
      <div className="controls">
        <Seg label="Track" value={track} onChange={setTrack} options={[["closed", "Closed-book"], ["tools", "Tool-assisted"]]} />
        <Seg label="Scores" value={kind} onChange={setKind}
          options={[["both", "Both"], ["reproduced", "Reproduced"], ["published", "Published"]]} />
      </div>
      {Object.entries(d.tasks).map(([task, info]) => {
        const ours = d.reproduced.filter((r) => r.task === task && r.track === track).sort((a, b) => b.value - a.value);
        const pub = d.published.filter((r) => r.task === task);
        // Published rows are ranked only against rows scored on the same evaluation set.
        const groups: [string, Row[]][] = [];
        if (kind !== "published") groups.push(["Reproduced under the FinEval setup", ours]);
        if (kind !== "reproduced") {
          for (const scope of [...new Set(pub.map((r) => r.scope!))]) {
            const g = pub.filter((r) => r.scope === scope).sort((a, b) => b.value - a.value);
            groups.push([`Published · ${g[0].source_name} · ${g[0].table}`, g]);
          }
        }
        return (
          <section className="task-group" key={task}>
            <h2>{info.title}</h2>
            <div className="small">{info.metric}</div>
            {groups.map(([title, rows]) => (
            <div key={title} style={{ marginTop: 12 }}>
            <h3 className="small" style={{ fontWeight: 600, color: "var(--text)" }}>{title}</h3>
            <div className="table-scroll">
              <table>
                <thead><tr><th>Model</th><th>Score</th><th>Source</th><th>Evaluated on</th></tr></thead>
                <tbody>
                  {rows.length === 0 && <tr><td colSpan={4} className="empty">No reproduced runs for this task and track yet.</td></tr>}
                  {rows.map((r, i) => (
                    <tr key={i}>
                      <td>{r.model}{r.setting ? <div className="small">{r.setting}</div> : null}</td>
                      <td className="num">
                        {pct(r.value)}
                        {r.ci95 && <div className="small">{pct(r.ci95[0])} – {pct(r.ci95[1])}</div>}
                        <Bar v={r.value} pub={r.kind === "published"} />
                      </td>
                      <td>
                        {r.kind === "published"
                          ? <><span className="badge pub">published</span><div className="small">{r.table}, p. {r.page}</div></>
                          : <><span className="badge ours">reproduced</span><div className="small mono">seed {r.seed}</div></>}
                      </td>
                      <td className="small">
                        {r.kind === "published" ? <>{r.scope} <span className="badge note">{r.relation}</span></>
                          : <>n = {int(r.n ?? 0)}{r.judge ? `, judge ${r.judge.replace("ollama:", "")}` : ""}</>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            </div>
            ))}
          </section>
        );
      })}
    </>
  );
}

// ------------------------------------------------------------------ compare
function Compare({ d }: { d: Data }) {
  const models = useMemo(() => [...new Set(d.reproduced.map((r) => r.model))].sort(), [d]);
  const [a, setA] = useState(models[0] ?? "");
  const [b, setB] = useState(models[1] ?? models[0] ?? "");
  if (models.length < 2) {
    return (<><h1>Compare</h1><div className="notice">Comparison needs at least two reproduced models. Runs are pending GPU time.</div></>);
  }
  const cell = (m: string, task: string, track: string) => d.reproduced.find((r) => r.model === m && r.task === task && r.track === track);
  return (
    <>
      <h1>Compare</h1>
      <div className="controls">
        {[[a, setA], [b, setB]].map(([v, set], i) => (
          <select key={i} value={v as string} onChange={(e) => (set as (s: string) => void)(e.target.value)}>
            {models.map((m) => <option key={m}>{m}</option>)}
          </select>
        ))}
      </div>
      <div className="table-scroll">
        <table>
          <thead><tr><th>Task</th><th>Track</th><th>{a}</th><th>{b}</th></tr></thead>
          <tbody>
            {Object.entries(d.tasks).flatMap(([task, info]) => ["closed", "tools"].map((tr) => {
              const x = cell(a, task, tr), y = cell(b, task, tr);
              if (!x && !y) return null;
              return (<tr key={task + tr}><td>{info.title}</td><td>{tr}</td>
                <td className="num">{x ? pct(x.value) : "—"}</td><td className="num">{y ? pct(y.value) : "—"}</td></tr>);
            }))}
          </tbody>
        </table>
      </div>
    </>
  );
}

// ------------------------------------------------------------------ tasks
function Tasks({ d }: { d: Data }) {
  const items = d.datasets.summary.items as Record<string, number>;
  const primary = d.datasets.summary.primary_items as Record<string, number>;
  const tax = d.retrieval.taxonomy ?? {};
  return (
    <>
      <h1>Tasks</h1>
      <p className="lede">Four task categories for the first version. Long-context consistency auditing (FinAuditing) follows once larger GPUs or API access are available.</p>
      <div className="grid">
        {Object.entries(d.tasks).map(([task, info]) => (
          <div className="card" key={task}>
            <h3>{info.title}</h3>
            <div className="stat"><span className="v">{int(items[`${task}:test`] ?? 0)}</span> <span className="k">test items</span></div>
            <div className="small">{int(primary[`${task}:test`] ?? 0)} in the primary score</div>
            <p className="small">Metric: {info.metric}</p>
            <ul className="small">{info.sources.map((s) => <li key={s}>{s}</li>)}</ul>
          </div>
        ))}
      </div>
      <h2>Retrieval ceilings for the tool-assisted track</h2>
      <p className="lede">A reranker cannot pick a concept that retrieval never offered, so these bound tool-assisted tagging accuracy. Computed without any language model.</p>
      <div className="table-scroll">
        <table>
          <thead><tr><th>Setting</th><th>Items</th>{["acc@1", "acc@10", "acc@50", "acc@100", "acc@200"].map((k) => <th key={k}>{k}</th>)}</tr></thead>
          <tbody>
            {Object.entries(tax).map(([name, r]: [string, any]) => (
              <tr key={name}><td className="mono">{name}</td><td className="num">{r.n}</td>
                {["acc@1", "acc@10", "acc@50", "acc@100", "acc@200"].map((k) => <td className="num" key={k}>{pct(r[k].value)}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
      {d.retrieval.formulas && (
        <p className="small">Formula retrieval for calculation questions: right formula retrieved first for {pct(d.retrieval.formulas.xbrl_agent_formula["acc@1"].value)} of {int(d.retrieval.formulas.xbrl_agent_formula.n)} questions.</p>
      )}
      {d.retrieval.filings && (
        <p className="small">Filing page retrieval: a gold evidence page is among the top three pages for {pct(d.retrieval.filings.financebench_open["recall@3"].value)} of questions.</p>
      )}
    </>
  );
}

// ------------------------------------------------------------------ methodology
function Methodology({ d }: { d: Data }) {
  const s = d.datasets.summary;
  return (
    <>
      <h1>Methodology</h1>
      <p className="lede">How items are chosen, de-duplicated and scored. Every rule is implemented in the open harness and covered by tests.</p>
      <h2>Read this before quoting a number</h2>
      <ul className="rules">
        <li>Published and reproduced scores are different measurements. A published score uses the paper's own items and scorer; check the "Evaluated on" column.</li>
        <li>Reproduced rows show a bootstrap confidence interval. Models whose intervals overlap should not be ranked against each other.</li>
        <li>Our runs use open models on a laptop GPU, quantised, with greedy decoding. Closed models appear only as published numbers until we have API access.</li>
        <li>FinTagging runs use the subsets released on GitHub, not the full gated sets the paper scores.</li>
      </ul>
      <h2>De-duplication</h2>
      <ul className="rules">
        <li>Items are joined only when they share a FinanceBench id or have identical text after normalisation (case, spacing, number formatting, enumeration prefixes). This joined {int(s.joins.exact_text)} pairs by text and {int(s.joins.same_source_id)} by id.</li>
        <li>Near-identical items are never joined automatically: in this data they are mostly distinct XBRL elements ("Due from" vs "Due to") or templated questions about another company. Cross-source near pairs go to human review ({int(s.review_pending)} pending).</li>
        <li>When copies disagree on the answer, the original publisher's answer is kept and the item is flagged. Identical inputs with different answers inside one dataset are marked ambiguous and left out of the primary score.</li>
        <li>Each unique item belongs to exactly one split, and a few-shot example is never taken from the test item's own filing.</li>
      </ul>
      <h2>Scoring</h2>
      <ul className="rules">
        <li><b>Concept tagging:</b> exact match of the predicted US-GAAP concept, as in FinTagging's own scorer; a case- and prefix-insensitive variant is reported as sensitivity.</li>
        <li><b>Fact extraction:</b> micro precision, recall and F1 over (fact, type) pairs, pooled over items.</li>
        <li><b>Financial calculation:</b> a number in the answer's final segment matches the gold to two decimals or within a small relative tolerance; percentages are read as fractions when the gold is a fraction.</li>
        <li><b>Filing QA:</b> a cross-family LLM judge labels answers correct, incorrect or failed, as in FinanceBench's human grading. Refusals are caught by a rule first. The judge is checked against two human labellers before its scores are treated as primary.</li>
      </ul>
      <h2>Judge validation</h2>
      <div className="notice info">Pending: human labels are collected after the first filing-QA runs.</div>
    </>
  );
}

// ------------------------------------------------------------------ datasets
function Datasets({ d }: { d: Data }) {
  const s = d.datasets.summary;
  const ov = d.datasets.overlap;
  const full = ov.pairs.filter((p: any) => p.share >= 0.999);
  return (
    <>
      <h1>Datasets</h1>
      <p className="lede">Sources are pinned to exact commits and every file is hash-checked. Counts below are computed from the files.</p>
      <div className="grid">
        <div className="card stat"><div className="k">Source items</div><div className="v">{int(s.records_loaded)}</div></div>
        <div className="card stat"><div className="k">Unique items</div><div className="v">{int(s.clusters)}</div></div>
        <div className="card stat"><div className="k">Items found in more than one source</div><div className="v">{int(s.multi_member_clusters)}</div></div>
        <div className="card stat"><div className="k">Answer conflicts flagged</div><div className="v">{int(d.datasets.conflicts.length)}</div></div>
      </div>
      <h2>Sources</h2>
      <div className="table-scroll"><table>
        <thead><tr><th>Source</th><th>Pinned at</th><th>Licence</th><th>Files</th></tr></thead>
        <tbody>{d.datasets.sources.map((x: any) => (
          <tr key={x.key}><td>{x.title}<div className="small mono">{x.repo}</div></td><td className="mono">{x.commit.slice(0, 10)}</td><td>{x.licence}</td><td className="num">{x.files}</td></tr>))}</tbody>
      </table></div>
      <h2>Fully contained datasets</h2>
      <p className="lede">Every item of the left dataset also appears in the right one, so they are not independent sources.</p>
      <div className="table-scroll"><table>
        <thead><tr><th>Dataset</th><th>Contained in</th><th>Items</th></tr></thead>
        <tbody>{full.map((p: any, i: number) => (
          <tr key={i}><td className="mono">{p.dataset}</td><td className="mono">{p.in_dataset}</td><td className="num">{int(p.overlap)} / {int(p.size)}</td></tr>))}</tbody>
      </table></div>
      <h2>Benchmark size after de-duplication</h2>
      <div className="table-scroll"><table>
        <thead><tr><th>Task and split</th><th>Items</th><th>Primary score</th></tr></thead>
        <tbody>{Object.entries(s.items as Record<string, number>).map(([k, v]) => (
          <tr key={k}><td className="mono">{k}</td><td className="num">{int(v)}</td><td className="num">{int(s.primary_items[k])}</td></tr>))}</tbody>
      </table></div>
      <h2>Answer conflicts</h2>
      <div className="table-scroll"><table>
        <thead><tr><th>Task and kind</th><th>Items</th></tr></thead>
        <tbody>{Object.entries(s.conflicts as Record<string, number>).map(([k, v]) => (
          <tr key={k}><td className="mono">{k}</td><td className="num">{int(v)}</td></tr>))}</tbody>
      </table></div>
    </>
  );
}

// ------------------------------------------------------------------ reproduce
function Reproduce() {
  return (
    <>
      <h1>Reproduce</h1>
      <p className="lede">Everything on this site is regenerated from source with these commands.</p>
      <pre className="cmd">{`python -I -m fineval.fetch       # download pinned sources, verify hashes
python -I -m fineval.build       # load, de-duplicate, split
python -I -m pytest -q           # exit tests for every phase
python -I -m fineval.run --model ollama:qwen2.5:7b --task financial_calc --track closed
python -I -m fineval.score --run <run name>
python -I -m fineval.export      # data for this site`}</pre>
      <h2>Submitting a model</h2>
      <p>Run the harness on the full test split for every task and track, then share the generation and score files. Reproduced rows always list the model digest, seed and harness commit.</p>
    </>
  );
}

export default function App() {
  const page = usePage();
  const [d, setD] = useState<Data | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [theme, setTheme] = useState<string | null>(() => { try { return localStorage.getItem("theme"); } catch { return null; } });
  useEffect(() => { load().then(setD).catch((e) => setErr(String(e))); }, []);
  useEffect(() => {
    if (theme) document.documentElement.dataset.theme = theme; else delete document.documentElement.dataset.theme;
    try { theme ? localStorage.setItem("theme", theme) : localStorage.removeItem("theme"); } catch { /* storage unavailable */ }
  }, [theme]);
  const dark = theme ? theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  return (
    <>
      <header className="top">
        <div className="wrap top-inner">
          <div className="brand">Fin<span>Eval</span></div>
          <nav className="tabs">
            {PAGES.map((p) => <a key={p} href={`#${p}`} className={p === page ? "on" : ""}>{LABEL[p]}</a>)}
          </nav>
          <button className="theme-btn" onClick={() => setTheme(dark ? "light" : "dark")}>{dark ? "Light" : "Dark"} mode</button>
        </div>
      </header>
      <main className="wrap">
        {err && <div className="notice">Could not load data: {err}</div>}
        {!d && !err && <div className="empty">Loading…</div>}
        {d && page === "leaderboard" && <Leaderboard d={d} />}
        {d && page === "compare" && <Compare d={d} />}
        {d && page === "tasks" && <Tasks d={d} />}
        {d && page === "methodology" && <Methodology d={d} />}
        {d && page === "datasets" && <Datasets d={d} />}
        {page === "reproduce" && <Reproduce />}
      </main>
      <footer><div className="wrap">FinEval v1 · XBRL-Agent, FinanceBench, FinTagging and the Regulations Challenge, de-duplicated and scored under one setup · Dev Gaglani and Stavan Desai</div></footer>
    </>
  );
}

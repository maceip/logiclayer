const BLOCKS = [
  "Access Control",
  "Analytical Intelligence",
  "Asset Delivery",
  "Background Processing",
  "Connectivity Layer",
  "Core Rendering",
  "Data Persistence",
  "Data Sovereignty",
  "Error Boundaries",
  "Global Interface",
  "Interaction Design",
  "Network Edge",
  "Persistence Strategy",
  "Resiliency",
  "Search Architecture",
  "Security Ops",
  "State Management",
  "System Telemetry",
  "Traffic Control",
  "User Observability",
  "Visual Systems",
];

const SIGNALS = [
  ["Access Control", /\b(auth|session|password|jwt|bearer|rbac|permission|role|guard|login|signup)\b/i, 2.0, "auth/session token"],
  ["Data Persistence", /\b(prisma|database|postgres|sqlite|mysql|mongodb|schema|migration|model|supabase|drizzle|redis|query)\b/i, 2.0, "database/schema token"],
  ["Network Edge", /\b(elysia|express|hono|fastify|router|route|middleware|request|response|fetch|axios|webhook|endpoint)\b/i, 1.7, "network edge token"],
  ["System Telemetry", /\b(telemetry|logger?|log\.|tracer|metric|sentry|otel|opentelemetry)\b/i, 1.8, "observability token"],
  ["Security Ops", /\b(secret|api[_-]?key|encrypt|decrypt|hash|salt|csrf|cors|helmet)\b/i, 1.5, "security token"],
  ["Traffic Control", /\b(rate[_-]?limit|throttle|quota|load balanc|proxy)\b/i, 1.4, "traffic control token"],
  ["Background Processing", /\b(queue|worker|job|task|schedule|cron|bullmq)\b/i, 1.7, "async processing token"],
  ["Search Architecture", /\b(search|index|meilisearch|typesense|elastic|opensearch)\b/i, 1.7, "search/index token"],
  ["Analytical Intelligence", /\b(warehouse|etl|analytics|segment|amplitude|mixpanel|report)\b/i, 1.5, "analytics token"],
  ["Data Sovereignty", /\b(gdpr|privacy|retention|archive|pii|cookie|consent)\b/i, 1.4, "privacy token"],
  ["Resiliency", /\b(retry|fallback|circuit|backup|restore|catch|try\s*\{)\b/i, 1.2, "resilience token"],
  ["State Management", /\b(zustand|redux|context|useReducer|store|atom|signal)\b/i, 1.5, "state token"],
  ["Core Rendering", /(jsx|tsx|render|component|className|<\/)/i, 1.3, "render token"],
  ["Interaction Design", /\b(onClick|onSubmit|form|button|input|navigate|router\.push)\b/i, 1.3, "interaction token"],
  ["Asset Delivery", /\b(vite|webpack|rollup|bundle|asset|image|font|css|tailwind)\b/i, 1.2, "asset/build token"],
  ["Error Boundaries", /\b(error boundary|fallback ui|componentDidCatch|useErrorBoundary)\b/i, 1.7, "frontend fault boundary"],
];

const PATH_SIGNALS = [
  ["Data Persistence", /(^|\/)prisma(\/|\.config)|(^|\/)schema\.prisma$|(^|\/)lib\/prisma\./i, 2.3, "persistence path"],
  ["Persistence Strategy", /(^|\/)(libs?\/)?cache(\/|\.)|(^|\/)cache\./i, 4.2, "cache path"],
  ["Background Processing", /(^|\/)(bull|queues?|workers?)(\/|\.)|(^|\/).*(queue|worker)[^/]*\./i, 3.2, "queue/worker path"],
  ["Global Interface", /(^|\/)(env|environment)\.config\.|(^|\/)config\/(env|environment)\./i, 2.6, "environment interface path"],
  ["System Telemetry", /(^|\/)(logger|telemetry|tracing)\./i, 2.0, "telemetry path"],
  ["Access Control", /(^|\/)(auth|passwords?|sessions?|permissions?)[^/]*\./i, 1.7, "access-control path"],
  ["Security Ops", /(^|\/)utils\/security\./i, 2.2, "security utility path"],
  ["Network Edge", /(^|\/)(api|routes?|controllers?|handlers?)\//i, 1.8, "route path"],
  ["Core Rendering", /(^|\/)(app|pages|components|views|screens)\//i, 1.3, "rendering path"],
  ["Connectivity Layer", /(^|\/)(services?|adapters|providers|clients?)\//i, 1.2, "service layer path"],
  ["Search Architecture", /(^|\/)(index|config\/index|database\/index|middlewares\/index|modules\/index|modules\/[^/]+\/index)\.(ts|tsx|js|jsx)$/i, 2.4, "architectural index path"],
];

const SOURCE_EXTENSIONS = /\.(ts|tsx|js|jsx|mjs|cjs|py|go|prisma|java|rs|cpp|cc|cxx|h|hpp|cs|rb|php|swift|kt)$/i;
const SKIP_PATHS = /(^|\/)(node_modules|\.git|dist|build|target|vendor|coverage|\.next|\.venv|\.venv-win|__pycache__)\//i;
const FEATURED_CASES = ["openai/codex", "denoland/deno", "go-gitea/gitea", "zed-industries/zed", "immich-app/immich", "apache/hadoop"];
const REPO_PATTERN = /^[A-Za-z0-9_.-]{1,100}\/[A-Za-z0-9_.-]{1,100}$/;

const state = {
  currentRepo: "openai/codex",
  surfaces: [],
  reference: null,
  backendAvailable: false,
  isAnalyzing: false,
  latestReceipt: null,
  latestBadge: null,
  signalAggregate: { total: 3, ok: 3, nodeCount: 1400, edgeCount: 4200 },
  heartbeatRunning: false,
};

const $ = (id) => document.getElementById(id);

document.addEventListener("DOMContentLoaded", async () => {
  $("repo-form").addEventListener("submit", onRepoSubmit);
  $("badge-copy").addEventListener("click", copyBadgeMarkdown);
  $("badge-download").addEventListener("click", downloadBadgeSvg);

  const params = new URLSearchParams(window.location.search);
  const initialRepo = normalizeRepo(params.get("repo") || $("repo-input").value);
  if (initialRepo) {
    state.currentRepo = initialRepo;
    $("repo-input").value = initialRepo;
  }

  renderCaseBoard();
  renderEmptyResults();
  renderEmptyBadge();
  startHeartbeat();
  await Promise.allSettled([loadReferenceMetrics(), detectBackend()]);

  if (params.get("autorun") === "1" && initialRepo) {
    ingestRepo(initialRepo);
  }
});

async function onRepoSubmit(event) {
  event.preventDefault();
  const repo = normalizeRepo($("repo-input").value);
  if (!repo) {
    setStatus("Enter a root GitHub URL or owner/name, for example openai/codex.", true);
    return;
  }
  $("repo-input").value = repo;
  await ingestRepo(repo);
}

async function ingestRepo(repo) {
  if (state.isAnalyzing) {
    setStatus("Analysis is already running. Please wait for this repository to finish.");
    return;
  }
  state.currentRepo = repo;
  state.isAnalyzing = true;
  const button = document.querySelector("#repo-form button[type='submit']");
  button.classList.add("is-loading");
  button.disabled = true;
  button.textContent = "Analyzing";
  setStatus(`Starting LogicLens analysis for ${repo}...`);

  try {
    if (state.backendAvailable) {
      await ingestRepoHosted(repo);
    } else {
      await ingestRepoStaticPreview(repo);
    }
  } catch (error) {
    setStatus(`Analysis stopped: ${error.message}`, true);
    renderFailureBadge(repo, error);
  } finally {
    state.isAnalyzing = false;
    button.classList.remove("is-loading");
    button.disabled = false;
    button.textContent = "Analyze repo";
  }
}

async function detectBackend() {
  try {
    const health = await fetchJson("./api/health");
    state.backendAvailable = Boolean(health.ok);
    $("runtime-mode").textContent = `hosted backend API; ${health.active_jobs}/${health.max_active_jobs} active jobs`;
    setStatus("Hosted analyzer ready for a public GitHub repository.");
  } catch {
    state.backendAvailable = false;
    $("runtime-mode").textContent = "GitHub Pages static preview";
    setStatus("Hosted analyzer not detected; browser preview mode is ready.");
  }
}

async function ingestRepoHosted(repo) {
  setStatus(`Submitting hosted backend job for ${repo}.`);
  const response = await fetch("./api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ repo }),
  });
  const job = await response.json();
  if (!response.ok) throw new Error(job.error || `API returned ${response.status}`);

  setStatus(`Hosted job ${job.job_id} queued for ${repo}.`);
  const completed = await pollJob(job.job_id);
  if (completed.status !== "succeeded") throw new Error(completed.error || "Hosted analysis failed.");

  const result = completed.result;
  state.latestReceipt = result;
  state.surfaces = normalizeHostedSurfaces(result.surfaces || []);
  renderRepoResults(result);
  renderRuntimeReceipt(result);
  updateBadge(buildBadgeData({ repo, mode: "hosted", surfaces: state.surfaces, result }));
  setStatus(`Analysis complete for ${repo}: ${formatNumber(result.summary.node_count)} nodes and ${formatNumber(result.summary.edge_count)} edges.`);
}

async function pollJob(jobId) {
  for (let attempt = 0; attempt < 240; attempt += 1) {
    const job = await fetchJson(`./api/jobs/${encodeURIComponent(jobId)}`);
    if (job.status === "succeeded" || job.status === "failed") return job;
    const detail = job.message || (job.status === "running" ? "Hosted analyzer is running." : "Hosted analyzer is queued.");
    setStatus(`Hosted job ${jobId}: ${detail}`);
    await sleep(attempt < 5 ? 900 : 1800);
  }
  throw new Error("Hosted analysis timed out in the browser.");
}

function normalizeHostedSurfaces(surfaces) {
  return surfaces.map((surface) => ({
    path: surface.path || surface.file_path || surface.name || "unknown",
    name: surface.name || "",
    block: BLOCKS.includes(surface.block) ? surface.block : surface.block || "Search Architecture",
    confidence: clamp(Number(surface.confidence || 0.5), 0, 1),
    signal: surface.signal || "backend evidence",
    language: surface.language || "",
    kind: surface.kind || "",
  }));
}

async function ingestRepoStaticPreview(repo) {
  setStatus(`Reading GitHub metadata for ${repo}.`);
  const meta = await fetchGitHubJson(repo, "");
  const defaultBranch = meta.default_branch || "main";
  const branch = await fetchGitHubJson(repo, `branches/${encodeURIComponent(defaultBranch)}`);
  const treeSha = branch.commit?.commit?.tree?.sha || branch.commit?.sha;
  if (!treeSha) throw new Error(`Could not resolve default branch tree for ${repo}.`);

  const tree = await fetchGitHubJson(repo, `git/trees/${encodeURIComponent(treeSha)}?recursive=1`);
  const files = (tree.tree || [])
    .filter((item) => item.type === "blob" && SOURCE_EXTENSIONS.test(item.path) && !SKIP_PATHS.test(item.path) && Number(item.size || 0) <= 512000)
    .slice(0, 350);
  if (!files.length) throw new Error("No supported source files found in the GitHub tree.");

  const truncated = tree.truncated ? " GitHub returned a truncated tree, so this is a bounded preview." : "";
  setStatus(`Classifying ${files.length} source surfaces from ${repo}; sampling content from the first ${Math.min(files.length, 70)} files.${truncated}`);
  const contentMap = await fetchSampledContent(repo, files.slice(0, 70));
  state.latestReceipt = null;
  state.surfaces = files.map((file) => classifySurface(file.path, contentMap.get(file.path) || "", file));
  renderRepoResults(null);
  renderRuntimeReceipt(null, {
    repo,
    mode: "browser preview",
    fileCount: state.surfaces.length,
    sampledCount: contentMap.size,
    warning: tree.truncated ? "GitHub tree was truncated." : "",
  });
  updateBadge(buildBadgeData({ repo, mode: "static", surfaces: state.surfaces, result: null, warning: tree.truncated ? "truncated tree" : "" }));
  setStatus(`Preview analysis complete for ${repo}: ${state.surfaces.length} file surfaces classified.`);
}

async function fetchSampledContent(repo, files) {
  const out = new Map();
  const batches = [];
  for (let i = 0; i < files.length; i += 8) batches.push(files.slice(i, i + 8));
  for (const batch of batches) {
    await Promise.all(
      batch.map(async (file) => {
        try {
          const blob = await fetchGitHubJson(repo, `git/blobs/${encodeURIComponent(file.sha)}`);
          if (blob.encoding === "base64" && blob.content) {
            out.set(file.path, decodeBase64Utf8(blob.content).slice(0, 5000));
          }
        } catch {
          out.set(file.path, "");
        }
      }),
    );
  }
  return out;
}

function classifySurface(path, content, file = {}) {
  const scores = new Map();
  const evidence = new Map();
  const hay = `${path} ${content.slice(0, 2600)}`;
  addScore(scores, evidence, "Search Architecture", 0.65, "source file in graph candidate set");

  for (const [block, pattern, weight, label] of PATH_SIGNALS) {
    if (pattern.test(path)) addScore(scores, evidence, block, weight, label);
  }
  for (const [block, pattern, weight, label] of SIGNALS) {
    if (pattern.test(hay)) addScore(scores, evidence, block, weight, label);
  }

  const exportCount = (content.match(/\bexport\b/g) || []).length;
  const importCount = (content.match(/\bimport\b/g) || []).length;
  const functionCount = (content.match(/\b(function|def|class|interface|struct|enum)\b/g) || []).length;
  if (/\/?index\.(ts|tsx|js|jsx)$/i.test(path)) addScore(scores, evidence, "Search Architecture", 2.0 + Math.min(exportCount, 4) * 0.25, "index/barrel surface");
  if (/(^|\/)(config|env|settings|drizzle|prisma)(\/|\.)/i.test(path)) addScore(scores, evidence, "Global Interface", 1.6, "configuration boundary");
  if (importCount >= 2 && exportCount >= 1) addScore(scores, evidence, "Connectivity Layer", 0.8, "bridges imports and exports");
  if (functionCount >= 6) addScore(scores, evidence, "Core Rendering", 0.4, "dense code surface");

  const ranked = [...scores.entries()].sort((a, b) => b[1] - a[1]);
  const [primary, score] = ranked[0] || ["Search Architecture", 0.1];
  const runnerUp = ranked[1]?.[1] || 0;
  const confidence = Math.min(0.42 + 0.08 * score + 0.06 * Math.max(score - runnerUp, 0), 0.95);
  return {
    path,
    name: path.split("/").pop(),
    block: primary,
    confidence,
    signal: (evidence.get(primary) || ["low signal fallback"]).slice(0, 3).join(", "),
    language: languageFromPath(path),
    kind: file.type || "blob",
  };
}

function addScore(scores, evidence, block, weight, label) {
  scores.set(block, (scores.get(block) || 0) + weight);
  evidence.set(block, [...(evidence.get(block) || []), label]);
}

function renderRepoResults(result) {
  renderOperatorAnswers(result);
  const counts = countBy(state.surfaces, (surface) => surface.block);
  const rows = [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 10);
  drawBarChart($("repo-block-chart"), rows, { title: "Primary architecture block count", suffix: " surfaces" });
  $("block-list").innerHTML = rows
    .map(([block, count]) => `<div class="block-pill"><strong>${escapeHtml(block)}</strong><span>${formatNumber(count)} evidence surfaces</span></div>`)
    .join("");
  $("surface-table").innerHTML = state.surfaces
    .slice()
    .sort((a, b) => b.confidence - a.confidence)
    .slice(0, 80)
    .map(
      (surface) =>
        `<tr><td>${escapeHtml(surface.path)}</td><td>${escapeHtml(surface.block)}</td><td>${Math.round(surface.confidence * 100)}%</td><td>${escapeHtml(surface.signal)}</td></tr>`,
    )
    .join("");
  renderBlockTree();
}

function renderEmptyResults() {
  drawBarChart($("repo-block-chart"), [], { title: "Primary architecture block count", suffix: " surfaces" });
  $("answer-grid").innerHTML = `
    <article class="answer-card">
      <strong>Run a repo to get a map.</strong>
      <p>The analyzer will classify file and code surfaces into likely architecture blocks, then show concrete evidence rows.</p>
    </article>
    <article class="answer-card">
      <strong>Why LogicLens?</strong>
      <p>The paper's core idea is graph-backed software understanding. This implementation exposes that idea through practical repo analysis.</p>
    </article>`;
  $("block-list").innerHTML = `<div class="block-pill"><strong>Waiting for analysis</strong><span>Submit a public GitHub repository.</span></div>`;
  $("surface-table").innerHTML = `<tr><td colspan="4">No repository analyzed yet.</td></tr>`;
  $("block-tree").innerHTML = `<div class="empty-card">No repository tree yet.</div>`;
}

function renderOperatorAnswers(result) {
  const insights = result?.insights?.length ? result.insights : buildPreviewInsights();
  $("answer-grid").innerHTML = insights
    .map((insight) => {
      const samples = insight.samples || [];
      const blocks = insight.dominant_blocks || [];
      return `
        <article class="answer-card">
          <strong>${escapeHtml(insight.title)}</strong>
          <p>${escapeHtml(insight.answer)}</p>
          ${
            samples.length
              ? `<ul>${samples.map(renderInsightSample).join("")}</ul>`
              : blocks.length
                ? `<ul>${blocks.map((block) => `<li><span>${escapeHtml(block.block)}</span><small>${formatNumber(block.count)} surfaces</small></li>`).join("")}</ul>`
                : `<em>${escapeHtml(insight.empty_state || "No evidence returned.")}</em>`
          }
        </article>`;
    })
    .join("");
}

function renderInsightSample(sample) {
  return `<li><span>${escapeHtml(sample.path || sample.file_path || sample.name)}</span><small>${escapeHtml(sample.block || "")} / ${Math.round(Number(sample.confidence || 0) * 100)}%</small></li>`;
}

function buildPreviewInsights() {
  const counts = [...countBy(state.surfaces, (surface) => surface.block).entries()].sort((a, b) => b[1] - a[1]);
  const sensitiveBlocks = new Set(["Access Control", "Security Ops", "Data Persistence", "Network Edge", "Background Processing"]);
  const sensitive = state.surfaces.filter((surface) => sensitiveBlocks.has(surface.block)).sort((a, b) => b.confidence - a.confidence).slice(0, 5);
  const highSignal = state.surfaces.slice().sort((a, b) => b.confidence - a.confidence).slice(0, 5);
  const lowConfidence = state.surfaces.slice().sort((a, b) => a.confidence - b.confidence).slice(0, 5);

  return [
    {
      title: "What architecture blocks dominate?",
      answer: "The top labels show the repo areas LogicLens can identify from path and source evidence in this run.",
      dominant_blocks: counts.slice(0, 5).map(([block, count]) => ({ block, count })),
      empty_state: "No block distribution available.",
    },
    {
      title: "Where are the sensitive seams?",
      answer: "Start review around auth, security, persistence, network, and background-work surfaces.",
      samples: sensitive,
      empty_state: "No sensitive architecture seams found in the bounded result window.",
    },
    {
      title: "Which files have the clearest evidence?",
      answer: "These rows have the highest combined path and code signals, making them good anchors for manual inspection.",
      samples: highSignal,
      empty_state: "No high-confidence evidence rows found.",
    },
    {
      title: "What should a reviewer inspect next?",
      answer: "Lower-confidence rows are where a human reviewer can improve labels or ask deeper graph questions.",
      samples: lowConfidence,
      empty_state: "No low-confidence rows returned.",
    },
  ];
}

function renderRuntimeReceipt(result, preview = null) {
  if (result) {
    const integrity = result.summary?.graph_integrity?.overall_status || "unknown";
    const manifest = result.summary?.manifest?.required_artifacts_present ? "manifest complete" : "manifest incomplete";
    const artifactId = String(result.artifact_dir || "").split(/[\\/]/).filter(Boolean).pop() || "artifact saved";
    $("runtime-mode").textContent = `hosted backend API; ${result.runtime_capabilities?.structural_ingest || "structural ingest"}`;
    $("runtime-receipt").textContent = `${manifest}; graph integrity ${integrity}; artifact ${artifactId}`;
    return;
  }
  if (preview) {
    $("runtime-mode").textContent = "GitHub Pages static preview";
    $("runtime-receipt").textContent = `${preview.fileCount} file surfaces; ${preview.sampledCount} sampled blobs${preview.warning ? `; ${preview.warning}` : ""}`;
    return;
  }
  $("runtime-receipt").textContent = "No completed analysis yet.";
}

function renderBlockTree() {
  const byDirectory = new Map();
  for (const surface of state.surfaces) {
    const parts = surface.path.split("/");
    const directory = parts.length > 1 ? parts[0] : ".";
    if (!byDirectory.has(directory)) byDirectory.set(directory, []);
    byDirectory.get(directory).push(surface);
  }

  const branches = [...byDirectory.entries()]
    .map(([directory, surfaces]) => ({
      directory,
      total: surfaces.length,
      blockCounts: [...countBy(surfaces, (surface) => surface.block).entries()].sort((a, b) => b[1] - a[1]).slice(0, 4),
    }))
    .sort((a, b) => b.total - a.total)
    .slice(0, 8);

  $("block-tree").innerHTML = `
    <div class="trees-root" role="tree" aria-label="Detected architecture block tree">
      <div class="trees-row repo-row" role="treeitem" aria-level="1" aria-expanded="true">
        <span class="trees-twist" aria-hidden="true">+</span>
        <span class="trees-label">${escapeHtml(state.currentRepo)}</span>
      </div>
      ${branches
        .map(
          (branch) => `
            <div class="trees-branch" role="group">
              <div class="trees-row" role="treeitem" aria-level="2" aria-expanded="true">
                <span class="trees-indent" aria-hidden="true"></span>
                <span class="trees-twist" aria-hidden="true">+</span>
                <span class="trees-label">${escapeHtml(branch.directory)}/</span>
                <span class="trees-count">${formatNumber(branch.total)} surfaces</span>
              </div>
              ${branch.blockCounts
                .map(
                  ([block, count]) => `
                    <div class="trees-row trees-leaf" role="treeitem" aria-level="3">
                      <span class="trees-indent" aria-hidden="true"></span>
                      <span class="trees-indent" aria-hidden="true"></span>
                      <span class="trees-twist" aria-hidden="true"></span>
                      <span class="trees-label">${escapeHtml(block)}</span>
                      <span class="trees-count">${formatNumber(count)}</span>
                    </div>`,
                )
                .join("")}
            </div>`,
        )
        .join("")}
    </div>`;
}

function renderEmptyBadge() {
  $("badge-preview").innerHTML = `<div class="badge-empty">Run an analysis to generate a badge.</div>`;
  $("badge-markdown").value = "";
  $("badge-copy").disabled = true;
  $("badge-download").disabled = true;
}

function renderFailureBadge(repo, error) {
  updateBadge({
    repo,
    mode: "failed",
    modeLabel: "Analysis failed",
    status: "needs review",
    score: 0,
    grade: "FAIL",
    nodes: 0,
    edges: 0,
    files: 0,
    topBlocks: [],
    integrity: "not run",
    completedAt: new Date(),
    warning: error.message,
    primaryMetric: "failed",
    coverageLabel: "no badgeable result",
  });
}

function buildBadgeData({ repo, mode, surfaces, result, warning = "" }) {
  const counts = [...countBy(surfaces, (surface) => surface.block).entries()].sort((a, b) => b[1] - a[1]);
  const files = new Set(surfaces.map((surface) => surface.path)).size;
  const nodes = Number(result?.summary?.node_count || surfaces.length || 0);
  const edges = Number(result?.summary?.edge_count || 0);
  const avgConfidence = surfaces.length ? surfaces.reduce((sum, surface) => sum + Number(surface.confidence || 0), 0) / surfaces.length : 0;
  const integrity = result?.summary?.graph_integrity?.overall_status || (mode === "hosted" ? "unknown" : "preview");
  const manifestOk = Boolean(result?.summary?.manifest?.required_artifacts_present);
  const score = scoreAnalysis({ mode, nodes, files, avgConfidence, integrity, manifestOk });
  const grade = score >= 90 ? "A" : score >= 80 ? "B" : score >= 70 ? "C" : mode === "static" ? "PREVIEW" : "REVIEW";
  return {
    repo,
    mode,
    modeLabel: mode === "hosted" ? "Hosted backend graph" : "Browser GitHub preview",
    status: mode === "hosted" ? "graph receipt" : "bounded preview",
    score,
    grade,
    nodes,
    edges,
    files,
    topBlocks: counts.slice(0, 3).map(([block, count]) => ({ block, count })),
    integrity,
    completedAt: new Date(),
    warning,
    primaryMetric: mode === "hosted" ? `${compactNumber(nodes)} nodes` : `${formatNumber(files)} files`,
    coverageLabel: mode === "hosted" ? "backend graph" : "static preview",
  };
}

function scoreAnalysis({ mode, nodes, files, avgConfidence, integrity, manifestOk }) {
  const confidenceScore = Math.round((avgConfidence || 0.55) * 100);
  const volumeScore = Math.min(20, Math.round(Math.log10(Math.max(nodes, files, 1)) * 8));
  const graphBonus = mode === "hosted" ? 14 : 0;
  const integrityBonus = /ok|pass|green|valid/i.test(String(integrity)) ? 10 : manifestOk ? 6 : 0;
  const previewBonus = mode === "static" ? 8 : 0;
  return clamp(Math.round(42 + confidenceScore * 0.28 + volumeScore + graphBonus + integrityBonus + previewBonus), mode === "static" ? 45 : 35, 98);
}

function updateBadge(data) {
  state.latestBadge = data;
  const svg = buildBadgeSvg(data);
  $("badge-preview").innerHTML = svg;
  $("badge-markdown").value = buildMarkdownBadge(data);
  $("badge-copy").disabled = false;
  $("badge-download").disabled = false;
}

function buildMarkdownBadge(data) {
  const color = data.score >= 90 ? "2f7d5a" : data.score >= 80 ? "2f5f8f" : data.score >= 70 ? "8a6f2a" : "8f3434";
  const message = encodeURIComponent(`${data.grade} ${data.score}% | ${data.primaryMetric}`);
  const badgeUrl = `https://img.shields.io/badge/LogicLens-${message}-${color}?style=flat-square&labelColor=1f2937`;
  const analyzerUrl = `${window.location.origin}${window.location.pathname}?repo=${encodeURIComponent(data.repo)}`;
  return `[![LogicLens analysis](${badgeUrl})](${analyzerUrl})`;
}

function buildBadgeSvg(data) {
  const width = 860;
  const height = 260;
  const blocks = data.topBlocks.length ? data.topBlocks : [{ block: "No block evidence", count: 0 }];
  const blockRows = blocks
    .map(
      (item, index) => `
        <g transform="translate(42 ${148 + index * 28})">
          <rect width="${Math.max(80, Math.min(390, item.count * 18 + 80))}" height="16" fill="${index === 0 ? "#2f5f8f" : index === 1 ? "#56738f" : "#78909c"}" opacity="0.88"/>
          <text x="12" y="12" font-size="12" fill="#ffffff">${escapeXml(item.block)} / ${formatNumber(item.count)}</text>
        </g>`,
    )
    .join("");
  const warning = data.warning ? `<text x="42" y="238" font-size="12" fill="#8a6f2a">${escapeXml(data.warning)}</text>` : "";

  return `
    <svg class="analysis-badge-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="LogicLens analysis badge for ${escapeAttribute(data.repo)}">
      <defs>
        <linearGradient id="badge-bg" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0%" stop-color="#edf1f6"/>
          <stop offset="100%" stop-color="#d7dee8"/>
        </linearGradient>
      </defs>
      <rect width="${width}" height="${height}" fill="url(#badge-bg)"/>
      <rect x="20" y="20" width="${width - 40}" height="${height - 40}" fill="#f7f9fb" stroke="#9aa8ba"/>
      <text x="42" y="58" font-family="Space Grotesk, Segoe UI, sans-serif" font-size="28" font-weight="700" fill="#263544">LogicLens analysis</text>
      <text x="42" y="84" font-family="JetBrains Mono, Consolas, monospace" font-size="14" fill="#516173">${escapeXml(data.repo)}</text>
      <text x="42" y="118" font-family="JetBrains Mono, Consolas, monospace" font-size="12" fill="#516173">${escapeXml(data.modeLabel)} / ${escapeXml(data.status)}</text>
      ${blockRows}
      <g transform="translate(585 42)">
        <rect width="220" height="158" fill="#263544"/>
        <text x="18" y="36" font-family="JetBrains Mono, Consolas, monospace" font-size="12" fill="#b7c2ce">score</text>
        <text x="18" y="92" font-family="Space Grotesk, Segoe UI, sans-serif" font-size="52" font-weight="700" fill="#ffffff">${escapeXml(data.grade)}</text>
        <text x="128" y="88" font-family="Space Grotesk, Segoe UI, sans-serif" font-size="30" font-weight="700" fill="#ffffff">${data.score}%</text>
        <text x="18" y="122" font-family="JetBrains Mono, Consolas, monospace" font-size="12" fill="#dbe3eb">${escapeXml(data.primaryMetric)}</text>
        <text x="18" y="145" font-family="JetBrains Mono, Consolas, monospace" font-size="12" fill="#dbe3eb">${formatNumber(data.edges)} edges / ${formatNumber(data.files)} files</text>
      </g>
      <text x="585" y="226" font-family="JetBrains Mono, Consolas, monospace" font-size="12" fill="#516173">Generated ${escapeXml(data.completedAt.toISOString().slice(0, 19))}Z</text>
      ${warning}
    </svg>`;
}

async function copyBadgeMarkdown() {
  const value = $("badge-markdown").value;
  if (!value) return;
  try {
    await navigator.clipboard.writeText(value);
    setStatus("Badge Markdown copied to clipboard.");
  } catch {
    $("badge-markdown").select();
    document.execCommand("copy");
    setStatus("Badge Markdown selected and copied.");
  }
}

function downloadBadgeSvg() {
  if (!state.latestBadge) return;
  const svg = buildBadgeSvg(state.latestBadge);
  const blob = new Blob([svg.trim(), "\n"], { type: "image/svg+xml" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `logiclens-${state.latestBadge.repo.replace(/[^A-Za-z0-9_.-]+/g, "-")}.svg`;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function loadReferenceMetrics() {
  try {
    state.reference = await fetchJson("./evals/trending-top50-ec2-summary-2026-04-27.json");
    const ok = Number(state.reference.by_status?.ok || 0);
    const total = Number(state.reference.total || 0);
    const languageRows = Object.entries(state.reference.by_language || {});
    const nodeCount = languageRows.reduce((sum, [, value]) => sum + Number(value.node_count || 0), 0);
    const edgeCount = languageRows.reduce((sum, [, value]) => sum + Number(value.edge_count || 0), 0);
    state.signalAggregate = { total, ok, nodeCount, edgeCount };
    $("reference-stats").innerHTML = `
      <span><strong>${formatNumber(total)}</strong> preserved reference repo runs</span>
      <span><strong>${formatNumber(ok)}</strong> successful corpus ingests</span>
      <span><strong>${compactNumber(nodeCount)}</strong> code nodes in the reference summary</span>`;
    renderCaseBoard();
  } catch {
    // The page works without the optional reference summary.
  }
}

function renderCaseBoard() {
  const resultByRepo = new Map((state.reference?.results || []).map((item) => [item.full_name, item]));
  $("case-grid").innerHTML = FEATURED_CASES.map((repo) => {
    const [owner, name] = repo.split("/");
    const result = resultByRepo.get(repo);
    const nodes = result?.node_count != null ? `${compactNumber(Number(result.node_count))} nodes` : "live run";
    const language = result?.language || "public repo";
    const status = result?.status === "ok" ? "reference ok" : "try now";
    return `
      <button class="case-card" type="button" data-repo="${escapeAttribute(repo)}">
        <span class="case-head">
          <img src="https://github.com/${escapeAttribute(owner)}.png?size=96" alt="" loading="lazy" />
          <span>
            <strong>${escapeHtml(name)}</strong>
            <span>${escapeHtml(owner)}</span>
          </span>
        </span>
        <span class="case-meta">
          <span>${escapeHtml(language)}</span>
          <span>${escapeHtml(status)}</span>
          <span>${escapeHtml(nodes)}</span>
        </span>
      </button>`;
  }).join("");
  document.querySelectorAll(".case-card").forEach((card) => {
    card.addEventListener("click", () => {
      const repo = card.getAttribute("data-repo");
      $("repo-input").value = repo;
      ingestRepo(repo);
    });
  });
}

function normalizeRepo(value) {
  let trimmed = String(value || "").trim();
  if (!trimmed) return "";
  trimmed = trimmed.replace(/[?#].*$/, "").replace(/\/+$/, "");

  const gitSsh = trimmed.match(/^git@github\.com:(?<owner>[^/\s]+)\/(?<repo>[^/\s]+?)(?:\.git)?$/i);
  if (gitSsh?.groups) {
    trimmed = `${gitSsh.groups.owner}/${gitSsh.groups.repo.replace(/\.git$/i, "")}`;
  } else {
    const githubUrl = trimmed.match(/^(?:https?:\/\/)?github\.com\/(?<path>[^?#]+)$/i);
    if (githubUrl?.groups) {
      const parts = githubUrl.groups.path.split("/").filter(Boolean);
      if (parts.length !== 2) return "";
      const repo = parts[1].replace(/\.git$/i, "");
      trimmed = `${parts[0]}/${repo}`;
    }
  }

  return REPO_PATTERN.test(trimmed) ? trimmed : "";
}

function fetchGitHubJson(repo, path) {
  const [owner, name] = repo.split("/");
  const base = `https://api.github.com/repos/${encodeURIComponent(owner)}/${encodeURIComponent(name)}`;
  const url = path ? `${base}/${path}` : base;
  return fetchJson(url);
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      Accept: "application/vnd.github+json",
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    const label = url.replace("https://api.github.com/", "GitHub API ");
    throw new Error(`${response.status} from ${label}`);
  }
  return response.json();
}

function decodeBase64Utf8(value) {
  const normalized = String(value).replace(/\s/g, "");
  const binary = atob(normalized);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return new TextDecoder("utf-8", { fatal: false }).decode(bytes);
}

function drawBarChart(canvas, rows, options = {}) {
  const ctx = canvas.getContext("2d");
  const { width, height } = canvas;
  const palette = ["#2f5f8f", "#56738f", "#78909c", "#2f7d5a", "#8a6f2a"];
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = cssHsl("--card");
  ctx.fillRect(0, 0, width, height);
  const max = Math.max(1, ...rows.map(([, value]) => value));
  const left = options.left || 178;
  const top = 44;
  const rightPad = 110;
  const rowHeight = Math.max(26, (height - top - 24) / Math.max(rows.length, 1));
  ctx.strokeStyle = cssHsl("--border", 0.52);
  ctx.lineWidth = 1;
  for (let x = left; x < width - rightPad; x += 92) {
    ctx.beginPath();
    ctx.moveTo(x, top - 8);
    ctx.lineTo(x, height - 18);
    ctx.stroke();
  }
  ctx.font = "18px Space Grotesk, Segoe UI, sans-serif";
  ctx.fillStyle = cssHsl("--foreground");
  ctx.fillText(options.title || "", 12, 26);
  rows.forEach(([label, value], index) => {
    const y = top + index * rowHeight + 8;
    const fullWidth = Math.max(40, width - left - rightPad);
    const barWidth = Math.max(2, (fullWidth * value) / max);
    ctx.fillStyle = cssHsl("--muted-foreground");
    ctx.font = "13px JetBrains Mono, Consolas, monospace";
    ctx.fillText(truncate(label, 22), 12, y + 14);
    ctx.fillStyle = cssHsl("--background");
    ctx.fillRect(left, y, fullWidth, Math.max(10, rowHeight - 13));
    ctx.strokeStyle = cssHsl("--border", 0.72);
    ctx.strokeRect(left, y, fullWidth, Math.max(10, rowHeight - 13));
    ctx.fillStyle = palette[index % palette.length];
    ctx.fillRect(left, y, barWidth, Math.max(10, rowHeight - 12));
    ctx.fillStyle = cssHsl("--foreground");
    ctx.fillText(`${compactNumber(value)}${options.suffix || ""}`, Math.min(left + barWidth + 8, width - rightPad + 8), y + 14);
  });
}

function startHeartbeat() {
  if (state.heartbeatRunning) return;
  state.heartbeatRunning = true;
  const tick = (time) => {
    drawOscilloscope($("vitals-scope"), state.signalAggregate, time);
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

function drawOscilloscope(canvas, aggregate, time = 0) {
  const ctx = canvas.getContext("2d");
  const { width, height } = canvas;
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = cssHsl("--card");
  ctx.fillRect(0, 0, width, height);
  ctx.strokeStyle = cssHsl("--border", 0.44);
  ctx.lineWidth = 1;
  for (let x = 40; x < width; x += 64) {
    ctx.beginPath();
    ctx.moveTo(x, 18);
    ctx.lineTo(x, height - 18);
    ctx.stroke();
  }
  for (let y = 32; y < height; y += 40) {
    ctx.beginPath();
    ctx.moveTo(22, y);
    ctx.lineTo(width - 22, y);
    ctx.stroke();
  }

  const okRatio = aggregate.total ? aggregate.ok / aggregate.total : 0.8;
  const density = Math.min(1, Math.log10(Math.max(aggregate.nodeCount, 1)) / 6);
  const phase = ((time || 0) / 1000) % 1.6;
  const beatCenter = phase / 1.6;
  const trace = [];
  for (let i = 0; i < 160; i += 1) {
    const t = i / 159;
    const drift = Math.sin((t + phase) * Math.PI * 6) * 7 + Math.sin((t + phase) * Math.PI * 18) * 2;
    const wrapDistance = Math.min(Math.abs(t - beatCenter), Math.abs(t + 1 - beatCenter), Math.abs(t - 1 - beatCenter));
    const qrs = wrapDistance < 0.008 ? -44 * okRatio : wrapDistance < 0.018 ? 42 * density : wrapDistance < 0.035 ? -16 : 0;
    const y = height * 0.5 + drift + qrs;
    trace.push([24 + t * (width - 48), Math.max(20, Math.min(height - 20, y))]);
  }

  ctx.strokeStyle = cssHsl("--primary");
  ctx.lineWidth = 3;
  ctx.beginPath();
  trace.forEach(([x, y], index) => {
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();
  ctx.fillStyle = cssHsl("--foreground");
  ctx.font = "18px Space Grotesk, Segoe UI, sans-serif";
  ctx.fillText("LogicLens analysis signal", 24, 32);
  ctx.fillStyle = cssHsl("--muted-foreground");
  ctx.font = "13px JetBrains Mono, Consolas, monospace";
  ctx.fillText(`${formatNumber(aggregate.total)} reference runs - ${formatNumber(aggregate.ok)} successful`, 24, height - 22);
}

function countBy(items, keyFn) {
  const out = new Map();
  for (const item of items) {
    const key = keyFn(item);
    out.set(key, (out.get(key) || 0) + 1);
  }
  return out;
}

function setStatus(message, isError = false) {
  const status = $("repo-status");
  status.textContent = message;
  status.style.color = isError ? cssHsl("--danger") : cssHsl("--muted-foreground");
}

function cssHsl(name, alpha = null) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  if (!value) return alpha == null ? "#000000" : `rgba(0, 0, 0, ${alpha})`;
  return alpha == null ? `hsl(${value})` : `hsl(${value} / ${alpha})`;
}

function languageFromPath(path) {
  const ext = path.split(".").pop()?.toLowerCase() || "";
  return (
    {
      ts: "TypeScript",
      tsx: "TypeScript",
      js: "JavaScript",
      jsx: "JavaScript",
      py: "Python",
      go: "Go",
      rs: "Rust",
      java: "Java",
      cpp: "C++",
      cc: "C++",
      cxx: "C++",
      h: "C/C++",
      hpp: "C++",
      cs: "C#",
      rb: "Ruby",
      php: "PHP",
      swift: "Swift",
      kt: "Kotlin",
      prisma: "Prisma",
    }[ext] || ext.toUpperCase()
  );
}

function compactNumber(value) {
  return Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(Number(value || 0));
}

function formatNumber(value) {
  return Intl.NumberFormat("en").format(Number(value || 0));
}

function truncate(value, length) {
  return String(value).length > length ? `${String(value).slice(0, length - 1)}...` : String(value);
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" })[char]);
}

function escapeAttribute(value) {
  return escapeHtml(value).replaceAll("\n", "&#10;");
}

function escapeXml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;" })[char]);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

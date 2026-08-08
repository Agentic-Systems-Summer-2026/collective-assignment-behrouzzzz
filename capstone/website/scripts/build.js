// scripts/build.js
// Reads data/content.json, writes a single self-contained dist/index.html.
// No dependencies. Run: node scripts/build.js

const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "..");
const data = JSON.parse(fs.readFileSync(path.join(ROOT, "data", "content.json"), "utf8"));

function esc(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function list(items) {
  return `<ul class="check-list">${items.map((i) => `<li>${esc(i)}</li>`).join("")}</ul>`;
}

function metricRow(metrics) {
  return `<div class="metrics">${metrics
    .map((m) => `<div class="metric"><div class="metric-value">${esc(m.value)}</div><div class="metric-label">${esc(m.label)}</div></div>`)
    .join("")}</div>`;
}

function figure(section) {
  if (!section.image) return "";
  return `<div class="figure"><img src="${esc(section.image)}" alt="${esc(section.image_alt || "")}" loading="lazy"></div>`;
}

const nav = [
  ["problem", "Problem"],
  ["solution", "Solution"],
  ["architecture", "Architecture"],
  ["workflow", "Workflow"],
  ["evaluation", "Evaluation"],
  ["governance", "Governance"],
  ["limitations", "Limitations"],
  ["future_work", "Future Work"],
]
  .map(([id, label]) => `<a href="#${id}">${label}</a>`)
  .join("");

const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${esc(data.project.name)}</title>
<meta name="description" content="${esc(data.project.tagline)}">
<style>
  :root {
    --navy: #1E2761;
    --navy-light: #2A3577;
    --ice: #CADCFC;
    --ice-dark: #3A4A8A;
    --white: #FFFFFF;
    --muted: #6B7280;
    --card: #F4F6FC;
    --green: #1E5C3A;
    --green-bg: #E8F3EC;
    --red: #8A3A3A;
    --red-bg: #F7EBEB;
    --warm: #8A6D3A;
    --warm-bg: #F7F1E8;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: Calibri, Arial, sans-serif;
    color: #1a1a1a;
    line-height: 1.6;
    background: var(--white);
  }
  h1, h2, h3 { font-family: Cambria, Georgia, serif; color: var(--navy); margin: 0; }
  a { color: var(--navy); }
  .container { max-width: 880px; margin: 0 auto; padding: 0 24px; }

  header.hero {
    background: var(--navy);
    color: var(--white);
    padding: 64px 0 56px;
  }
  header.hero h1 { color: var(--white); font-size: 2.4rem; margin-bottom: 14px; }
  header.hero .tagline { color: var(--ice); font-size: 1.15rem; max-width: 640px; margin-bottom: 28px; }
  .links { display: flex; gap: 12px; flex-wrap: wrap; }
  .links a { margin-right: 12px; margin-bottom: 12px; }
  .links a:last-child { margin-right: 0; }
  .btn {
    display: inline-block;
    padding: 10px 20px;
    border-radius: 6px;
    text-decoration: none;
    font-weight: bold;
    font-size: 0.95rem;
  }
  .btn-primary { background: var(--ice); color: var(--navy); }
  .btn-secondary { background: var(--navy-light); color: var(--white); border: 1px solid var(--ice-dark); }

  nav.subnav {
    position: sticky; top: 0; z-index: 10;
    background: var(--white);
    border-bottom: 1px solid #E5E7EB;
    padding: 12px 0;
  }
  nav.subnav .container { display: flex; gap: 20px; flex-wrap: wrap; }
  nav.subnav a { color: var(--muted); font-size: 0.9rem; text-decoration: none; font-weight: bold; margin-right: 20px; }
  nav.subnav a:last-child { margin-right: 0; }
  nav.subnav a:hover { color: var(--navy); }

  section { padding: 48px 0; border-bottom: 1px solid #EEF0F5; }
  section:last-of-type { border-bottom: none; }
  section h2 { font-size: 1.6rem; margin-bottom: 16px; }
  section p { font-size: 1.02rem; color: #333; max-width: 720px; }

  .check-list { list-style: none; padding: 0; margin: 16px 0 0; }
  .check-list li {
    padding: 10px 0 10px 28px;
    position: relative;
    font-size: 0.98rem;
    color: #333;
    border-bottom: 1px solid #F0F0F0;
  }
  .check-list li:before {
    content: "\\2022";
    color: var(--navy);
    font-weight: bold;
    position: absolute;
    left: 6px;
  }

  .figure { margin-top: 24px; }
  .figure img { max-width: 100%; border-radius: 10px; border: 1px solid #E5E7EB; }

  .metrics { display: flex; gap: 16px; flex-wrap: wrap; margin-top: 20px; }
  .metric { margin-right: 16px; margin-bottom: 16px; }
  .metric:last-child { margin-right: 0; }
  .metric {
    background: var(--card);
    border-radius: 10px;
    padding: 20px 24px;
    min-width: 160px;
  }
  .metric-value { font-family: Cambria, Georgia, serif; font-size: 2rem; font-weight: bold; color: var(--navy); }
  .metric-label { font-size: 0.85rem; color: var(--muted); margin-top: 6px; }
  .note { font-size: 0.85rem; color: var(--muted); font-style: italic; margin-top: 14px; }

  .governance-box { background: var(--warm-bg); border-radius: 10px; padding: 20px 24px; margin-top: 16px; }

  .limitations-box, .future-box { background: var(--card); border-radius: 10px; padding: 8px 24px; margin-top: 16px; }

  footer {
    background: var(--card);
    padding: 32px 0;
    text-align: center;
  }
  footer p { color: var(--muted); font-size: 0.88rem; margin: 0; }

  @media (max-width: 600px) {
    header.hero { padding: 40px 0 32px; }
    header.hero h1 { font-size: 1.8rem; }
    nav.subnav .container { gap: 12px; }
  }
</style>
</head>
<body>

<header class="hero">
  <div class="container">
    <h1>${esc(data.project.name)}</h1>
    <p class="tagline">${esc(data.project.tagline)}</p>
    <div class="links">
      <a class="btn btn-primary" href="${esc(data.project.repo_url)}">GitHub Repository</a>
      <a class="btn btn-secondary" href="${esc(data.project.demo_video_url)}">Demo Video</a>
      <a class="btn btn-secondary" href="${esc(data.project.final_report_url)}">Final Report</a>
    </div>
  </div>
</header>

<nav class="subnav"><div class="container">${nav}</div></nav>

<section id="problem"><div class="container">
  <h2>${esc(data.problem.heading)}</h2>
  <p>${esc(data.problem.body)}</p>
</div></section>

<section id="solution"><div class="container">
  <h2>${esc(data.solution.heading)}</h2>
  <p>${esc(data.solution.body)}</p>
</div></section>

<section id="architecture"><div class="container">
  <h2>${esc(data.architecture.heading)}</h2>
  <p>${esc(data.architecture.body)}</p>
  ${figure(data.architecture)}
</div></section>

<section id="workflow"><div class="container">
  <h2>${esc(data.workflow.heading)}</h2>
  <p>${esc(data.workflow.body)}</p>
  ${figure(data.workflow)}
</div></section>

<section id="evaluation"><div class="container">
  <h2>${esc(data.evaluation.heading)}</h2>
  <p>${esc(data.evaluation.body)}</p>
  ${metricRow(data.evaluation.metrics)}
  <p class="note">${esc(data.evaluation.note)}</p>
</div></section>

<section id="governance"><div class="container">
  <h2>${esc(data.governance.heading)}</h2>
  <div class="governance-box"><p style="margin:0;">${esc(data.governance.body)}</p></div>
</div></section>

<section id="limitations"><div class="container">
  <h2>${esc(data.limitations.heading)}</h2>
  <div class="limitations-box">${list(data.limitations.items)}</div>
</div></section>

<section id="future_work"><div class="container">
  <h2>${esc(data.future_work.heading)}</h2>
  <div class="future-box">${list(data.future_work.items)}</div>
</div></section>

<footer>
  <div class="container">
    <p>${esc(data.footer.note)}</p>
  </div>
</footer>

</body>
</html>
`;

fs.mkdirSync(path.join(ROOT, "dist"), { recursive: true });
fs.writeFileSync(path.join(ROOT, "dist", "index.html"), html);
console.log("Built dist/index.html");

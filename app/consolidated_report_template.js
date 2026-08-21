/**
 * consolidated_report_template.js
 * ----------------------------------
 * Renders the consolidated analysis JSON (Tier 1 + Tier 2 recruiting +
 * revenue-leak findings, plus pre-ranked priority items) into ONE
 * branded client-facing .docx covering both analysis areas.
 *
 * Usage:
 *   node consolidated_report_template.js <consolidated.json> <client_name> <output.docx>
 *
 * Presentation-only — all figures, rankings, and labels are computed in
 * Python (consolidated_report_generator.py) and simply rendered here,
 * the same pattern used by report_docx_template.js.
 */

const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell,
  WidthType, ShadingType, BorderStyle, ImageRun,
} = require("docx");
const fs = require("fs");
const path = require("path");

const [, , jsonPath, clientName, outPath] = process.argv;
if (!jsonPath || !clientName || !outPath) {
  console.error("Usage: node consolidated_report_template.js <consolidated.json> <client_name> <output.docx>");
  process.exit(1);
}

const data = JSON.parse(fs.readFileSync(jsonPath, "utf8"));

const LOGO_PATH = path.join(__dirname, "..", "assets", "pls_logo_dark_trimmed.png");
const LOGO_ASPECT = 770 / 1100;

const NAVY = "0B2545";
const CORAL = "E8604C";
const GRAY = "595959";

const SEVERITY_ICON = { CRITICAL: "\uD83D\uDD34", WARNING: "\uD83D\uDFE1", INFO: "\u26AA" };

const REVENUE_CATEGORY_LABELS = {
  missed_markup: "Missed / incorrect markup",
  stale_rate_card: "Stale rate card billing",
  off_contract_spend: "Off-contract / maverick spend",
  classification_risk: "Potential classification risk requiring review",
  hours_variance: "Unbilled / duplicate hours",
};

// ── STYLE HELPERS (same pattern as report_docx_template.js) ──

function logoHeader() {
  const width = 150;
  return [new Paragraph({
    spacing: { after: 220 },
    children: [new ImageRun({ data: fs.readFileSync(LOGO_PATH), transformation: { width, height: Math.round(width * LOGO_ASPECT) }, type: "png" })],
  })];
}
function docTitle(text) {
  return new Paragraph({
    spacing: { after: 240 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: CORAL, space: 6 } },
    children: [new TextRun({ text, bold: true, color: NAVY, size: 34 })],
  });
}
function h(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 260, after: 120 },
    children: [new TextRun({ text, bold: true, color: NAVY, size: 26 })],
  });
}
function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 180, after: 90 },
    children: [new TextRun({ text, bold: true, color: NAVY, size: 22 })],
  });
}
function p(text, opts = {}) {
  return new Paragraph({
    spacing: { after: 120 },
    children: [new TextRun({ text, size: 21, color: opts.color || "222222", italics: !!opts.italics, bold: !!opts.bold })],
  });
}
function bullet(text) {
  return new Paragraph({
    spacing: { after: 80 },
    children: [new TextRun({ text: "\u2022  ", size: 21, color: NAVY, bold: true }), new TextRun({ text, size: 21 })],
  });
}
function cell(text, opts = {}) {
  return new TableCell({
    width: { size: opts.width || 3000, type: WidthType.DXA },
    shading: opts.shade ? { type: ShadingType.CLEAR, fill: opts.shade } : undefined,
    margins: { top: 100, bottom: 100, left: 120, right: 120 },
    children: [new Paragraph({ children: [new TextRun({ text: String(text), bold: !!opts.bold, color: opts.color || "222222", size: 20 })] })],
  });
}
function footer() {
  return new Paragraph({
    spacing: { before: 300 },
    border: { top: { style: BorderStyle.SINGLE, size: 4, color: "CCCCCC", space: 6 } },
    children: [new TextRun({ text: "Paul Linn Solutions — Workforce Solutions & Agentic AI Consulting", italics: true, color: GRAY, size: 18 })],
  });
}
function fmtPct(v) { return v === null || v === undefined ? "\u2014" : `${v}%`; }
function fmtNum(v) { return v === null || v === undefined ? "\u2014" : `${v}`; }
function fmtUsd(v) { return v === null || v === undefined ? "\u2014" : `$${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2 })}`; }

const now = new Date();
const today = `${String(now.getMonth() + 1).padStart(2, "0")}/${String(now.getDate()).padStart(2, "0")}/${now.getFullYear()}`;

// ── DATA COVERAGE TABLE ──

const v = data.validation;
const coverageTable = new Table({
  columnWidths: [3200, 1800, 4300],
  width: { size: 9300, type: WidthType.DXA },
  rows: [
    new TableRow({ tableHeader: true, children: [
      cell("Analysis Area", { bold: true, shade: NAVY, color: "FFFFFF", width: 3200 }),
      cell("Status", { bold: true, shade: NAVY, color: "FFFFFF", width: 1800 }),
      cell("Notes", { bold: true, shade: NAVY, color: "FFFFFF", width: 4300 }),
    ]}),
    new TableRow({ children: [
      cell("Recruiting — Tier 1", { width: 3200 }),
      cell(v.recruiting_tier1.available ? "Available" : "Unavailable", { width: 1800, color: v.recruiting_tier1.available ? "1a7f37" : "b42318", bold: true }),
      cell(v.recruiting_tier1.available ? "Full data received." : `Missing: ${v.recruiting_tier1.missing.join(", ")}`, { width: 4300 }),
    ]}),
    new TableRow({ children: [
      cell("Recruiting — Tier 2", { width: 3200 }),
      cell(v.recruiting_tier2.available ? "Available" : "Unavailable", { width: 1800, color: v.recruiting_tier2.available ? "1a7f37" : "b42318", bold: true }),
      cell(v.recruiting_tier2.available ? "Full data received." : `Missing: ${v.recruiting_tier2.missing.join(", ")}`, { width: 4300 }),
    ]}),
    new TableRow({ children: [
      cell("Revenue Leak Analysis", { width: 3200 }),
      cell(v.revenue.available ? "Available" : "Unavailable", { width: 1800, color: v.revenue.available ? "1a7f37" : "b42318", bold: true }),
      cell(v.revenue.available ? "Full data received." : `Missing: ${v.revenue.missing.join(", ")}`, { width: 4300 }),
    ]}),
  ],
});

// ── RECRUITING SNAPSHOT (Tier 1) ──

let recruitingBlocks = [];
const t1 = data.recruiting.tier1;
if (data.recruiting.tier1_available && t1) {
  const snapshotTable = new Table({
    columnWidths: [4500, 4800],
    width: { size: 9300, type: WidthType.DXA },
    rows: [
      new TableRow({ tableHeader: true, children: [
        cell("Metric", { bold: true, shade: NAVY, color: "FFFFFF", width: 4500 }),
        cell("Value", { bold: true, shade: NAVY, color: "FFFFFF", width: 4800 }),
      ]}),
      new TableRow({ children: [cell("Avg. Time to Fill", { width: 4500 }), cell(`${fmtNum(t1.time_to_fill.average_days)} days`, { width: 4800 })]}),
      new TableRow({ children: [cell("Avg. Time to Hire", { width: 4500 }), cell(`${fmtNum(t1.time_to_hire.average_days)} days`, { width: 4800 })]}),
      new TableRow({ children: [cell("Offer Acceptance Rate", { width: 4500 }), cell(fmtPct(t1.offer_acceptance_rate.rate_pct), { width: 4800 })]}),
      new TableRow({ children: [cell("Fill Rate", { width: 4500 }), cell(fmtPct(t1.fill_rate.fill_rate_pct), { width: 4800 })]}),
      new TableRow({ children: [cell("Vacancy Rate", { width: 4500 }), cell(fmtPct(t1.pct_open_positions.vacancy_rate_pct), { width: 4800 })]}),
      new TableRow({ children: [cell("Application Completion Rate", { width: 4500 }), cell(fmtPct(t1.application_completion_rate.rate_pct), { width: 4800 })]}),
      new TableRow({ children: [cell("Selection Ratio", { width: 4500 }), cell(fmtPct(t1.selection_ratio.ratio_pct), { width: 4800 })]}),
    ],
  });
  recruitingBlocks.push(h2("Tier 1 — Recruiting Pipeline Snapshot"), snapshotTable, new Paragraph({ text: "", spacing: { after: 120 } }));

  const alerts = data.recruiting.tier1_alerts || [];
  if (alerts.length) {
    recruitingBlocks.push(h2("Tier 1 Alerts"));
    for (const a of alerts) {
      recruitingBlocks.push(new Paragraph({
        spacing: { after: 100 },
        children: [
          new TextRun({ text: `${SEVERITY_ICON[a.level] || "\u26AA"}  `, size: 21 }),
          new TextRun({ text: `${a.metric.replace(/_/g, " ")}: `, bold: true, color: NAVY, size: 21 }),
          new TextRun({ text: a.message, size: 21 }),
        ],
      }));
    }
  } else {
    recruitingBlocks.push(p("No threshold breaches this period.", { italics: true, color: GRAY }));
  }
} else {
  recruitingBlocks.push(p("Tier 1 recruiting analysis unavailable — required intake files were not provided.", { italics: true, color: GRAY }));
}

// ── RECRUITING QUALITY & RETENTION (Tier 2) ──

const t2 = data.recruiting.tier2;
if (data.recruiting.tier2_available && t2) {
  const qoh = t2.quality_of_hire && !t2.quality_of_hire.error ? t2.quality_of_hire : null;
  const cx = t2.candidate_experience && !t2.candidate_experience.error ? t2.candidate_experience : null;
  const qualityTable = new Table({
    columnWidths: [4500, 4800],
    width: { size: 9300, type: WidthType.DXA },
    rows: [
      new TableRow({ tableHeader: true, children: [
        cell("Metric", { bold: true, shade: NAVY, color: "FFFFFF", width: 4500 }),
        cell("Value", { bold: true, shade: NAVY, color: "FFFFFF", width: 4800 }),
      ]}),
      new TableRow({ children: [cell("First-Year Attrition", { width: 4500 }), cell(fmtPct(t2.first_year_attrition.rate_pct), { width: 4800 })]}),
      new TableRow({ children: [cell("Quality of Hire (success ratio)", { width: 4500 }), cell(qoh ? fmtPct(qoh.success_ratio_pct) : "Insufficient data", { width: 4800 })]}),
      new TableRow({ children: [cell("Cost per Hire", { width: 4500 }), cell(fmtUsd(t2.cost_per_hire.cost_per_hire), { width: 4800 })]}),
      new TableRow({ children: [cell("Candidate NPS (cNPS)", { width: 4500 }), cell(cx ? fmtNum(cx.cnps) : "Insufficient data", { width: 4800 })]}),
      new TableRow({ children: [cell("Funnel Bottleneck Stage", { width: 4500 }), cell(fmtNum(t2.recruitment_funnel_effectiveness.biggest_drop_stage), { width: 4800 })]}),
    ],
  });
  recruitingBlocks.push(h2("Tier 2 — Quality & Retention"), qualityTable);

  const ai = t2.adverse_impact || {};
  if (ai.compliance_review_required) {
    recruitingBlocks.push(new Paragraph({ spacing: { before: 140 }, children: [
      new TextRun({ text: "\uD83D\uDD34  Adverse Impact Flag: ", bold: true, color: CORAL, size: 21 }),
      new TextRun({ text: `Group(s) ${ai.adverse_impact_flags.join(", ")} flagged under the 4/5ths rule. Requires HR/Legal review before any related personnel action.`, size: 21 }),
    ]}));
  }
} else {
  recruitingBlocks.push(p("Tier 2 recruiting analysis unavailable — required intake files were not provided.", { italics: true, color: GRAY }));
}

// ── REVENUE LEAKAGE / WORKFLOW SPRINT ──

let revenueBlocks = [];
const rev = data.revenue;
if (rev.available) {
  const byCat = rev.by_category || {};
  const catRows = Object.entries(byCat)
    .sort((a, b) => b[1].dollar_impact - a[1].dollar_impact)
    .map(([cat, d]) => new TableRow({ children: [
      cell(REVENUE_CATEGORY_LABELS[cat] || cat, { width: 3600 }),
      cell(String(d.count), { width: 1600 }),
      cell(fmtUsd(d.dollar_impact), { width: 2900 }),
    ]}));

  const revTable = new Table({
    columnWidths: [3600, 1600, 2900],
    width: { size: 8100, type: WidthType.DXA },
    rows: [
      new TableRow({ tableHeader: true, children: [
        cell("Finding Category", { bold: true, shade: NAVY, color: "FFFFFF", width: 3600 }),
        cell("Findings", { bold: true, shade: NAVY, color: "FFFFFF", width: 1600 }),
        cell("Est. $ Impact", { bold: true, shade: NAVY, color: "FFFFFF", width: 2900 }),
      ]}),
      ...(catRows.length ? catRows : [new TableRow({ children: [cell("No findings this period", { width: 3600 }), cell("\u2014", { width: 1600 }), cell("\u2014", { width: 2900 })] })]),
    ],
  });

  revenueBlocks.push(
    new Paragraph({ spacing: { after: 140 }, children: [
      new TextRun({ text: "Total estimated financial exposure flagged: ", bold: true, size: 23, color: NAVY }),
      new TextRun({ text: fmtUsd(rev.total_exposure), bold: true, size: 23, color: CORAL }),
    ]}),
    revTable,
  );
} else {
  revenueBlocks.push(p("Revenue leak analysis unavailable — required intake files were not provided.", { italics: true, color: GRAY }));
}

// ── PRIORITY FINDINGS (pre-ranked in Python) ──

const priorityItems = data.priority_items || [];
let priorityBlocks = [];
if (priorityItems.length) {
  for (const it of priorityItems.slice(0, 12)) {
    const icon = SEVERITY_ICON[it.severity] || "\u26AA";
    const impactStr = it.dollar_impact ? fmtUsd(it.dollar_impact) : (it.area === "revenue" ? "n/a" : "");
    priorityBlocks.push(new Paragraph({
      spacing: { before: 160, after: 50 },
      children: [
        new TextRun({ text: `${icon}  `, size: 22 }),
        new TextRun({ text: `[${it.area === "revenue" ? "Revenue" : "Recruiting"}] `, bold: true, color: GRAY, size: 20 }),
        new TextRun({ text: it.label, bold: true, color: NAVY, size: 22 }),
        impactStr ? new TextRun({ text: `  —  ${impactStr}`, bold: true, color: CORAL, size: 22 }) : new TextRun({ text: "" }),
      ],
    }));
    priorityBlocks.push(p(it.detail));
  }
} else {
  priorityBlocks.push(p("No critical or warning-level findings across either analysis area this period.", { italics: true, color: GRAY }));
}

// ── RECOMMENDED ACTIONS (derived from priority items) ──

let actionBlocks = [];
if (priorityItems.length) {
  for (const it of priorityItems.slice(0, 12)) {
    if (it.action) actionBlocks.push(bullet(it.action));
  }
} else {
  actionBlocks.push(p("No immediate actions required based on current findings.", { italics: true, color: GRAY }));
}

// ── DOCUMENT ──

const doc = new Document({
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 900, bottom: 900, left: 1100, right: 1100 } } },
    children: [
      ...logoHeader(),
      docTitle("Consolidated Client Analysis"),
      p(`${clientName}  |  Generated ${today}`, { italics: true, color: GRAY }),

      h("Executive Summary"),
      p(
        `This report combines recruiting performance analysis with the Workforce Revenue Leak ` +
        `Workflow Sprint to give one consolidated view of operational and commercial risk. ` +
        (rev.available ? `Total estimated financial exposure flagged: ${fmtUsd(rev.total_exposure)}. ` : "") +
        (data.recruiting.tier1_available ? `${(data.recruiting.tier1_alerts || []).length} recruiting alert(s) this period.` : "")
      ),

      h("Data Coverage"),
      coverageTable,
      new Paragraph({ text: "", spacing: { after: 160 } }),

      h("Recruiting Performance"),
      ...recruitingBlocks,

      h("Revenue Leakage / Commercial Risk — Workforce Revenue Leak Workflow Sprint"),
      ...revenueBlocks,

      h("Priority Findings"),
      ...priorityBlocks,

      h("Recommended Actions"),
      ...actionBlocks,

      h("Methodology / Important Notes"),
      p(
        "This report reflects the intake data supplied at the time of analysis. Metrics for any " +
        "analysis area marked \"Unavailable\" above were not calculated and are not represented " +
        "elsewhere in this report — no value has been estimated or assumed in place of missing data."
      ),
      p(
        "Classification-related findings are operational risk indicators only and do not " +
        "constitute legal advice or a legal determination of worker classification. Any such " +
        "finding should be reviewed by the appropriate legal or compliance resource.",
        { italics: true, color: GRAY }
      ),
      p(
        "Adverse-impact findings, where present, require HR/Legal review before any related " +
        "personnel, process, or vendor decision.",
        { italics: true, color: GRAY }
      ),

      footer(),
    ],
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(outPath, buf);
  console.log(`Consolidated report written: ${outPath}`);
});

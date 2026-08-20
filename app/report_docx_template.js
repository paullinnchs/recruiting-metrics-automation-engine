/**
 * report_docx_template.js
 * -------------------------
 * Renders a leak_detection_agent JSON report into a branded,
 * client-ready Workforce Revenue Leak Audit .docx.
 *
 * Usage:
 *   node report_docx_template.js <report.json> <client_name> <output.docx>
 *
 * Called from leak_report_generator.py via subprocess so the Python
 * detection/report data remains the source of truth and this script
 * remains presentation-only.
 */

const {
  Document,
  Packer,
  Paragraph,
  TextRun,
  HeadingLevel,
  Table,
  TableRow,
  TableCell,
  WidthType,
  ShadingType,
  BorderStyle,
  ImageRun,
} = require("docx");

const fs = require("fs");
const path = require("path");

const [, , reportPath, clientName, outPath] = process.argv;

if (!reportPath || !clientName || !outPath) {
  console.error(
    "Usage: node report_docx_template.js " +
      "<report.json> <client_name> <output.docx>"
  );
  process.exit(1);
}

const report = JSON.parse(
  fs.readFileSync(reportPath, "utf8")
);

const LOGO_PATH = path.join(
  __dirname,
  "..",
  "assets",
  "pls_logo_dark_trimmed.png"
);

const LOGO_ASPECT = 770 / 1100;

const NAVY = "0B2545";
const CORAL = "E8604C";
const GRAY = "595959";

const CATEGORY_LABELS = {
  missed_markup: "Missed / incorrect markup",
  stale_rate_card: "Stale rate card billing",
  off_contract_spend: "Off-contract / maverick spend",
  classification_risk:
    "Potential classification risk requiring review",
  hours_variance: "Unbilled / duplicate hours",
  revenue_at_risk_fill: "Revenue-at-risk open fills",
};

const SEVERITY_ICON = {
  CRITICAL: "\uD83D\uDD34",
  WARNING: "\uD83D\uDFE1",
  INFO: "\u26AA",
};


function logoHeader() {
  const width = 150;

  return [
    new Paragraph({
      spacing: {
        after: 220,
      },
      children: [
        new ImageRun({
          data: fs.readFileSync(LOGO_PATH),
          transformation: {
            width,
            height: Math.round(
              width * LOGO_ASPECT
            ),
          },
          type: "png",
        }),
      ],
    }),
  ];
}


function docTitle(text) {
  return new Paragraph({
    spacing: {
      after: 240,
    },
    border: {
      bottom: {
        style: BorderStyle.SINGLE,
        size: 6,
        color: CORAL,
        space: 6,
      },
    },
    children: [
      new TextRun({
        text,
        bold: true,
        color: NAVY,
        size: 34,
      }),
    ],
  });
}


function h(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: {
      before: 260,
      after: 120,
    },
    children: [
      new TextRun({
        text,
        bold: true,
        color: NAVY,
        size: 26,
      }),
    ],
  });
}


function p(text, opts = {}) {
  return new Paragraph({
    spacing: {
      after: 120,
    },
    children: [
      new TextRun({
        text,
        size: 21,
        color: opts.color || "222222",
        italics: !!opts.italics,
      }),
    ],
  });
}


function bullet(text) {
  return new Paragraph({
    spacing: {
      after: 80,
    },
    children: [
      new TextRun({
        text: "\u2022  ",
        size: 21,
        color: NAVY,
        bold: true,
      }),
      new TextRun({
        text,
        size: 21,
      }),
    ],
  });
}


function cell(text, opts = {}) {
  return new TableCell({
    width: {
      size: opts.width || 3000,
      type: WidthType.DXA,
    },
    shading: opts.shade
      ? {
          type: ShadingType.CLEAR,
          fill: opts.shade,
        }
      : undefined,
    margins: {
      top: 100,
      bottom: 100,
      left: 120,
      right: 120,
    },
    children: [
      new Paragraph({
        children: [
          new TextRun({
            text: String(text),
            bold: !!opts.bold,
            color:
              opts.color || "222222",
            size: 20,
          }),
        ],
      }),
    ],
  });
}


function footer() {
  return new Paragraph({
    spacing: {
      before: 300,
    },
    border: {
      top: {
        style: BorderStyle.SINGLE,
        size: 4,
        color: "CCCCCC",
        space: 6,
      },
    },
    children: [
      new TextRun({
        text:
          "Paul Linn Solutions — Workforce Solutions & " +
          "Agentic AI Consulting",
        italics: true,
        color: GRAY,
        size: 18,
      }),
    ],
  });
}


const byCat = report.by_category || {};

const catRows = Object.entries(byCat)
  .sort(
    (a, b) =>
      b[1].dollar_impact -
      a[1].dollar_impact
  )
  .map(
    ([cat, data]) =>
      new TableRow({
        children: [
          cell(
            CATEGORY_LABELS[cat] || cat,
            {
              width: 3600,
            }
          ),
          cell(
            String(data.count),
            {
              width: 1600,
            }
          ),
          cell(
            `$${data.dollar_impact.toLocaleString(
              undefined,
              {
                minimumFractionDigits: 2,
              }
            )}`,
            {
              width: 2900,
            }
          ),
        ],
      })
  );


const summaryTable = new Table({
  columnWidths: [
    3600,
    1600,
    2900,
  ],
  width: {
    size: 8100,
    type: WidthType.DXA,
  },
  rows: [
    new TableRow({
      tableHeader: true,
      children: [
        cell(
          "Finding Category",
          {
            bold: true,
            shade: NAVY,
            color: "FFFFFF",
            width: 3600,
          }
        ),
        cell(
          "Findings",
          {
            bold: true,
            shade: NAVY,
            color: "FFFFFF",
            width: 1600,
          }
        ),
        cell(
          "Est. $ Impact",
          {
            bold: true,
            shade: NAVY,
            color: "FFFFFF",
            width: 2900,
          }
        ),
      ],
    }),

    ...(
      catRows.length
        ? catRows
        : [
            new TableRow({
              children: [
                cell(
                  "No findings this period",
                  {
                    width: 3600,
                  }
                ),
                cell(
                  "—",
                  {
                    width: 1600,
                  }
                ),
                cell(
                  "—",
                  {
                    width: 2900,
                  }
                ),
              ],
            }),
          ]
    ),
  ],
});


const findings = (
  report.findings || []
)
  .filter(
    (f) =>
      f.severity === "CRITICAL" ||
      f.severity === "WARNING"
  )
  .slice(0, 15);


const findingBlocks = [];

for (const f of findings) {
  const icon =
    SEVERITY_ICON[f.severity] ||
    "\u26AA";

  const impactStr =
    f.dollar_impact != null
      ? `$${Number(
          f.dollar_impact
        ).toLocaleString(
          undefined,
          {
            minimumFractionDigits: 2,
          }
        )}`
      : "n/a — review required";

  findingBlocks.push(
    new Paragraph({
      spacing: {
        before: 200,
        after: 60,
      },
      children: [
        new TextRun({
          text: `${icon}  `,
          size: 22,
        }),

        new TextRun({
          text:
            `${
              CATEGORY_LABELS[
                f.category
              ] || f.category
            } — `,
          bold: true,
          color: NAVY,
          size: 22,
        }),

        new TextRun({
          text: impactStr,
          bold: true,
          color: CORAL,
          size: 22,
        }),
      ],
    })
  );

  findingBlocks.push(
    p(
      f.description || ""
    )
  );

  findingBlocks.push(
    new Paragraph({
      spacing: {
        after: 160,
      },
      children: [
        new TextRun({
          text:
            "Recommended action: ",
          bold: true,
          size: 21,
        }),

        new TextRun({
          text:
            f.recommendation || "",
          size: 21,
        }),
      ],
    })
  );
}


if (!findingBlocks.length) {
  findingBlocks.push(
    p(
      "No critical or warning-level findings this period.",
      {
        italics: true,
        color: GRAY,
      }
    )
  );
}


const totalExposure = (
  report.total_exposure || 0
).toLocaleString(
  undefined,
  {
    minimumFractionDigits: 2,
  }
);


const now = new Date();

const today =
  `${String(
    now.getMonth() + 1
  ).padStart(2, "0")}/` +
  `${String(
    now.getDate()
  ).padStart(2, "0")}/` +
  `${now.getFullYear()}`;


const doc = new Document({
  sections: [
    {
      properties: {
        page: {
          size: {
            width: 12240,
            height: 15840,
          },
          margin: {
            top: 900,
            bottom: 900,
            left: 1100,
            right: 1100,
          },
        },
      },

      children: [
        ...logoHeader(),

        docTitle(
          "Workforce Revenue Leak Audit"
        ),

        p(
          `${clientName}  |  Generated ${today}`,
          {
            italics: true,
            color: GRAY,
          }
        ),

        h(
          "Executive Summary"
        ),

        new Paragraph({
          spacing: {
            after: 160,
          },
          children: [
            new TextRun({
              text:
                "Total estimated financial exposure flagged: ",
              bold: true,
              size: 24,
              color: NAVY,
            }),

            new TextRun({
              text:
                `$${totalExposure}`,
              bold: true,
              size: 24,
              color: CORAL,
            }),
          ],
        }),

        p(
          "This audit reviewed billing, timesheet, rate card, " +
            "and contract data to identify potential revenue leakage " +
            "and operational risk across contingent workforce spend — " +
            "including missed markups, stale rate cards, off-contract " +
            "spend, potential worker-classification concerns requiring " +
            "review, and unbilled or duplicate hours."
        ),

        p(
          "Classification-related findings are operational risk " +
            "indicators only and do not constitute legal advice or a " +
            "legal determination of worker classification.",
          {
            italics: true,
            color: GRAY,
          }
        ),

        h(
          "Findings by Category"
        ),

        summaryTable,

        new Paragraph({
          text: "",
          spacing: {
            after: 160,
          },
        }),

        h(
          "Prioritized Findings"
        ),

        ...findingBlocks,

        h(
          "Next Steps"
        ),

        bullet(
          "Validate the highest-dollar findings against your own records."
        ),

        bullet(
          "Address confirmed billing and revenue issues first; route " +
            "classification-related findings to the appropriate legal " +
            "or compliance resource for review."
        ),

        bullet(
          "Consider ongoing monitoring on a monthly or quarterly basis " +
            "to identify new leakage or risk signals before they compound."
        ),

        footer(),
      ],
    },
  ],
});


Packer.toBuffer(
  doc
).then(
  (buf) => {
    fs.writeFileSync(
      outPath,
      buf
    );

    console.log(
      `Branded report written: ${outPath}`
    );
  }
);
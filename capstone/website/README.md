# Capstone Marketing Website — Source

A one-page brochure site for the Literature Review Assistant capstone.
Built the same way as the Ship Day site: edit a data file, run one build
script, deploy only the generated folder.

## Structure

```
website/
├── data/
│   └── content.json      ← all page text and metrics live here
├── scripts/
│   └── build.js           ← reads content.json, writes dist/index.html
├── dist/                  ← generated output — this is what gets deployed
│   ├── index.html
│   ├── architecture-diagram.png
│   └── workflow-diagram.png
└── README.md               ← this file
```

## Before you deploy

Open `data/content.json` and replace these three placeholder values with
real links:

- `project.repo_url` — your GitHub repository URL
- `project.demo_video_url` — your recorded demo video link
- `project.final_report_url` — a link to your Final Report, if you're making
  it public (leave as-is or point to `#` if not)

Everything else in `content.json` is already written from the project's
actual evaluation record and documentation — you should not need to change
the rest unless your live re-run numbers change (see the note below).

## If your live evaluation numbers change

The `evaluation.metrics` array in `content.json` currently shows `12/12`
and `12/13` (updated 2026-08-06 to reflect the confirmed live 13-case
re-run — see `docs/cases.md` Addendum 5 for why it's `12/13`, not
`13/13`). If a future re-run produces different numbers, update those
values (and the `evaluation.note`/`evaluation.body` fields if needed)
before deploying — do not leave the site showing numbers that don't match
your Final Report.

## Build

```bash
cd website
node scripts/build.js
```

This regenerates `dist/index.html` from `data/content.json`. It does not
touch the two diagram PNGs already sitting in `dist/` — those were copied
in once and don't need rebuilding unless you change the diagrams
themselves.

No npm install, no dependencies. Plain Node.js only.

## Deploy

See `DEPLOYMENT-GUIDE.md` in this same folder for the complete, no-memory-
required walkthrough. Short version, if you already remember Ship Day:

```bash
netlify deploy --dir=dist --site=$NETLIFY_SITE_ID --prod
```

Only the `dist/` folder is ever uploaded. `data/content.json` and
`scripts/build.js` stay in your repository and are never public.

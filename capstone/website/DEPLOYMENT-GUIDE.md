# Deployment Guide — Capstone Marketing Website
### Complete walkthrough. Assumes you remember nothing from Ship Day.

---

## Decision already made: new site, Ship Day untouched

This deploys to a **brand new Netlify site**. Your Ship Day site keeps
running at its own URL, completely untouched — this is a deliberate
choice, not a default: previous course artifacts stay available, per your
instructor's note that *"your Ship Day pages are still up... the artifact
outlives the process."*

Same Netlify **account**, same `NETLIFY_AUTH_TOKEN` — just a second,
separate **site** under that account.

---

## Step 1 — Open your Codespace

Open the GitHub Codespace for your capstone repository (not the Ship Day
repository, if they're separate). You should land in a terminal.

## Step 2 — Check your Netlify credentials

Run this to confirm your Netlify auth token is available as an environment
variable:

```bash
node -e "console.log('NETLIFY_AUTH_TOKEN:', process.env.NETLIFY_AUTH_TOKEN ? process.env.NETLIFY_AUTH_TOKEN.slice(0,8)+'...' : 'MISSING')"
```

If it prints `MISSING`, your Codespace secret isn't set for this repo.
Go to GitHub → your repo → Settings → Secrets and variables → Codespaces,
and add `NETLIFY_AUTH_TOKEN` (the same value you used for Ship Day — it's
tied to your Netlify account, not to one site). Then rebuild/restart the
Codespace so the secret loads.

If a value prints, you're good — move on.

## Step 3 — Install the Netlify CLI (if not already installed)

```bash
npm install -g netlify-cli
```

If it's already installed from Ship Day, this command just confirms it and
exits quickly — safe to run either way.

## Step 4 — Get the website files into your repo

You should have received a folder called `website/` (or a zip containing
it) with this structure:

```
website/
├── data/content.json
├── scripts/build.js
├── dist/
│   ├── index.html
│   ├── architecture-diagram.png
│   └── workflow-diagram.png
├── README.md
└── DEPLOYMENT-GUIDE.md   (this file)
```

Copy the whole `website/` folder into the root of your capstone repository
in the Codespace (drag-and-drop in the file explorer, or `git` it in if
you downloaded a zip — unzip it, then move the folder in).

## Step 5 — Fill in your real links

Open `website/data/content.json` in the Codespace editor. Near the top,
find:

```json
"repo_url": "REPLACE_WITH_YOUR_GITHUB_REPO_URL",
"demo_video_url": "REPLACE_WITH_YOUR_DEMO_VIDEO_URL",
"final_report_url": "REPLACE_WITH_YOUR_FINAL_REPORT_LINK_IF_PUBLIC"
```

Replace each placeholder with a real URL. Save the file.

If your live evaluation re-run (Phase 1 of the main capstone work) produced
different numbers than `12/12` and `13/13`, also update the
`evaluation.metrics` section further down in the same file. See the
website's own `README.md` for exactly which fields to touch.

## Step 6 — Build the site

```bash
cd website
node scripts/build.js
```

You should see:

```
Built dist/index.html
```

This reads `data/content.json` and regenerates `dist/index.html`. It does
not touch the two diagram images already in `dist/` — leave those as they
are unless you're replacing the diagrams themselves.

## Step 7 — Look at it before deploying (optional but recommended)

In the Codespace, right-click `dist/index.html` → "Show Preview," or open
a simple local server:

```bash
npx serve dist
```

and open the printed `localhost` link. Confirm it looks right — check that
your links work and the diagrams show up — before making it public.

## Step 8 — Create the new Netlify site

```bash
netlify sites:create --name your-capstone-site-name
```

Pick a name that isn't taken — Netlify tells you immediately if it's not
available; just try again with a different name.

The output includes a line like:

```
Site ID: 7a1b2c3d-4e5f-6789-a0b1-c2d3e4f5a6b7
```

**Copy that Site ID.** You'll use it in every deploy from now on, and you
should save it somewhere you won't lose it — see the box below.

### Save the Site ID as a Codespaces secret (recommended)

Rather than pasting the Site ID into a command every time, store it once:

1. GitHub → your capstone repo → Settings → Secrets and variables →
   Codespaces
2. Add a new secret named `NETLIFY_SITE_ID`, value = the ID you just copied
3. Rebuild or restart your Codespace so the secret loads

Once that's done, `$NETLIFY_SITE_ID` works in every command below instead
of typing the raw ID. If you'd rather not set up the secret, you can also
just paste the raw ID directly each time — both are shown in Step 9.

## Step 9 — Deploy

If you saved `NETLIFY_SITE_ID` as a Codespaces secret:

```bash
netlify deploy --dir=dist --site=$NETLIFY_SITE_ID --prod
```

Or, using the raw ID directly:

```bash
netlify deploy --dir=dist --site=<YOUR_SITE_ID> --prod
```

This is the exact same command shape you used for Ship Day — same flags,
same pattern. Only the site ID and the folder's contents are different.

Only the `dist/` folder is uploaded. `data/content.json` and
`scripts/build.js` never leave your Codespace or your repository — the
public site only ever sees the finished HTML and the two diagram images.

## Step 10 — Verify

The command prints a live URL when it finishes, something like:

```
Website URL: https://your-capstone-site-name.netlify.app
```

Open it in a browser. Check:

- The page loads and the title bar shows your project name
- Both diagram images display (not broken image icons)
- The GitHub, Demo Video, and Final Report links go to the right places
- Scroll all the way down — nothing looks cut off or overlapping

## Step 11 — If you need to make the site private

Per your instructions, a real password wall may not be available on a
free Netlify plan. Two fallbacks:

**Unlisted URL.** Just don't publish the link publicly — only share it in
your Q&A thread as instructed. This is the simplest option and is
explicitly called acceptable in your assignment instructions.

**Simple front-page gate.** If you want a lightweight barrier, you'd add a
small script to `dist/index.html` that prompts for a shared word before
showing the page content. This is optional — ask if you want this built;
it's a small addition to the existing `build.js`, not a new project.

## Step 12 — Update your other Day 19 documents

Once you have the live URL, send it back so the following can be updated
with it:

- Final Report (Project Overview section, and the Deliverables list)
- Submission checklist
- Peer Q&A thread

This is exactly the "update instead of rewrite" workflow already in use
for the rest of the capstone package.

## Step 13 — Updating the site later (e.g. once live evaluation numbers are in)

You will likely need to update this site at least once — for example, once
your live 13-case re-run finishes and you have final numbers to show. The
site is data-driven specifically so this doesn't mean touching HTML:

1. Edit `website/data/content.json` — change only the fields that need to
   change (for example, `evaluation.metrics`)
2. Rebuild:
   ```bash
   cd website
   node scripts/build.js
   ```
3. Redeploy, same command as Step 9:
   ```bash
   netlify deploy --dir=dist --site=$NETLIFY_SITE_ID --prod
   ```

That's the whole cycle. The site ID doesn't change, so this redeploy
replaces the previous version at the same URL — you don't create a new
site each time you update content.

---

## If something goes wrong

**`netlify: command not found`** — Step 3 didn't complete. Run
`npm install -g netlify-cli` again and check for errors in the output.

**`Error: Must run inside a Netlify site directory or specify a site with --site flag`**
— You forgot `--site=<id>` or copy-pasted an empty value. Recheck Step 9.

**Deploy succeeds but the diagrams don't show on the live site** — Confirm
`architecture-diagram.png` and `workflow-diagram.png` actually exist inside
`dist/` (not just referenced by name) before you deploy. Run `ls dist/` to
check.

**You deployed to the wrong site by accident** — Not destructive to worry
about long-term. You can redeploy the correct content to the correct site
ID at any time; the previous deploy is simply replaced by the next one to
that same site.

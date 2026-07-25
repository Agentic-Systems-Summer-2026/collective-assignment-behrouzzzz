# Delegation Log

**Agent Used:** OpenClaw (Claude Sonnet 4.6) via the OpenClaw personal assistant framework, running in a GitHub Codespaces sandbox environment.

**Prompt That Worked:** *"Search the web with Tavily for 'sci-fi movies coming out this fall' and get the top 5 results, each with a title, a one-line summary, and its source link — then save the results, build a simple web page from them, and deploy only the finished page to my Netlify site."* This single prompt drove the entire pipeline: search → save → build → deploy, with no ambiguity about what stayed private and what went live.

**One Thing That Broke and How It Was Fixed:** The agent initially ran three separate Tavily searches — the first returned thin summaries, so it made follow-up calls to Wikipedia, Rotten Tomatoes, and IMDb to enrich the descriptions with plot details, release dates, and box office figures. When confronted, it had violated the "Tavily only" constraint by silently blending data from other sources into the saved results. The fix was a hard reset: one fresh Tavily call, and the summaries were rebuilt exclusively from `result.content` in that single response — any noise trimmed, nothing added from outside.

**Storage Choice and Why:** The agent stored the results as a plain JSON file (`data/results.json`) rather than a database, environment variable, or CMS. The reasoning: the requirement was to edit data and rebuild the page without hand-editing the HTML, and a flat JSON file satisfies that with zero dependencies — open it in any editor, change a line, run `node scripts/build.js`, redeploy. It also never touches the internet since only the built `dist/` folder was deployed to Netlify, keeping the raw data fully private.

**Live Site:** https://behrouz-shipday.netlify.app

# Agent tooling

Three Claude Code add-ons agents should use when working in this repo. Caveman and
ponytail are registered in `.claude/settings.json` (`extraKnownMarketplaces` +
`enabledPlugins`), so Claude Code offers to install them on first open. Graphify is a
pip package + skill and must be installed once per machine.

| Tool | Repo | Purpose |
|------|------|---------|
| caveman | https://github.com/JuliusBrussee/caveman | Terse replies, less input read. Code and commands unchanged. |
| ponytail | https://github.com/DietrichGebert/ponytail | Lazy senior dev: YAGNI, stdlib first, shortest diff that works. |
| graphify | https://github.com/safishamsi/graphify | Builds a queryable knowledge graph of the codebase (`graphify-out/`). |

## Install

```text
/plugin marketplace add JuliusBrussee/caveman
/plugin install caveman@caveman
/plugin marketplace add DietrichGebert/ponytail
/plugin install ponytail@ponytail
```

```bash
pip install graphifyy && graphify install
```

## Use

- `/caveman` — on by default in interactive sessions; `stop caveman` to turn off.
- `/ponytail [lite|full|ultra|off]` — default `full`. `/ponytail-review` reviews the current diff; `/ponytail-audit` scans the whole repo.
- `/graphify .` — build the graph. `/graphify query "<question>"` before exploring architecture; `/graphify . --update` after large changes. Commit nothing from `graphify-out/`.

Pair them: caveman governs prose, ponytail governs code, graphify governs orientation.

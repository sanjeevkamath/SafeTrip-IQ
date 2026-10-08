# Frontend dependency patch — 2026-10-08

The original lockfile reported 21 npm audit findings: one critical, 16 high, three moderate, and one low. These counts include parent packages affected through dependencies; they do not represent 21 independently exploitable application flaws.

## Changes

| Package | Before | After |
| --- | --- | --- |
| next | 16.0.8 | 16.3.8 |
| eslint-config-next | 16.0.6 | 16.3.8 |
| react / react-dom | 19.2.0 | 19.2.8 |

The framework and lint configuration now share an exact version. React remains on the 19.2 release line. Compatible transitive fixes were applied with `npm audit fix` without `--force`, including PostCSS, Sharp, ws, Babel, and glob-related utilities. Existing D3 overrides and application UI remain unchanged.

The [Next.js 16.3.8 release](https://github.com/vercel/next.js/releases/tag/v16.3.8) contains security fixes. The current production dependency audit reports zero known vulnerabilities. This is a dependency advisory check, not a full application security assessment.

## Remaining development dependency finding

The full audit reports five high-severity package entries for this single dependency chain:

```text
eslint-config-next → @next/eslint-plugin-next → fast-glob → micromatch → braces
```

[GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) describes stack exhaustion from deeply nested brace patterns. At verification time, braces 3.0.3 was the latest release and the advisory listed no patched version. Even the newer Next.js 16.4 lint plugin retained fast-glob.

This chain belongs to lint tooling, not the production dependency set. It remains a development/build concern. npm's suggested forced remediation would downgrade the lint configuration to 14.2.35; that was not applied. No audit finding is suppressed or represented as fixed. Revisit when the package or upstream lint tool publishes a compatible fix.

## Verification and ongoing checks

- Clean `npm ci` succeeded with the updated lockfile.
- `npm run audit:production` reports zero findings.
- TypeScript, ESLint, and production build passed. Three existing image-optimization lint warnings remain.
- A local Chromium smoke check passed for homepage hydration, map rendering/zoom, mocked search results, and the short-query search API. External browser requests were blocked, the map/search responses were fixtures, and the build used dummy Supabase credentials. This does not verify live country data or the deployed Vercel site.

CI and `scripts/check_ci.sh` now run `npm run audit:production`, which fails on high/critical production advisories or audit execution failures. `npm audit` remains the command for the full dependency report; it currently exits nonzero for the documented development dependency finding. This gate does not cover development dependencies. Registry connectivity and advisory database changes can affect later CI runs even if source code is unchanged.

From `frontend/`:

```sh
npm run audit:production
npm audit
```

The patch takes effect on the public website only after it is committed, pushed, and deployed through Vercel. Verify the preview's search, map, and country page before promoting it. No production deployment or database modification was performed during this patch.

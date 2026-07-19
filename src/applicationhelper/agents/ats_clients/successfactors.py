"""SAP SuccessFactors client — currently unavailable.

Checked directly against SAP's own SuccessFactors-hosted career site
(career5.successfactors.eu/careers?company=SAP, which is what jobs.sap.com
redirects to) on 2026-07-19:

- The careers page itself is server-rendered HTML from a stateful SPA
  framework ("verp"), not a clean JSON endpoint — scraping it reliably would
  need a real browser, not a simple HTTP client.
- The documented-sounding REST path
  (`POST /services/recruiting/v1/jobs`) returned `403 Forbidden` — it exists,
  but requires per-tenant OAuth2/SAML that SAP hasn't exposed publicly for
  this site.
- No public `/sitemap.xml` was present either.

There is no known-working unauthenticated path here comparable to Greenhouse,
Ashby, SmartRecruiters, or Workday's CXS API. Not wired into JobSearchAgent.
"""

from __future__ import annotations

import httpx

from applicationhelper.models.job import JobPosting


async def fetch_successfactors_jobs(company: str, client: httpx.AsyncClient) -> list[JobPosting]:
    raise NotImplementedError(
        "SAP SuccessFactors has no confirmed public unauthenticated jobs API. See module docstring."
    )

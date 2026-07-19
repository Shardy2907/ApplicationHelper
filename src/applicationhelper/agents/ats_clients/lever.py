"""Lever public Postings API client — currently unavailable.

As of 2026-07-19, `GET https://api.lever.co/v1/postings/{company}?mode=json`
returns `401 {"code": "UnauthorizedError", "message": "The request requires
authentication."}` for every company board tested (coinbase, canva, discord,
scaleai, anthropic, plaid, reddit, figma, robinhood, shopify, attentive,
lever itself) — this is a real response from Lever's servers, not a network
issue, so the previously-public postings API appears to now require auth
Lever hasn't documented a self-serve path for. Not wired into JobSearchAgent
until a working (possibly authenticated) integration path is confirmed.
"""

from __future__ import annotations

import httpx

from applicationhelper.models.job import JobPosting


async def fetch_lever_jobs(company: str, client: httpx.AsyncClient) -> list[JobPosting]:
    raise NotImplementedError(
        "Lever's public postings API currently returns 401 Unauthorized for all "
        "tested boards. See module docstring."
    )

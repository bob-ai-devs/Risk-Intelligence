"""Fast keyword pre-scan: which risk areas does each headline likely touch?

This is a cheap triage aid shown before any Gemini call. It never feeds the final scores.
"""
from __future__ import annotations

import re
from typing import List

KEYWORDS = {
    "capital_adequacy": ["capital", "crar", "cet1", "tier 1", "tier-1", "tier 2", "tier-2", "at1", "dividend", "qip",
                         "fund-raising", "fund raising", "raises", "buyback", "infusion", "leverage ratio"],
    "credit_risk": ["loan", "lending", "advances", "credit growth", "exposure", "mortgage", "retail credit",
                    "credit card", "risk weight", "rwa", "msme", "sme"],
    "market_risk": ["bond yield", "yields", "forex", "rupee", "treasury", "investment portfolio", "mark-to-market",
                    "mtm", "securities", "bond portfolio"],
    "operational_risk": ["cyber", "outage", "fraud", "hack", "breach", "phishing", "scam", "data leak", "downtime",
                         "system failure", "mis-selling", "misselling", "glitch"],
    "concentration_risk": ["concentration", "large borrower", "large exposure", "group exposure", "corporate account",
                           "single borrower", "exposure to"],
    "irrbb": ["repo rate", "rate cut", "rate hike", "interest rate", "margin", "nim", "deposit rate", "mclr",
              "repricing", "yield curve"],
    "governance_reputation": ["resign", "appoint", "ceo", "chairman", "board", "probe", "investigation", "cbi",
                              "governance", "whistleblower", "merger", "acquisition", "stake sale", "managing director",
                              "irregularit", "reputation"],
    "market_discipline": ["results", "quarterly", "earnings", "rating", "upgrade", "downgrade", "crisil", "icra",
                          "target price", "analyst", "shares", "stock", "valuation", "brokerage", "q1", "q2", "q3", "q4"],
    "asset_quality": ["npa", "asset quality", "slippage", "provision", "default", "stressed", "write-off", "write off",
                      "sma", "bad loan", "recovery", "nclt", "insolvency", "restructur", "ecl"],
    "liquidity_funding": ["deposit", "casa", "liquidity", "lcr", "nsfr", "funding", "credit-deposit", "withdrawal",
                          "bank run"],
    "regulatory_action": ["rbi", "penalty", "fine", "restrict", "prompt corrective", "pca", "circular", "regulator",
                          "sebi", "show cause", "directive", "compliance", "kyc", "monetary penalty"],
    "profitability": ["profit", "net interest income", "nii", "roa", "roe", "income", "cost-to-income", "growth",
                      "earnings"],
    "macro_sector": ["inflation", "gdp", "crude", "geopolitic", "budget", "policy", "banking sector", "banking stocks",
                     "global", "economy", "tariff", "psu bank", "fed "],
}

_COMPILED = {
    bid: [re.compile(r"(?<![a-z0-9])" + re.escape(k)) for k in kws] for bid, kws in KEYWORDS.items()
}


def scan(title: str) -> List[str]:
    t = title.lower()
    return [bid for bid, pats in _COMPILED.items() if any(p.search(t) for p in pats)]

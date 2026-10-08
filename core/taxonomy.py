"""Risk framework used to structure every Gemini impact assessment.

Branches are grouped by Basel III pillar (RBI Master Circular on Basel III
Capital Regulations) plus the India-specific areas that sit outside that
circular (liquidity, asset quality, supervisory action, earnings, macro).
`signal` says how much a *headline alone* can tell you about the branch.
"""
from dataclasses import dataclass
from typing import Tuple

GROUPS = [
    "Pillar 1: Minimum capital",
    "Pillar 2: Supervisory review",
    "Pillar 3: Market discipline",
    "Beyond Basel: RBI and Indian context",
]


@dataclass(frozen=True)
class Branch:
    id: str
    name: str
    short: str
    group: str
    icon: str
    metrics: Tuple[str, ...]
    signal: str  # Direct | Indirect
    signal_note: str


BRANCHES = [
    Branch("capital_adequacy", "Capital adequacy and buffers", "Capital",
           GROUPS[0], "🏛️",
           ("CET1 ratio", "Tier 1 ratio", "Total CRAR", "Capital conservation buffer",
            "Countercyclical buffer", "Leverage ratio", "AT1 / Tier 2 issuance", "Dividend capacity"),
           "Indirect",
           "Ratios are published quarterly. Headlines signal capital raises, large losses or dividend moves."),
    Branch("credit_risk", "Credit risk and RWA", "Credit / RWA",
           GROUPS[0], "💳",
           ("Risk-weighted assets", "Exposure by asset class (corporate, retail, mortgage, CRE, sovereign)",
            "Dependence on external ratings", "Collateral and guarantees (CRM)",
            "Off-balance-sheet exposure", "Securitisation"),
           "Indirect",
           "Borrower-level and portfolio-level stories change risk weights only with a lag."),
    Branch("market_risk", "Market risk", "Market",
           GROUPS[0], "📉",
           ("Interest-rate risk in trading book", "Equity price risk", "Foreign-exchange risk",
            "Investment portfolio mark-to-market", "Bond yields", "Credit default swap positions"),
           "Indirect",
           "Rate, yield and currency moves in the news feed straight into valuation losses or gains."),
    Branch("operational_risk", "Operational, cyber and fraud risk", "Op / Cyber / Fraud",
           GROUPS[0], "🛡️",
           ("Operational risk capital charge", "Cyber and IT outages", "Fraud and mis-selling losses",
            "Third-party and vendor failures", "Internal control lapses"),
           "Direct",
           "Outages, frauds and breaches are reported as events, so headlines carry real signal."),
    Branch("concentration_risk", "Concentration and large exposures", "Concentration",
           GROUPS[1], "🎯",
           ("Large borrower or group exposure", "Sector concentration", "Geographic concentration",
            "Single-industry exposure above 5%", "Counterparty concentration"),
           "Indirect",
           "Visible when a named borrower, group or sector gets into trouble."),
    Branch("irrbb", "Interest rate risk in the banking book", "IRRBB",
           GROUPS[1], "⚖️",
           ("Net interest income sensitivity", "Economic value of equity", "Repricing gaps",
            "Deposit repricing speed", "Repo-rate transmission"),
           "Indirect",
           "Policy-rate and yield-curve headlines hint at direction, not size."),
    Branch("governance_reputation", "Governance, reputation and strategy", "Governance",
           GROUPS[1], "🧭",
           ("Board and senior management stability", "Risk culture", "Compensation and incentives",
            "Auditor and internal-audit findings", "Reputational events", "Strategic moves (M&A, expansion)"),
           "Direct",
           "Management exits, probes and strategic announcements are headline events."),
    Branch("market_discipline", "Market discipline and disclosure", "Disclosure",
           GROUPS[2], "📢",
           ("Quarterly results and disclosure quality", "Credit ratings and outlooks",
            "Share price and valuation", "Investor and analyst sentiment",
            "Restatements and filing delays"),
           "Direct",
           "Results, rating actions and analyst calls are widely covered."),
    Branch("asset_quality", "Asset quality and provisioning", "Asset quality",
           GROUPS[3], "🧾",
           ("Gross NPA ratio", "Net NPA ratio", "Provision coverage ratio", "Slippages",
            "SMA-1 / SMA-2 accounts", "Restructured loans", "Write-offs", "Expected credit loss stage migration"),
           "Indirect",
           "Exact ratios arrive with results. Default and stress stories signal the direction."),
    Branch("liquidity_funding", "Liquidity and funding", "Liquidity",
           GROUPS[3], "💧",
           ("Liquidity coverage ratio", "Net stable funding ratio", "CASA ratio",
            "Deposit growth and concentration", "Credit-deposit ratio", "ALM gaps", "Wholesale funding"),
           "Indirect",
           "Deposit-run rumours or funding stress show up in news before the ratios do."),
    Branch("regulatory_action", "Regulatory and supervisory action", "Regulatory",
           GROUPS[3], "⚠️",
           ("RBI monetary penalties", "Business restrictions", "Prompt Corrective Action",
            "Pillar 2 capital add-ons", "D-SIB surcharge", "New RBI circulars"),
           "Direct",
           "RBI actions are announced publicly and reported immediately."),
    Branch("profitability", "Profitability and growth", "Profitability",
           GROUPS[3], "📈",
           ("Net interest margin", "Net interest income", "Return on assets / equity",
            "Cost-to-income ratio", "Credit cost", "Fee income", "Loan growth"),
           "Indirect",
           "Results coverage gives real numbers. Other stories give direction only."),
    Branch("macro_sector", "Macro and sector environment", "Macro / Sector",
           GROUPS[3], "🌐",
           ("Repo rate", "Inflation and GDP", "Sector stress", "Geopolitical events",
            "Government and banking policy", "Global banking events"),
           "Direct",
           "Not bank-specific. Impact depends on how exposed this bank is."),
]

BY_ID = {b.id: b for b in BRANCHES}
IDS = [b.id for b in BRANCHES]

"""Reference data for the demonstration dataset.

Fictional households and fictional financial data. Security symbols are drawn
from well-known instruments so the dataset reads plausibly, but every price,
holding and balance below is invented for this demonstration.
"""

from __future__ import annotations

CUSTODIANS = [
    ("Meridian Trust & Custody", "Meridian", "direct_feed", "fresh"),
    ("Harborline Securities", "Harborline", "aggregated", "fresh"),
    ("Cascade National Bank", "Cascade", "aggregated", "delayed"),
    ("Ironbridge Retirement Services", "Ironbridge", "direct_feed", "fresh"),
    ("Northmoor Private Bank", "Northmoor", "manual", "stale"),
]

BENCHMARKS = [
    (
        "GLOBAL_60_40",
        "Global 60/40 Blend",
        "60% MSCI ACWI / 40% Bloomberg US Aggregate, rebalanced monthly.",
        {"us_equity": 0.36, "intl_equity": 0.24, "fixed_income": 0.40},
    ),
    (
        "GROWTH_80_20",
        "Growth 80/20 Blend",
        "80% global equity / 20% investment-grade fixed income.",
        {"us_equity": 0.50, "intl_equity": 0.30, "fixed_income": 0.20},
    ),
    (
        "CONSERVATIVE_30_70",
        "Conservative 30/70 Blend",
        "30% global equity / 70% fixed income and cash.",
        {"us_equity": 0.18, "intl_equity": 0.12, "fixed_income": 0.60, "cash": 0.10},
    ),
]

# symbol, name, type, asset_class, sector, region, price, prev_close, yield,
# expense, beta, volatility, esg, municipal, substantially_identical_to
SECURITIES = [
    ("VTI", "Vanguard Total Stock Market ETF", "etf", "us_equity", "Diversified", "United States", 298.42, 296.15, 0.0126, 0.0003, 1.00, 0.161, 62.0, False, "ITOT"),
    ("ITOT", "iShares Core S&P Total US Stock Market ETF", "etf", "us_equity", "Diversified", "United States", 132.88, 131.90, 0.0129, 0.0003, 1.00, 0.160, 61.0, False, "VTI"),
    ("VOO", "Vanguard S&P 500 ETF", "etf", "us_equity", "Diversified", "United States", 546.71, 542.60, 0.0122, 0.0003, 1.00, 0.158, 63.0, False, "SPLG"),
    ("SPLG", "SPDR Portfolio S&P 500 ETF", "etf", "us_equity", "Diversified", "United States", 74.19, 73.63, 0.0124, 0.0002, 1.00, 0.158, 63.0, False, "VOO"),
    ("SCHG", "Schwab US Large-Cap Growth ETF", "etf", "us_equity", "Growth", "United States", 116.24, 114.88, 0.0042, 0.0004, 1.14, 0.198, 58.0, False, None),
    ("AVUV", "Avantis US Small Cap Value ETF", "etf", "us_equity", "Small Cap Value", "United States", 98.37, 97.61, 0.0158, 0.0025, 1.12, 0.213, 51.0, False, None),
    ("NVDA", "NVIDIA Corporation", "stock", "us_equity", "Information Technology", "United States", 181.44, 178.20, 0.0003, None, 1.72, 0.421, 55.0, False, None),
    ("MSFT", "Microsoft Corporation", "stock", "us_equity", "Information Technology", "United States", 447.13, 444.02, 0.0072, None, 0.94, 0.234, 78.0, False, None),
    ("JNJ", "Johnson & Johnson", "stock", "us_equity", "Health Care", "United States", 162.55, 163.10, 0.0312, None, 0.55, 0.148, 71.0, False, None),
    ("BRK.B", "Berkshire Hathaway Class B", "stock", "us_equity", "Financials", "United States", 486.20, 483.75, 0.0000, None, 0.86, 0.169, 49.0, False, None),
    ("VXUS", "Vanguard Total International Stock ETF", "etf", "intl_equity", "Diversified", "Developed ex-US", 64.88, 64.31, 0.0298, 0.0007, 1.05, 0.176, 66.0, False, "IXUS"),
    ("IXUS", "iShares Core MSCI Total International Stock ETF", "etf", "intl_equity", "Diversified", "Developed ex-US", 73.42, 72.79, 0.0301, 0.0007, 1.05, 0.177, 66.0, False, "VXUS"),
    ("EFA", "iShares MSCI EAFE ETF", "etf", "intl_equity", "Diversified", "Europe & Asia", 84.11, 83.47, 0.0286, 0.0033, 1.02, 0.174, 68.0, False, None),
    ("VWO", "Vanguard FTSE Emerging Markets ETF", "etf", "intl_equity", "Emerging Markets", "Emerging Markets", 47.63, 47.02, 0.0271, 0.0008, 1.18, 0.208, 52.0, False, None),
    ("BND", "Vanguard Total Bond Market ETF", "etf", "fixed_income", "Aggregate", "United States", 74.06, 74.21, 0.0431, 0.0003, 0.14, 0.058, 60.0, False, "AGG"),
    ("AGG", "iShares Core US Aggregate Bond ETF", "etf", "fixed_income", "Aggregate", "United States", 99.18, 99.36, 0.0428, 0.0003, 0.14, 0.058, 60.0, False, "BND"),
    ("MUB", "iShares National Muni Bond ETF", "etf", "fixed_income", "Municipal", "United States", 108.42, 108.55, 0.0327, 0.0007, 0.11, 0.049, 64.0, True, None),
    ("VTEB", "Vanguard Tax-Exempt Bond ETF", "etf", "fixed_income", "Municipal", "United States", 51.07, 51.14, 0.0334, 0.0005, 0.11, 0.048, 64.0, True, "MUB"),
    ("VCIT", "Vanguard Intermediate-Term Corporate Bond ETF", "etf", "fixed_income", "Corporate", "United States", 83.29, 83.44, 0.0472, 0.0004, 0.22, 0.071, 57.0, False, None),
    ("SGOV", "iShares 0-3 Month Treasury Bond ETF", "etf", "cash", "Treasury", "United States", 100.42, 100.41, 0.0428, 0.0009, 0.01, 0.004, 70.0, False, None),
    ("GLD", "SPDR Gold Shares", "etf", "real_assets", "Precious Metals", "Global", 254.88, 252.30, 0.0000, 0.0040, 0.16, 0.145, None, False, None),
    ("VNQ", "Vanguard Real Estate ETF", "etf", "real_assets", "Real Estate", "United States", 94.71, 94.02, 0.0384, 0.0013, 1.09, 0.191, 59.0, False, None),
    ("QAI", "NYLI Hedge Multi-Strategy Tracker ETF", "etf", "alternatives", "Multi-Strategy", "Global", 32.18, 32.05, 0.0212, 0.0091, 0.42, 0.084, 47.0, False, None),
    ("PSP", "Invesco Global Listed Private Equity ETF", "etf", "alternatives", "Private Equity", "Global", 68.94, 68.11, 0.0344, 0.0139, 1.31, 0.243, 44.0, False, None),
]

CHARITIES = [
    ("Rivermark Education Foundation", "**-***4821", "Education", "Portland, OR", 4.6),
    ("Cascade Food Alliance", "**-***7734", "Food Security", "Seattle, WA", 4.8),
    ("Harborlight Marine Conservancy", "**-***2290", "Environment", "Monterey, CA", 4.3),
    ("Willow Creek Free Clinic", "**-***9015", "Health Care", "Austin, TX", 4.7),
    ("Northlake Arts Collective", "**-***3388", "Arts & Culture", "Minneapolis, MN", 4.1),
    ("Stonebridge Housing Trust", "**-***6602", "Housing", "Denver, CO", 4.5),
]

EDUCATION_CONTENT = [
    ("Understanding Your 401(k) Match", "guide", "Retirement Foundations", "beginner", 8,
     "How the employer match works and why contributing at least to the match is the first priority.",
     "An employer match is compensation you only receive if you contribute. If your plan matches 100% of the first 4% of pay, contributing 4% doubles that portion of your savings immediately."),
    ("Roth vs Traditional Contributions", "guide", "Retirement Foundations", "beginner", 10,
     "The trade-off is simple: pay tax now, or pay tax later.",
     "Traditional contributions reduce taxable income today and are taxed on withdrawal. Roth contributions are made after tax and qualified withdrawals are tax free. Which wins depends on your rate now versus in retirement."),
    ("How Vesting Works", "video", "Retirement Foundations", "beginner", 6,
     "Your own contributions are always yours. Employer contributions vest over time.",
     None),
    ("Choosing an Investment Mix", "guide", "Investing Basics", "intermediate", 12,
     "Matching your asset allocation to your time horizon and comfort with volatility.",
     "A target-date fund handles the mix for you. Building your own means deciding how much to hold in stocks versus bonds, and rebalancing when it drifts."),
    ("What a Target-Date Fund Actually Does", "video", "Investing Basics", "beginner", 7,
     "One fund that becomes more conservative as your retirement year approaches.",
     None),
    ("Diversification and Concentration Risk", "guide", "Investing Basics", "intermediate", 11,
     "Why holding a large position in one company is a different kind of risk.",
     "Concentration works both ways. A single holding above 10% of a portfolio drives an outsized share of both gains and losses."),
    ("Taking a Plan Loan: What to Consider", "guide", "Life Events", "intermediate", 9,
     "Plan loans are repaid with after-tax dollars and can become taxable if you leave.",
     "A loan removes money from the market while it is outstanding. If employment ends before repayment, the balance can be treated as a distribution."),
    ("Naming Your Beneficiaries", "guide", "Life Events", "beginner", 5,
     "Your beneficiary designation overrides your will for this account.",
     "Review your designation after a marriage, divorce, birth or death in the family. A missing designation sends the account through probate."),
    ("Catch-Up Contributions After 50", "guide", "Retirement Foundations", "intermediate", 8,
     "Additional contribution room becomes available in the year you turn 50.",
     None),
    ("Reading Your Quarterly Statement", "webinar", "Investing Basics", "beginner", 20,
     "Balance, contributions, returns and fees, and what each one is telling you.",
     None),
    ("Planning for Healthcare in Retirement", "guide", "Retirement Readiness", "advanced", 14,
     "Healthcare is often the largest under-estimated cost in a retirement plan.",
     None),
    ("Social Security Claiming Basics", "webinar", "Retirement Readiness", "intermediate", 18,
     "Claiming early reduces the benefit permanently; delaying increases it.",
     None),
]

FIRST_NAMES = [
    "Amara", "Beatriz", "Cormac", "Delphine", "Elias", "Farida", "Gideon", "Halima", "Idris", "Junia",
    "Kwame", "Liesel", "Mateo", "Noor", "Oskar", "Priya", "Quentin", "Rosalind", "Sunil", "Tamsin",
    "Ulises", "Verity", "Wren", "Xiomara", "Yusuf", "Zephyr", "Anouk", "Bram", "Cecily", "Dashiell",
    "Esme", "Fionn", "Greta", "Hugo", "Ingrid", "Jasper", "Kiona", "Lucian", "Marisol", "Nikolai",
]

LAST_NAMES = [
    "Achebe", "Baptiste", "Calloway", "Delacroix", "Emerson", "Fontaine", "Grayson", "Halvorsen",
    "Ishikawa", "Jhaveri", "Kowalski", "Lindqvist", "Moreau", "Nakamura", "Okonkwo", "Pemberton",
    "Quintero", "Ravensworth", "Sandoval", "Thorne", "Ueda", "Villareal", "Waverly", "Xanthos",
    "Yamamoto", "Zdravkovic", "Ashworth", "Bergstrom", "Castellanos", "Duvall",
]

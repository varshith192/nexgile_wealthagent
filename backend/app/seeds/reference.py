"""Reference data for the demonstration dataset.

Fictional households and fictional financial data. Instrument names are drawn
from well-known Indian listed securities and fund categories so the dataset
reads plausibly to anyone who knows the market, but every price, holding and
balance below is invented for this demonstration.
"""

from __future__ import annotations

# name, short name, connection type, feed status
CUSTODIANS = [
    ("Zerodha Broking Ltd", "Zerodha", "direct_feed", "fresh"),
    ("HDFC Bank", "HDFC", "aggregated", "fresh"),
    ("CAMS / KFintech Registry", "CAMS", "direct_feed", "fresh"),
    ("EPFO — Regional Office", "EPFO", "aggregated", "delayed"),
    ("NSDL / Protean e-Gov", "NSDL", "direct_feed", "fresh"),
    ("Kotak Mahindra Bank", "Kotak", "manual", "stale"),
]

BENCHMARKS = [
    (
        "BALANCED_60_40",
        "Nifty 50 / CRISIL Composite Bond 60:40",
        "60% Nifty 50 TRI and 40% CRISIL Composite Bond Fund Index, rebalanced quarterly.",
        {"indian_equity": 0.60, "debt": 0.40},
    ),
    (
        "AGGRESSIVE_80_20",
        "Nifty 500 / Debt 80:20",
        "80% Nifty 500 TRI and 20% CRISIL Short Term Bond Index.",
        {"indian_equity": 0.62, "intl_equity": 0.18, "debt": 0.20},
    ),
    (
        "CONSERVATIVE_30_70",
        "Conservative 30:70 Blend",
        "30% Nifty 50 TRI and 70% CRISIL Composite Bond Fund Index.",
        {"indian_equity": 0.30, "debt": 0.60, "cash": 0.10},
    ),
]

# symbol, name, type, asset_class, sector, region, price, prev_close, yield,
# expense, beta, volatility, esg, is_tax_free, substantially_identical_to
SECURITIES = [
    # --- Index and large-cap equity -----------------------------------------
    ("NIFTYBEES", "Nippon India ETF Nifty 50 BeES", "etf", "indian_equity", "Diversified", "India", 296.84, 294.10, 0.0112, 0.0005, 1.00, 0.148, 61.0, False, "SETFNIF50"),
    ("SETFNIF50", "SBI Nifty 50 ETF", "etf", "indian_equity", "Diversified", "India", 271.35, 268.90, 0.0110, 0.0007, 1.00, 0.148, 61.0, False, "NIFTYBEES"),
    ("UTINEXT50", "UTI Nifty Next 50 Index Fund", "mutual_fund", "indian_equity", "Large Cap", "India", 22.84, 22.61, 0.0000, 0.0032, 1.14, 0.192, 57.0, False, None),
    ("PPFAS-FLEXI", "Parag Parikh Flexi Cap Fund — Direct Growth", "mutual_fund", "indian_equity", "Flexi Cap", "India", 89.42, 88.61, 0.0000, 0.0063, 0.88, 0.141, 66.0, False, None),
    ("HDFC-MIDCAP", "HDFC Mid-Cap Opportunities Fund — Direct Growth", "mutual_fund", "indian_equity", "Mid Cap", "India", 178.26, 176.02, 0.0000, 0.0074, 1.09, 0.201, 54.0, False, None),
    ("AXIS-SMALL", "Axis Small Cap Fund — Direct Growth", "mutual_fund", "indian_equity", "Small Cap", "India", 112.68, 110.94, 0.0000, 0.0056, 1.16, 0.238, 51.0, False, None),
    ("MIRAE-ELSS", "Mirae Asset ELSS Tax Saver Fund — Direct Growth", "mutual_fund", "indian_equity", "ELSS", "India", 46.92, 46.41, 0.0000, 0.0057, 0.98, 0.163, 63.0, False, None),

    # --- Direct equity ------------------------------------------------------
    ("RELIANCE", "Reliance Industries Ltd", "stock", "indian_equity", "Energy & Retail", "India", 1_412.60, 1_396.85, 0.0035, None, 1.06, 0.238, 58.0, False, None),
    ("TCS", "Tata Consultancy Services Ltd", "stock", "indian_equity", "Information Technology", "India", 3_284.40, 3_312.15, 0.0182, None, 0.74, 0.207, 74.0, False, None),
    ("HDFCBANK", "HDFC Bank Ltd", "stock", "indian_equity", "Financials", "India", 1_742.85, 1_728.30, 0.0110, None, 0.92, 0.196, 69.0, False, None),
    ("INFY", "Infosys Ltd", "stock", "indian_equity", "Information Technology", "India", 1_586.20, 1_601.45, 0.0264, None, 0.81, 0.221, 76.0, False, None),
    ("ITC", "ITC Ltd", "stock", "indian_equity", "Consumer Staples", "India", 424.75, 421.90, 0.0338, None, 0.62, 0.174, 48.0, False, None),

    # --- International ------------------------------------------------------
    ("MON100", "Motilal Oswal Nasdaq 100 ETF", "etf", "intl_equity", "US Technology", "United States", 152.38, 150.12, 0.0000, 0.0058, 1.21, 0.226, 62.0, False, None),
    ("MAFANG", "Mirae Asset NYSE FANG+ ETF", "etf", "intl_equity", "US Growth", "United States", 84.16, 82.74, 0.0000, 0.0066, 1.34, 0.281, 57.0, False, None),
    ("FRANKLIN-USOPP", "Franklin India Feeder US Opportunities — Direct", "mutual_fund", "intl_equity", "Global Equity", "United States", 68.94, 68.02, 0.0000, 0.0061, 1.12, 0.219, 64.0, False, None),

    # --- Debt ---------------------------------------------------------------
    ("BHARATBOND33", "Bharat Bond ETF — April 2033", "etf", "debt", "Target Maturity", "India", 1_284.60, 1_285.90, 0.0716, 0.0005, 0.09, 0.041, 67.0, False, None),
    ("ICICI-CORPBOND", "ICICI Prudential Corporate Bond Fund — Direct Growth", "mutual_fund", "debt", "Corporate Bond", "India", 29.84, 29.86, 0.0742, 0.0032, 0.11, 0.033, 60.0, False, None),
    ("HDFC-SHORT", "HDFC Short Term Debt Fund — Direct Growth", "mutual_fund", "debt", "Short Duration", "India", 32.16, 32.18, 0.0728, 0.0028, 0.08, 0.026, 60.0, False, None),
    ("SBI-GILT", "SBI Magnum Gilt Fund — Direct Growth", "mutual_fund", "debt", "Government Securities", "India", 68.42, 68.51, 0.0704, 0.0046, 0.14, 0.052, 72.0, False, None),

    # --- Cash and liquid ----------------------------------------------------
    ("LIQUIDBEES", "Nippon India ETF Nifty 1D Rate Liquid BeES", "etf", "cash", "Overnight", "India", 1_000.00, 1_000.00, 0.0648, 0.0027, 0.00, 0.002, 70.0, False, None),
    ("ICICI-LIQUID", "ICICI Prudential Liquid Fund — Direct Growth", "mutual_fund", "cash", "Liquid", "India", 384.26, 384.19, 0.0672, 0.0020, 0.01, 0.003, 68.0, False, None),

    # --- Gold ---------------------------------------------------------------
    ("GOLDBEES", "Nippon India ETF Gold BeES", "etf", "gold", "Precious Metals", "India", 78.64, 77.92, 0.0000, 0.0082, 0.14, 0.152, None, False, "HDFCGOLD"),
    ("HDFCGOLD", "HDFC Gold ETF", "etf", "gold", "Precious Metals", "India", 79.18, 78.44, 0.0000, 0.0059, 0.14, 0.152, None, False, "GOLDBEES"),

    # --- Alternatives and REITs ---------------------------------------------
    ("EMBASSY", "Embassy Office Parks REIT", "reit", "alternatives", "Commercial Real Estate", "India", 386.40, 383.15, 0.0642, None, 0.71, 0.163, 64.0, False, None),
    ("MINDSPACE", "Mindspace Business Parks REIT", "reit", "alternatives", "Commercial Real Estate", "India", 358.92, 356.20, 0.0618, None, 0.68, 0.158, 62.0, False, None),
    ("INDIGRID", "IndiGrid Infrastructure Trust", "invit", "alternatives", "Power Transmission", "India", 148.26, 147.10, 0.0894, None, 0.54, 0.131, 71.0, False, None),
]

CHARITIES = [
    # name, registration (masked), mission area, location, rating, 80G category
    ("Prathama Shiksha Foundation", "AAA**1284K", "Education", "Pune, Maharashtra", 4.6, "50_capped"),
    ("Annapurna Seva Trust", "AAB**7739L", "Food Security & Nutrition", "Bengaluru, Karnataka", 4.8, "50_capped"),
    ("Sujala Water Mission", "AAC**2291M", "Water & Sanitation", "Jaipur, Rajasthan", 4.3, "50_capped"),
    ("Arogya Gramin Health Trust", "AAD**9016N", "Rural Healthcare", "Nashik, Maharashtra", 4.7, "50_capped"),
    ("Kalasangam Arts Society", "AAE**3389P", "Arts & Heritage", "Chennai, Tamil Nadu", 4.1, "50_capped"),
    ("Prime Minister's National Relief Fund", "AAF**0001Q", "Disaster Relief", "New Delhi", 5.0, "100_no_cap"),
    ("Swachh Bharat Kosh", "AAG**0002R", "Sanitation", "New Delhi", 5.0, "100_no_cap"),
]

EDUCATION_CONTENT = [
    ("Understanding Your EPF Statement", "guide", "Retirement Foundations", "beginner", 8,
     "What the employee, employer and pension columns on your passbook actually mean.",
     "Your own 12% and part of your employer's 12% go into EPF. The rest — 8.33% of a wage capped at "
     "Rs 15,000 — is diverted to EPS, the pension scheme. That is why the employer column in your passbook "
     "is smaller than your own."),
    ("EPF, PPF or NPS: which and why", "guide", "Retirement Foundations", "beginner", 10,
     "Three tax-advantaged wrappers with different lock-ins, limits and exit rules.",
     "EPF is automatic and employer-linked. PPF is voluntary, capped at Rs 1.5 lakh a year and entirely tax "
     "free. NPS allows the highest equity exposure and an extra Rs 50,000 deduction, but locks the money to "
     "age 60 and requires at least 40% of the corpus to buy an annuity."),
    ("Why your 80C limit is probably already full", "guide", "Tax Basics", "beginner", 7,
     "EPF, PPF, ELSS, insurance premium, home loan principal and tuition fees all share one Rs 1.5 lakh ceiling.",
     "Many salaried people invest in ELSS believing it adds to their deduction, when their EPF contribution "
     "alone has already used the entire section 80C limit. Check the headroom before you invest for tax."),
    ("Old regime or new regime", "video", "Tax Basics", "intermediate", 9,
     "The new regime has lower rates but almost no deductions. The choice is made afresh each year.",
     None),
    ("Nominee is not the same as heir", "guide", "Life Events", "beginner", 6,
     "A nominee receives the asset as a trustee. Your will decides who ultimately owns it.",
     "This is the single most common and most expensive planning mistake in India. If your nomination names "
     "one person and your will names another, the estate will very likely end up in dispute. Review both "
     "together, and after any marriage, birth or death in the family."),
    ("How capital gains on equity are taxed", "guide", "Tax Basics", "intermediate", 11,
     "Short-term at 20%, long-term at 12.5% with the first Rs 1.25 lakh of gains exempt each year.",
     "Holding for more than twelve months moves a listed equity gain from 20% to 12.5%, and the first "
     "Rs 1,25,000 of long-term gains each financial year is exempt entirely. Many investors never use that "
     "exemption — realising gains up to it and repurchasing costs nothing and resets your cost base."),
    ("Choosing your NPS asset mix", "guide", "Investing Basics", "intermediate", 12,
     "Equity is capped at 75% below age 50 and tapers thereafter. Auto and active choice explained.",
     None),
    ("SIP: why the date matters less than the habit", "video", "Investing Basics", "beginner", 7,
     "Consistency over timing, and what a systematic investment plan actually does to your average cost.",
     None),
    ("Diversification and concentration risk", "guide", "Investing Basics", "intermediate", 10,
     "Why holding a large position in one company is a different kind of risk from holding an index fund.",
     "Concentration works both ways. A single stock above 10% of a portfolio drives an outsized share of "
     "both gains and losses. An index fund at the same weight does not carry the same single-name risk."),
    ("Taking a PF advance: what to consider", "guide", "Life Events", "intermediate", 9,
     "Partial withdrawal is permitted for housing, medical treatment, education and marriage.",
     "A PF advance is not a loan and is not repaid, so the corpus and all its future compounding are gone. "
     "Withdrawal before five years of continuous service is also taxable."),
    ("Health insurance and section 80D", "guide", "Life Events", "beginner", 8,
     "Medical inflation runs well ahead of general inflation, and cover gets harder to buy with age.",
     None),
    ("Reading your consolidated account statement", "webinar", "Investing Basics", "beginner", 18,
     "The CAS from CAMS and KFintech shows every folio you hold. How to read it and what to check.",
     None),
]

FIRST_NAMES = [
    "Aarav", "Ananya", "Advait", "Bhavana", "Chirag", "Deepika", "Devansh", "Esha", "Farhan", "Gauri",
    "Harsh", "Ishaan", "Jaya", "Kabir", "Lavanya", "Manav", "Nandini", "Omkar", "Pranav", "Priya",
    "Rahul", "Riya", "Sanjay", "Shreya", "Tanvi", "Uday", "Vaishnavi", "Vikram", "Yash", "Zoya",
    "Aditi", "Arjun", "Kavya", "Nikhil", "Meera", "Rohan", "Sneha", "Varun", "Divya", "Karthik",
]

LAST_NAMES = [
    "Agarwal", "Bhattacharya", "Chandrasekhar", "Deshpande", "Iyer", "Joshi", "Kulkarni", "Menon",
    "Nair", "Pillai", "Rao", "Reddy", "Sharma", "Shetty", "Srinivasan", "Trivedi", "Verma", "Banerjee",
    "Chatterjee", "Gupta", "Kapoor", "Malhotra", "Mehta", "Patel", "Sengupta", "Subramanian", "Thakur",
    "Venkatesan", "Bhat", "Krishnan",
]

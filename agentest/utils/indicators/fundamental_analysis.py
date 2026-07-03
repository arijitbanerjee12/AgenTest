"""Fundamental & sentiment analysis for BUY/SELL signals using AI knowledge."""

from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path


# ── Sector Classification ─────────────────────────────────────────────

SECTOR_MAP: dict[str, str] = {
    # Large caps (top 30 Nifty 50)
    "RELIANCE": "Energy & Telecom",
    "TCS": "IT",
    "HDFCBANK": "Banking",
    "INFY": "IT",
    "ICICIBANK": "Banking",
    "HINDUNILVR": "FMCG",
    "ITC": "FMCG & Hotels",
    "SBIN": "Banking (PSU)",
    "BHARTIARTL": "Telecom",
    "KOTAKBANK": "Banking",
    "LT": "Engineering & Construction",
    "BAJFINANCE": "NBFC",
    "WIPRO": "IT",
    "AXISBANK": "Banking",
    "TITAN": "Retail & Jewelry",
    "HCLTECH": "IT",
    "SUNPHARMA": "Pharma",
    "MARUTI": "Automotive",
    "ULTRACEMCO": "Cement",
    "BAJAJFINSV": "Financial Services",
    "NTPC": "Power",
    "ONGC": "Oil & Gas",
    "ADANIPORTS": "Infrastructure & Logistics",
    "POWERGRID": "Power Transmission",
    "M&M": "Automotive",
    "TRENT": "Retail",
    "GRASIM": "Cement & Textiles",
    "JSWSTEEL": "Steel",
    "COALINDIA": "Mining (PSU)",
    "APOLLOHOSP": "Healthcare",
    "ASIANPAINT": "Paints & Chemicals",
    "BEL": "Defense & Aerospace",
    "BAJAJ-AUTO": "Automotive",
    "CIPLA": "Pharma",
    "DRREDDY": "Pharma",
    "EICHERMOT": "Automotive",
    "HDFCLIFE": "Insurance",
    "HEROMOTOCO": "Automotive",
    "HINDALCO": "Aluminum & Metals",
    "ICICIGI": "Insurance",
    "INDUSINDBK": "Banking",
    "LTF": "NBFC",
    "M&M": "Automotive",
    "NESTLEIND": "FMCG",
    "SHRIRAMFIN": "NBFC",
    "SBILIFE": "Insurance",
    "TATACONSUM": "FMCG",
    "TATASTEEL": "Steel",
    "TECHM": "IT",
    "WIPRO": "IT",

    # ETFs
    "NIFTYBEES": "Index ETF (Nifty 50)",
    "JUNIORBEES": "Index ETF (Nifty Next 50)",
    "MON100": "International ETF (US Nasdaq)",
    "MAFANG": "International ETF (FANG+)",
    "MAHKTECH": "International ETF (Hong Kong Tech)",
    "MONQ50": "International ETF (US QQQ)",
    "MASPTOP50": "International ETF (S&P 500 Top 50)",
    "TMPV": "International ETF (US Momentum)",
    "MNC": "Index ETF (MNC)",
    "NIFTY1": "Index ETF (Nifty 50)",
    "SETFNIF50": "Index ETF (Nifty 50)",
    "QNIFTY": "Index ETF (Nifty 50)",
    "NIFTYIETF": "Index ETF (Nifty 50)",
    "NIFTYBETA": "Index ETF (Nifty Beta)",
    "NIFTYETF": "Index ETF (Nifty 50)",
    "CPSEETF": "PSU ETF (CPSE)",
    "ICICIB22": "PSU ETF (BSE PSU)",
    "SBIETFIT": "Sector ETF (IT)",
    "ITBEES": "Sector ETF (IT)",
    "HNGSNGBEES": "Sector ETF (Hang Seng)",
    "CONSUMBEES": "Sector ETF (Consumption)",
    "AUTOBEES": "Sector ETF (Auto)",
    "PHARMABEES": "Sector ETF (Pharma)",
    "BANKBEES": "Sector ETF (Banking)",
    "INFRAIETF": "Sector ETF (Infrastructure)",
    "AXISNIFTY": "Index ETF (Nifty 50)",
    "HDFCGOLD": "Gold ETF",
    "GOLDBEES": "Gold ETF",
    "GOLDETF": "Gold ETF",
    "SETFGOLD": "Gold ETF",
    "SILVERBEES": "Silver ETF",
    "PSUBNKBEES": "PSU ETF (PSU Banks)",
    "LIQUIDBEES": "Debt ETF (Liquid)",
    "LIQUIDCASE": "Debt ETF (Liquid)",
    "MOM30IETF": "Factor ETF (Momentum 30)",
    "HDFCMOMENT": "Factor ETF (Momentum)",
    "NEXT50IETF": "Index ETF (Next 50)",
    "MID150BEES": "Index ETF (Midcap 150)",
    "MOREALTY": "Sector ETF (Realty)",
    "FINIETF": "Sector ETF (Financial Services)",
    "AONETMMQ50": "Factor ETF (Alpha Low Vol 50)",
    "AONETOTAL": "Factor ETF (Alpha Quality)",
    "ALPHAETF": "Factor ETF (Alpha)",
    "ALPL30IETF": "Factor ETF (Alpha Low Vol 30)",
    "GROWWMETAL": "Factor ETF (Momentum - Metal)",
    "GROWWRLTY": "Factor ETF (Momentum - Realty)",
    "MOM100": "Index ETF (Momentum 100)",
    "MOMENTUM50": "Factor ETF (Momentum 50)",
    "EVINDIA": "Thematic ETF (EV)",
    "MIDCAP": "Index ETF (Midcap)",
    "SMALLCAP": "Index ETF (Smallcap)",
    "MONIFTY500": "Index ETF (Nifty 500)",
    "AUTOIETF": "Sector ETF (Auto)",
    "FMCGIETF": "Sector ETF (FMCG)",
    "HEALTHY": "Sector ETF (Healthcare)",
    "HEALTHCARE": "Sector ETF (Healthcare)",
    "CONS": "Sector ETF (Consumption)",
    "EVIETF": "Thematic ETF (EV)",
    "ESENSEX": "Index ETF (Sensex)",
    "FLEXIADD": "Factor ETF (Flexi Cap)",
    "GROWWCHEM": "Factor ETF (Momentum - Chemicals)",
    "GROWWDEFNC": "Factor ETF (Momentum - Defense)",
    "GROWWEV": "Factor ETF (Momentum - EV)",
    "GROWWMOM50": "Factor ETF (Momentum 50)",
    "LTGILTBEES": "Debt ETF (Gilt)",
    "MIDSMALL": "Index ETF (Mid Small Cap)",
    "MOHEALTH": "Factor ETF (Momentum - Healthcare)",
    "MOSMALL250": "Index ETF (Small Cap 250)",
    "MOCAPITAL": "Factor ETF (Momentum - Capital Goods)",
    "NV20IETF": "Factor ETF (Nifty Value 20)",
    "PVTBANIETF": "Sector ETF (Private Bank)",
    "SMALL250": "Index ETF (Small Cap 250)",
    "TOP100CASE": "Factor ETF (Top 100 Quality)",
    "IDFNIFTYET": "Index ETF (Nifty 50)",
    "NETF": "Index ETF (Nifty 50)",

    # Mid/Small Cap — fundamentally strong
    "PERSISTENT": "Digital Engineering",
    "RATEGAIN": "Travel Tech",
    "AFFLE": "Digital Advertising",
    "INTELLECT": "Banking Tech",
    "INDGN": "Life Sciences IT",
    "NEWGEN": "Software",

    # Mid/Small Cap — Water Infrastructure
    "WABAG": "Water Infrastructure",
    "EIEL": "Water Infrastructure",
    "INDIANHUME": "Water Infrastructure",
    "DENTA": "Water Infrastructure",
    "IONEXCHANG": "Water Infrastructure",

    # Mid/Small Cap — Defence
    "HAL": "Defense & Aerospace",
    "DATAPATTNS": "Defense & Aerospace",
    "PARAS": "Defense & Aerospace",
    "BDL": "Defense & Aerospace",

    # Mid/Small Cap — Electronics Manufacturing
    "DIXON": "Electronics Manufacturing",
    "KAYNES": "Electronics Manufacturing",
    "CGPOWER": "Electronics Manufacturing",
    "SYRMA": "Electronics Manufacturing",
    "AVALON": "Electronics Manufacturing",

    # Mid/Small Cap — AI / Power Infrastructure
    "SIEMENS": "Industrial Automation",
    "ABB": "Industrial Automation",
    "SCHNEIDER": "Industrial Automation",

    # Mid/Small Cap — Financials
    "ANGELONE": "Financial Services",
    "MCX": "Financial Services",
}

KNOWLEDGE_BASE: dict[str, dict] = {
    "IT": {"pe_range": (25, 35), "growth_outlook": "moderate", "trend_note": "Global IT spending stable; rupee weakness tailwind for exports"},
    "Banking": {"pe_range": (15, 22), "growth_outlook": "positive", "trend_note": "Credit growth healthy, NIMs stable; asset quality best in decade"},
    "Banking (PSU)": {"pe_range": (7, 12), "growth_outlook": "positive", "trend_note": "PSU banks seeing margin expansion; government capex push helps"},
    "FMCG": {"pe_range": (40, 55), "growth_outlook": "stable", "trend_note": "Rural recovery underway; urban demand steady; input costs easing"},
    "FMCG & Hotels": {"pe_range": (30, 45), "growth_outlook": "positive", "trend_note": "ITC: FMCG steady + hotels rebound; cigarette volumes stable"},
    "Pharma": {"pe_range": (30, 45), "growth_outlook": "positive", "trend_note": "USFDA approvals improving; India formulations stable; CDMO growing"},
    "Automotive": {"pe_range": (20, 30), "growth_outlook": "moderate", "trend_note": "EV transition cautious; two-wheeler demand recovering; exports weak"},
    "Energy & Telecom": {"pe_range": (12, 20), "growth_outlook": "stable", "trend_note": "Reliance: Jio tariff hikes + retail expansion; O2C margins volatile"},
    "Telecom": {"pe_range": (12, 18), "growth_outlook": "positive", "trend_note": "ARPU uptrend; tariff hikes sustaining; 5G capex peaking"},
    "Engineering & Construction": {"pe_range": (25, 40), "growth_outlook": "positive", "trend_note": "Capex super-cycle; government infra push; order books strong"},
    "NBFC": {"pe_range": (18, 28), "growth_outlook": "positive", "trend_note": "Credit demand strong; Co-lending models scaling; NIMs stable"},
    "Financial Services": {"pe_range": (18, 28), "growth_outlook": "positive", "trend_note": "Broad-based credit growth; capital markets booming"},
    "Retail & Jewelry": {"pe_range": (50, 70), "growth_outlook": "positive", "trend_note": "Titan: jewelry demand strong; watches segment recovering"},
    "Retail": {"pe_range": (50, 80), "growth_outlook": "positive", "trend_note": "Organized retail gaining share; Trent/Zudio expanding rapidly"},
    "Cement": {"pe_range": (20, 30), "growth_outlook": "moderate", "trend_note": "Volume growth steady; pricing pressure from excess capacity"},
    "Power": {"pe_range": (15, 22), "growth_outlook": "positive", "trend_note": "Power demand growing 6-7% YoY; PLF improving; renewable capex"},
    "Oil & Gas": {"pe_range": (8, 15), "growth_outlook": "stable", "trend_note": "ONGC: subsidy burden manageable; production flat; crude volatile"},
    "Power Transmission": {"pe_range": (18, 28), "growth_outlook": "positive", "trend_note": "Green energy corridor expansion; inter-regional capacity growing"},
    "Infrastructure & Logistics": {"pe_range": (25, 40), "growth_outlook": "positive", "trend_note": "Adani Ports: cargo volume growing; logistics integration scaling"},
    "Steel": {"pe_range": (8, 15), "growth_outlook": "moderate", "trend_note": "Global steel prices soft; China export overhang; domestic demand steady"},
    "Mining (PSU)": {"pe_range": (6, 10), "growth_outlook": "stable", "trend_note": "Coal India: production record; e-auction premium normalizing"},
    "Healthcare": {"pe_range": (30, 45), "growth_outlook": "positive", "trend_note": "Apollo: hospital occupancy high; insurance-linked revenue growing"},
    "Paints & Chemicals": {"pe_range": (35, 55), "growth_outlook": "stable", "trend_note": "Asian Paints: volume recovery; competitive pressure from Grasim entry"},
    "Aluminum & Metals": {"pe_range": (8, 14), "growth_outlook": "stable", "trend_note": "Hindalco: Novelis stable; aluminum prices range-bound"},
    "Insurance": {"pe_range": (18, 25), "growth_outlook": "positive", "trend_note": "Insurance penetration rising; regulatory tailwinds for private players"},
    "Defense & Aerospace": {"pe_range": (35, 55), "growth_outlook": "strong", "trend_note": "Make in India push; export orders rising; government capex supportive"},
    "Cement & Textiles": {"pe_range": (20, 30), "growth_outlook": "stable", "trend_note": "Grasim: cement expansion on track; VSF demand recovering"},

    # ETF notes
    "Index ETF (Nifty 50)": {"pe_range": (20, 25), "growth_outlook": "stable", "trend_note": "Tracks Nifty 50; broad market proxy; low-cost passive investment"},
    "Index ETF (Nifty Next 50)": {"pe_range": (25, 35), "growth_outlook": "positive", "trend_note": "Mid-large cap; higher growth potential than Nifty 50"},
    "International ETF (US Nasdaq)": {"pe_range": (30, 40), "growth_outlook": "positive", "trend_note": "Tracks US tech; AI tailwind; forex risk via INR depreciation hedge"},
    "International ETF (FANG+)": {"pe_range": (30, 45), "growth_outlook": "positive", "trend_note": "US mega-cap tech; AI/cloud momentum; rate cut expectations supportive"},
    "International ETF (Hong Kong Tech)": {"pe_range": (18, 25), "growth_outlook": "stable", "trend_note": "China tech regulatory stability; valuations attractive"},
    "International ETF (US QQQ)": {"pe_range": (30, 40), "growth_outlook": "positive", "trend_note": "Nasdaq-100 tracker; AI theme; USD/INR hedge"},
    "International ETF (S&P 500 Top 50)": {"pe_range": (25, 35), "growth_outlook": "positive", "trend_note": "US large cap tracker; diversified; forex gain tailwind"},
    "International ETF (US Momentum)": {"pe_range": (25, 35), "growth_outlook": "positive", "trend_note": "US momentum factor; follows US market trends"},
    "Index ETF (MNC)": {"pe_range": (30, 40), "growth_outlook": "stable", "trend_note": "Multinational companies in India; quality bias"},
    "PSU ETF (CPSE)": {"pe_range": (8, 14), "growth_outlook": "positive", "trend_note": "Central PSUs; government divestment + dividend yield play"},
    "PSU ETF (BSE PSU)": {"pe_range": (8, 14), "growth_outlook": "positive", "trend_note": "PSU basket; government capex push; valuation rerating ongoing"},
    "Sector ETF (IT)": {"pe_range": (25, 35), "growth_outlook": "moderate", "trend_note": "IT sector tracker; global tech spending linked; rupee impact"},
    "Sector ETF (Pharma)": {"pe_range": (30, 40), "growth_outlook": "positive", "trend_note": "Pharma sector; USFDA approvals; domestic formulations growth"},
    "Sector ETF (Auto)": {"pe_range": (18, 28), "growth_outlook": "moderate", "trend_note": "Auto sector; EV transition; rural demand recovery play"},
    "Sector ETF (Banking)": {"pe_range": (15, 22), "growth_outlook": "positive", "trend_note": "Banking sector; credit growth + NIM stability"},
    "Sector ETF (Financial Services)": {"pe_range": (16, 24), "growth_outlook": "positive", "trend_note": "Financials basket; credit + capital markets growth"},
    "Sector ETF (Consumption)": {"pe_range": (35, 50), "growth_outlook": "stable", "trend_note": "Consumption theme; rural recovery; premiumization trend"},
    "Sector ETF (Infrastructure)": {"pe_range": (22, 35), "growth_outlook": "positive", "trend_note": "Infra theme; government capex cycle; order book momentum"},
    "Sector ETF (Realty)": {"pe_range": (25, 40), "growth_outlook": "positive", "trend_note": "Real estate; consolidation + premium housing demand"},
    "Sector ETF (Private Bank)": {"pe_range": (18, 25), "growth_outlook": "positive", "trend_note": "Private banks; market share gains from PSUs; best-in-class NIMs"},
    "Sector ETF (Hang Seng)": {"pe_range": (10, 15), "growth_outlook": "stable", "trend_note": "HK market; China recovery; cheap valuations; dividend yield"},
    "Factor ETF (Momentum)": {"pe_range": (20, 30), "growth_outlook": "positive", "trend_note": "Momentum strategy; benefits in trending markets; churn cost consideration"},
    "Factor ETF (Alpha Low Vol 30)": {"pe_range": (20, 30), "growth_outlook": "stable", "trend_note": "Low volatility + alpha; defensive with upside potential"},
    "Factor ETF (Alpha Quality)": {"pe_range": (22, 32), "growth_outlook": "stable", "trend_note": "Quality factor; strong companies; lower drawdowns historically"},
    "Factor ETF (Alpha)": {"pe_range": (20, 30), "growth_outlook": "positive", "trend_note": "Multi-factor alpha strategy; aims to beat Nifty 50"},
    "Factor ETF (Nifty Value 20)": {"pe_range": (12, 20), "growth_outlook": "stable", "trend_note": "Value strategy; contrarian; works in mean-reversion phases"},
    "Factor ETF (Momentum 50)": {"pe_range": (20, 30), "growth_outlook": "positive", "trend_note": "Momentum 50; top trending stocks; high churn strategy"},
    "Factor ETF (Flexi Cap)": {"pe_range": (20, 30), "growth_outlook": "stable", "trend_note": "Flexi-cap allocation; active management within ETF wrapper"},
    "Factor ETF (Top 100 Quality)": {"pe_range": (25, 35), "growth_outlook": "stable", "trend_note": "Quality screen on Nifty 100; ROE focus; lower beta"},
    "Thematic ETF (EV)": {"pe_range": (25, 45), "growth_outlook": "strong", "trend_note": "EV theme; policy support; long-term structural story"},
    "Debt ETF (Liquid)": {"pe_range": (0, 0), "growth_outlook": "stable", "trend_note": "Low-risk; overnight/liquid funds; used for cash parking"},
    "Debt ETF (Gilt)": {"pe_range": (0, 0), "growth_outlook": "positive", "trend_note": "Gilt fund; rate cut cycle benefits; duration play"},
    "Gold ETF": {"pe_range": (0, 0), "growth_outlook": "positive", "trend_note": "Gold prices at highs; central bank buying; geopolitical hedge"},
    "Silver ETF": {"pe_range": (0, 0), "growth_outlook": "positive", "trend_note": "Silver catch-up to gold; industrial + precious metal demand"},
    "Index ETF (Midcap 150)": {"pe_range": (25, 35), "growth_outlook": "positive", "trend_note": "Midcap play; higher growth but higher volatility"},
    "Index ETF (Midcap)": {"pe_range": (25, 35), "growth_outlook": "positive", "trend_note": "Midcap index; growth + premium valuation"},
    "Index ETF (Smallcap)": {"pe_range": (30, 50), "growth_outlook": "positive", "trend_note": "Small cap; high growth; high volatility; long-term outperformance potential"},
    "Index ETF (Nifty 500)": {"pe_range": (22, 30), "growth_outlook": "stable", "trend_note": "Broad market; diversification; core portfolio holding"},
    "Index ETF (Mid Small Cap)": {"pe_range": (25, 40), "growth_outlook": "positive", "trend_note": "Mid + small cap; growth oriented; higher risk"},
    "Index ETF (Small Cap 250)": {"pe_range": (30, 45), "growth_outlook": "positive", "trend_note": "Small cap 250; broad small-cap exposure; long-term growth"},
    "Index ETF (Sensex)": {"pe_range": (20, 25), "growth_outlook": "stable", "trend_note": "Tracks BSE Sensex; blue-chip; stable returns"},
    "Here": {"pe_range": (0, 0), "growth_outlook": "stable", "trend_note": ""},

    "Factor ETF (Momentum - Defense)": {"pe_range": (35, 55), "growth_outlook": "strong", "trend_note": "Defense momentum; government push for indigenization; export orders"},
    "Factor ETF (Momentum - Metal)": {"pe_range": (8, 14), "growth_outlook": "moderate", "trend_note": "Metal momentum; commodity price linked; cyclical"},
    "Factor ETF (Momentum - Realty)": {"pe_range": (25, 40), "growth_outlook": "positive", "trend_note": "Realty momentum; housing upcycle; consolidation tailwinds"},
    "Factor ETF (Momentum - EV)": {"pe_range": (25, 45), "growth_outlook": "strong", "trend_note": "EV momentum; policy support; charging infra scaling"},
    "Factor ETF (Momentum - Capital Goods)": {"pe_range": (30, 50), "growth_outlook": "strong", "trend_note": "Capital goods momentum; capex cycle; Make in India"},
    "Factor ETF (Momentum - Chemicals)": {"pe_range": (25, 40), "growth_outlook": "stable", "trend_note": "Chemical momentum; global supply chain shift; China+1"},
    "Factor ETF (Momentum - Healthcare)": {"pe_range": (30, 45), "growth_outlook": "positive", "trend_note": "Healthcare momentum; hospitals + pharma; demand uptick"},
    "Factor ETF (Alpha Low Vol 50)": {"pe_range": (18, 28), "growth_outlook": "stable", "trend_note": "Low volatility + alpha on 50 stocks; defensive with edge"},

    # Mid/Small Cap sectors
    "Digital Engineering": {"pe_range": (25, 40), "growth_outlook": "positive", "trend_note": "Persistent Systems: product engineering & digital transformation; AI/cloud partnerships; enterprise data readiness"},
    "Travel Tech": {"pe_range": (40, 60), "growth_outlook": "positive", "trend_note": "RateGain: travel/hospitality SaaS; proprietary data moat; AI-driven revenue intelligence for hotels"},
    "Digital Advertising": {"pe_range": (35, 50), "growth_outlook": "positive", "trend_note": "Affle: mobile advertising platform; CPCU model; consumer behavior data driving ad efficiency"},
    "Banking Tech": {"pe_range": (25, 40), "growth_outlook": "positive", "trend_note": "Intellect Design Arena: banking technology; AI agents in core banking; Purple Fabric platform; regulatory compliance focused"},
    "Life Sciences IT": {"pe_range": (30, 45), "growth_outlook": "positive", "trend_note": "Indegene: life sciences digital; clinical trials + regulatory docs; AI for compliance-heavy workflows"},

    "Water Infrastructure": {"pe_range": (15, 25), "growth_outlook": "positive", "trend_note": "Water infrastructure EPC; Jal Jeevan Mission tailwind; government capex on water supply & wastewater treatment; urbanization driving demand"},

    "Software": {"pe_range": (20, 35), "growth_outlook": "positive", "trend_note": "Newgen Software: low-code BPM/ECM platform; AI-driven process automation; enterprise digital transformation"},
    "Electronics Manufacturing": {"pe_range": (25, 45), "growth_outlook": "positive", "trend_note": "India EMS ecosystem; PLI scheme tailwind; Apple supply chain shift; component localization drive"},
    "Industrial Automation": {"pe_range": (35, 55), "growth_outlook": "positive", "trend_note": "Factory automation; AI/data center power infrastructure; grid modernization; capex super-cycle beneficiary"},
}

SPECIFIC_STOCK_NOTES: dict[str, list[str]] = {
    "RELIANCE": ["Jio tariff hike cycle boosting ARPU", "Retail expanding rapidly", "O2C margins under pressure from global refining"],
    "TCS": ["AI/cloud deal pipeline strong", "Hiring pick-up signals demand recovery", "FY25 revenue growth guided 4-6%"],
    "HDFCBANK": ["Merger synergies with HDFC emerging", "Retail + corporate loan growth healthy", "NIM under some compression"],
    "INFY": ["Large deal wins in Q4", "AI-first strategy gaining traction", "Attrition stable at 12-13%"],
    "ICICIBANK": ["Best-in-class NIM", "SME + retail driving growth", "Asset quality best in a decade"],
    "HINDUNILVER": ["Rural recovery driving volume growth", "Premiumisation strategy working", "Input cost tailwinds"],
    "ITC": ["Cigarette volumes stable", "FMCG business turning profitable", "Hotels business monetization"],
    "SBIN": ["PSU banking leader", "Credit growth 14%+", "Asset quality improvement ongoing"],
    "BHARTIARTL": ["ARPU uptrend from tariff hikes", "5G capex largely done", "Africa operations stabilizing"],
    "KOTAKBANK": ["Retail franchise strong", "NIMs stable", "New CEO continuity assured"],
    "LT": ["Record order book >₹4.5L Cr", "Capex super-cycle beneficiary", "International orders growing"],
    "BAJFINANCE": ["AUM growth 25%+", "Asset quality stable", "Digital distribution scaling"],
    "AXISBANK": ["Retail + SME focus", "Margins improving", "Subsidiaries unlocking value"],
    "MARUTI": ["SUV launches gaining share", "CNG portfolio differentiation", "EV entry with e-Vitara planned"],
    "NTPC": ["Power demand growing 6-7%", "RE capacity addition accelerating", "Dividend yield attractive"],
    "ONGC": ["Subsidy burden manageable", "Production from KG basin ramp-up", "Crude price sensitivity high"],
    "POWERGRID": ["Regulatory clarity on RoE", "Green energy corridor builds", "Inter-regional line expansion"],
    "ULTRACEMCO": ["Volume growth 8-10%", "Cost reduction via green energy", "Industry consolidation benefit"],
    "TRENT": ["Zudio format scaling rapidly", "Westside stable", "Star acquisition now profitable"],
    "JSWSTEEL": ["Capacity expansion to 37MT", "US tariffs impact manageable", "India demand strong"],
    "GRASIM": ["Cement expansion to 80MT", "VSF demand recovering", "Paints business new entrant"],
    "ADANIPORTS": ["Cargo volume growth 10%+", "Logistics vertical scaling", "Debt reduction on track"],
    "BEL": ["Order book >₹70K Cr", "Export orders growing", "Make in India defense push"],
    "APOLLOHOSP": ["Hospital occupancy ~68%", "Insurance-led patient growth", "New hospital expansion"],
    "COALINDIA": ["Record production 780MT", "e-auction premium normalizing", "Dividend yield attractive"],
    "CIPLA": ["USFDA pipeline strong", "Indialaunch momentum", "Respiratory franchise leadership"],
    "DRREDDY": ["US generic launches driving growth", "Russia operations stable", "NLEM impact manageable"],
    "EICHERMOT": ["Royal Enfield demand strong", "New models (Hunter, Shotgun) successful", "Export recovery pending"],
    "NESTLEIND": ["Volume recovery in Q4", "Rural distribution expansion", "Input costs easing"],
    "TATASTEEL": ["European operations restructuring", "India capacity expansion to 23MT", "Global steel price headwinds"],
    "WIPRO": ["Consulting-led deals growing", "AI/automation focus", "Margins under pressure from wage hikes"],
    "BAJAJ-AUTO": ["Export recovery key monitorable", "EV Chetak scaling", "Domestic 2W demand improving"],
    "HEROMOTOCO": ["Entry into EV with Vida", "Rural demand recovery", "Margins recovering from RM easing"],
    "HCLTECH": ["ER&D division strong", "Cloud migration deals", "IBM partnership products"],
    "BAJAJFINSV": ["Cross-sell across Bajaj group", "AUM + insurance premium synergy", "Valuation supportive"],
    "SUNPHARMA": ["Specialty pipeline (Ilumya, Winlevi)", "Taro acquisition synergy", "Domestic formulations growing"],
    "SHRIRAMFIN": ["AUM growth 20%+", "Asset quality improving", "Co-lending partnerships scaling"],
    "TITAN": ["Jewelry demand robust", "Studded share improving", "Watches + eyewear recovery"],
    "TATACONSUM": ["International business mix improving", "India beverages stable", "Cost optimization program"],
    "SBILIFE": ["APEx margins improving", "Protection share growing", "Bancassurance channel strong"],
    "HDFCLIFE": ["VNB margin 27%+", "Credit life + protection mix improving", "Distribution network extensive"],
    "INDUSINDBK": ["Merger with BFIL completing", "Corporate book rebalancing", "NIM expectations improving"],

    # Mid/Small Cap — Digital / Tech
    "PERSISTENT": ["AI-first engineering partnerships", "Enterprise data readiness focus", "Proprietary IP building", "Tier-1 IT peer in digital engineering"],
    "RATEGAIN": ["Proprietary travel/hospitality data moat", "AI revenue intelligence platform", "Global hotel chain client base", "SaaS recurring revenue model"],
    "AFFLE": ["Unique CPCU (cost-per-converted-user) model", "Consumer behavior + conversion data advantage", "Mobile-first ad platform", "Profitable growth with strong cash flows"],
    "INTELLECT": ["Purple Fabric platform with embedded AI agents", "Mission-critical banking workflow focus", "Regulatory compliance DNA", "1,200+ financial institution clients"],
    "INDGN": ["Deep life sciences domain expertise", "AI for clinical trials & regulatory docs", "FDA compliance knowledge", "Pharma + biotech client base"],
    "NEWGEN": ["Low-code BPM/ECM platform for digital transformation", "AI-driven process automation", "Government + BFSI client base", "Strong product IP with recurring revenue"],

    # Mid/Small Cap — Water Infrastructure
    "WABAG": ["Global water & wastewater EPC leader", "Strong order book in India & international markets", "Advanced water treatment technologies", "Jal Jeevan Mission beneficiary"],
    "EIEL": ["Water & wastewater treatment plant EPC", "Sewage treatment + common effluent treatment plants", "Government contracts for water supply schemes", "15+ years of execution track record"],
    "INDIANHUME": ["Pioneer in pipe manufacturing for water supply", "Hume pipes + prestressed concrete pipes", "Government water infrastructure projects", "Established relationships with state water boards"],
    "DENTA": ["Groundwater recharge & water management specialist", "Civil engineering contractor for water projects", "Karnataka-focused with Jal Jeevan Mission exposure", "Recently IPO'd in Jan 2025"],
    "IONEXCHANG": ["Strong technology moat in ion exchange resins", "Industrial water treatment specialist", "Municipal + industrial wastewater solutions", "Long-standing government relationships"],

    # Mid/Small Cap — Defence
    "HAL": ["Tejas fighter jet production ramping", "Helicopter division growth (LCH, LUH)", "Record order book >₹1L Cr", "Strongest defence compounder in India"],
    "DATAPATTNS": ["Indigenous radar & electronic warfare systems", "Space-grade electronics", "High R&D moat in defence electronics", "Make in India defence push beneficiary"],
    "PARAS": ["Defence optics & night vision technology", "Space components manufacturing", "Niche technology with high entry barriers", "Growing order book from DRDO + private sector"],
    "BDL": ["Missile systems leader (Akash, Nag, Astra)", "Strong parentage (DRDO tech transfer)", "Export orders growing", "Long-term production visibility from armed forces induction"],

    # Mid/Small Cap — Electronics Manufacturing
    "DIXON": ["India's EMS leader; Apple ecosystem exposure", "Mobile manufacturing scaling rapidly", "Consumer electronics + home appliances", "PLI scheme major beneficiary"],
    "KAYNES": ["High-end EMS for aerospace & industrial", "Aerospace electronics certified", "IoT + smart metering product portfolio", "Export-driven growth story"],
    "CGPOWER": ["Semiconductor ecosystem play with CG Semi", "Power & industrial electronics", "Railway electrification beneficiary", "Legacy brand with manufacturing scale"],
    "SYRMA": ["PCB assembly + box build capabilities", "Automotive + industrial electronics", "EMS with design-led manufacturing", "Rapid revenue growth trajectory"],
    "AVALON": ["Clean room electronics manufacturing", "Aerospace & defence electronics", "Medical device electronics exposure", "High-value assembly expertise"],

    # Mid/Small Cap — AI / Power Infrastructure
    "SIEMENS": ["Factory automation & digital twin leader", "Rail electrification + smart grid", "AI-enabled industrial IoT play", "Capex super-cycle beneficiary"],
    "ABB": ["Industrial automation & robotics", "Data center power infrastructure", "EV charging + grid modernization", "Strong global technology backing"],
    "SCHNEIDER": ["Data center cooling & power management", "Building automation & energy efficiency", "Medium voltage switchgear leader", "AI infra power demand tailwind"],

    # Mid/Small Cap — Financials
    "ANGELONE": ["Discount broking market share leader", "Technology-first trading platform", "Client additions stabilizing after peak", "Diversifying into wealth management"],
    "MCX": ["Monopoly commodity exchange in India", "Options trading volume surge", "SEBI regulatory support for commodity derivatives", "High operating leverage play"],
}

# ETF-specific notes
ETF_NOTES: dict[str, list[str]] = {
    "LIQUIDBEES": ["Low-risk cash equivalent", "Used for liquidity management", "Returns 6-7% annualized"],
    "GOLDBEES": ["Gold at all-time highs", "Central bank buying supportive", "Geopolitical hedge"],
    "SILVERBEES": ["Silver tracking gold uptrend", "Industrial demand (solar, EVs) rising", "Catch-up trade possible"],
    "SETFNIF50": ["Nifty 50 tracker", "Low expense ratio", "Core portfolio holding"],
    "NIFTYBEES": ["Nifty 50 tracker", "Most liquid index ETF in India", "Low tracking error"],
}


def _get_sector(symbol: str) -> str:
    clean = symbol.removesuffix(".NS")
    return SECTOR_MAP.get(clean, SECTOR_MAP.get(symbol, "Unknown"))


def _get_knowledge(sector: str) -> dict:
    return KNOWLEDGE_BASE.get(sector, {"pe_range": (15, 25), "growth_outlook": "stable", "trend_note": "No specific sector data available"})


def _get_notes(symbol: str, sector: str) -> list[str]:
    clean = symbol.removesuffix(".NS")
    notes = SPECIFIC_STOCK_NOTES.get(clean, [])
    if not notes:
        etf_note = ETF_NOTES.get(clean)
        if etf_note:
            notes = etf_note
    if not notes and "ETF" in sector:
        notes = [KNOWLEDGE_BASE.get(sector, {}).get("trend_note", "No specific notes")]
    if not notes:
        notes = ["No specific stock news in knowledge base"]
    return notes


def _score_sentiment(sector: str, action: str, reason: str, knowledge: dict) -> tuple[str, float]:
    """Score market sentiment from 0.0 (negative) to 1.0 (positive)."""
    outlook = knowledge.get("growth_outlook", "stable")
    base_scores = {"strong": 0.75, "positive": 0.65, "stable": 0.5, "moderate": 0.4}
    base = base_scores.get(outlook, 0.5)

    if action == "BUY":
        if "strong buy" in reason:
            base += 0.15
        elif "cross" in reason:
            base += 0.10
        base = min(base, 0.95)
    elif action == "SELL":
        if "strong sell" in reason:
            base -= 0.15
        elif "bearish" in reason:
            base -= 0.10
        elif "below EMA" in reason:
            base -= 0.05
        base = max(base, 0.1)

    sentiment = "bullish" if base > 0.6 else "bearish" if base < 0.4 else "neutral"
    return sentiment, round(base, 2)


def _determine_fundamental_support(sector: str, action: str, sentiment_score: float) -> tuple[str, str, str]:
    """Check if fundamentals support the technical signal."""
    knowledge = _get_knowledge(sector)
    outlook = knowledge.get("growth_outlook", "stable")
    trend = knowledge.get("trend_note", "")

    # Positive outlook sectors → BUY supported, SELL contradicted
    if outlook in ("strong", "positive"):
        if action == "BUY":
            support = "support"
            details = f"Sector ({sector}): {trend} — supports bullish technical view"
            verdict = "buy"
        else:
            support = "contradict"
            details = f"Sector ({sector}): {trend} — fundamentals look positive despite technical SELL"
            verdict = "watch"
    # Stable → neutral
    elif outlook == "stable":
        support = "neutral"
        details = f"Sector ({sector}): {trend} — fundamentals neutral on the technical signal"
        verdict = action.lower()
    # Moderate → SELL supported, BUY warns
    else:
        if action == "SELL":
            support = "support"
            details = f"Sector ({sector}): {trend} — weak fundamentals align with technical SELL"
            verdict = "sell"
        else:
            support = "neutral"
            details = f"Sector ({sector}): {trend} — moderate fundamentals; technical BUY may be premature"
            verdict = "watch"

    if sentiment_score < 0.3:
        support = "support" if action == "SELL" else "contradict"
        details += " | Market sentiment is bearish."
        verdict = "sell"
    elif sentiment_score > 0.7:
        support = "support" if action == "BUY" else "contradict"
        details += " | Market sentiment is bullish."
        verdict = "buy"

    return support, details, verdict


def analyze_signal(symbol: str, action: str, reason: str, category: str) -> dict:
    """Analyze a single BUY/SELL signal using AI knowledge."""
    sector = _get_sector(symbol)
    knowledge = _get_knowledge(sector)
    notes = _get_notes(symbol, sector)
    sentiment, score = _score_sentiment(sector, action, reason, knowledge)
    support, details, verdict = _determine_fundamental_support(sector, action, score)

    # Override verdict for specific well-known cases
    if category == "etf" and "Gold" in sector and action == "SELL":
        verdict = "hold"
        support = "neutral"
        details = "Gold in uptrend; technical SELL likely temporary pullback"
    elif category == "etf" and "Debt" in sector:
        verdict = "hold"
        support = "neutral"
        details = "Debt ETFs are low-risk; technical signals less relevant"
    elif category == "large_cap" and sector in ("IT", "Banking") and action == "SELL":
        if score < 0.4:
            pass  # keep sell verdict
        else:
            verdict = "watch"
            support = "neutral"
            details += " | Consider buying on dips for quality sectors"

    return {
        "symbol": symbol,
        "technical_action": action,
        "category": category,
        "sentiment": sentiment,
        "sentiment_score": score,
        "key_news": notes,
        "fundamental_support": support,
        "fundamental_details": details,
        "overall_verdict": verdict,
        "verdict_reason": f"Technical: {action} ({reason}). Sector: {sector} ({knowledge.get('growth_outlook', 'unknown')} outlook). AI verdict: {verdict.upper()}.",
    }


def analyze_batch(signals: list[dict]) -> list[dict]:
    """Analyze multiple signals using AI knowledge (no external LLM)."""
    results = []
    total = len(signals)
    for i, sig in enumerate(signals):
        symbol = sig["symbol"]
        print(f"  Analyzing {symbol} ({i+1}/{total})...")
        result = analyze_signal(
            symbol=symbol,
            action=sig.get("action", "HOLD"),
            reason=sig.get("reason", ""),
            category=sig.get("category", ""),
        )
        results.append(result)
    return results


def load_scan_results(results_dir: str = "tests/temp/scan_results") -> list[dict]:
    """Load scan result JSONs and return only BUY/SELL signals."""
    path = Path(results_dir)
    if not path.exists():
        return []
    signals = []
    for f in sorted(path.iterdir()):
        if f.suffix != ".json":
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            if d.get("action") in ("BUY", "SELL"):
                signals.append(d)
        except Exception:
            pass
    return signals

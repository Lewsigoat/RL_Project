#!/usr/bin/env python3
"""Compile Lucas's Edexcel IGCSE EC2 notes into chapters.json + definitions.json.

Sources (Google Drive, owner's account):
- Copy of EoY EC2 Revision Chapters 1–42 Workbook
  id 1TggUdgA7ZJZxmzwhXAGHdeYbP6IqKzzL-MparcFnJSw
- EoY_EC2_Workbook_Answers
  id 1dFBgGZcf6srggyDTRBZIbisrEODQ21vhTrhBA36vSOk
- Chapter 28 4-mark savings ratio (viewed 2026-09-13)
  id 1_8muELqYaG9MIYxRQUg4lN7Cr4dwsrXVFZPTylk-Rjc
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src" / "data"
WORKBOOK = Path("/tmp/ec2_workbook.txt")
ANSWERS = Path("/tmp/ec2_answers.txt")

CHAPTER_META: dict[int, tuple[str, str]] = {
    1: ("The Market System — The Economic Problem", "Scarcity, opportunity cost, and the PPF/PPC."),
    2: ("The Market System — Economic Assumptions", "How consumers and firms are assumed to behave, and why they often do not."),
    3: ("Demand Curve", "Quantity consumers are willing and able to buy at different prices."),
    4: ("Factors that Shift Demand", "Income, substitutes, complements, advertising, and tastes."),
    5: ("Supply Curve", "Quantity producers are willing and able to sell at different prices."),
    6: ("Factors that Shift Supply", "Costs, taxes, subsidies, technology, and weather."),
    7: ("Market Equilibrium", "The price where quantity demanded equals quantity supplied."),
    8: ("Price Elasticity of Demand (PED)", "How quantity demanded responds to a change in price."),
    9: ("Price Elasticity of Supply (PES)", "How quantity supplied responds to a change in price."),
    10: ("Income Elasticity of Demand (YED)", "How demand responds to a change in income."),
    11: ("Mixed Economy & Market Failure", "When markets misallocate resources and why governments step in."),
    12: ("Privatisation", "Transferring ownership from the public sector to the private sector."),
    13: ("Externalities", "Third-party costs and benefits, social cost, and social benefit."),
    14: ("Factors of Production & Sectors of the Economy", "Labour, capital, enterprise, and the three sectors."),
    15: ("Productivity & Division of Labour", "Output per worker and splitting production into specialised tasks."),
    16: ("Business Costs, Revenue and Profit", "Total revenue, total cost, profit, and fixed versus variable cost."),
    17: ("Economies and Diseconomies of Scale", "Why average costs fall, then rise, as a firm grows."),
    18: ("Competitive Markets", "Many buyers and sellers, price takers, and low barriers to entry."),
    19: ("Large and Small Firms", "Why both sizes survive and when each has an advantage."),
    20: ("Monopoly", "A single dominant seller, barriers to entry, and price-making power."),
    21: ("Oligopoly", "A few large interdependent firms, and the risk of collusion."),
    22: ("The Labour Market — Demand and Supply", "Hiring, labour supply, and the equilibrium wage."),
    23: ("The Labour Market — Trade Unions", "Collective bargaining, wages, and employment."),
    24: ("Government Intervention", "Taxes, subsidies, the minimum wage, and regulation."),
    25: ("Economic Growth", "Real GDP, booms, recessions, and living standards."),
    26: ("Inflation", "Sustained price-level change, the CPI, and purchasing power."),
    27: ("Unemployment", "People willing and able to work who cannot find a job."),
    28: ("Balance of Payments (Current Account)", "Trade in goods and services and income flows."),
    29: ("Protection of the Environment", "Negative externalities from production and policy responses."),
    30: ("Redistribution of Income", "Taxes and benefits used to reduce inequality and poverty."),
    31: ("Fiscal Policy", "Government spending and taxation to influence the economy."),
    32: ("Monetary Policy", "Interest rates used to influence inflation and growth."),
    33: ("Supply-Side Policies", "Education, training, and deregulation to raise productive capacity."),
    34: ("Relationships Between Objectives and Policies", "Trade-offs between growth, inflation, unemployment, and the current account."),
    35: ("Globalisation", "Growing links between economies through trade, investment, and technology."),
    36: ("Multinational Companies and Foreign Direct Investment", "Firms that operate in more than one country, and the capital they bring."),
    37: ("International Trade", "Exports, imports, free trade, and comparative advantage."),
    38: ("Protectionism", "Tariffs, quotas, dumping, and infant-industry protection."),
    39: ("Trading Blocs", "Free trade areas, customs unions, trade creation, and trade diversion."),
    40: ("The World Trade Organization and World Trade Patterns", "WTO rules, disputes, and what countries export."),
    41: ("Exchange Rates and Their Determination", "The price of one currency in terms of another."),
    42: ("Impact of Changing Exchange Rates", "How appreciation and depreciation change trade, inflation, and growth."),
}

SPLIT_ASSIGN = {
    (3, 4): {
        "demand": 3,
        "substitute-good": 4,
        "complementary-good": 4,
    },
    (5, 6): {
        "supply": 5,
        "indirect-tax": 6,
        "subsidy": 6,
    },
    (22, 23): {
        "demand-for-labour": 22,
        "supply-of-labour": 22,
        "equilibrium-wage": 22,
        "trade-union": 23,
    },
}

ALIASES = {
    "ppf-ppc": ["PPF", "PPC", "production possibility frontier", "production possibility curve"],
    "ped": ["price elasticity of demand"],
    "pes": ["price elasticity of supply"],
    "yed": ["income elasticity of demand"],
    "gdp": ["gross domestic product"],
    "cpi": ["consumer price index"],
    "fdi": ["FDI"],
    "multinational-company": ["MNC", "multinational"],
    "world-trade-organization": ["WTO"],
    "mixed-economy": [],
    "benefit-utility": ["utility", "benefit"],
}

JUNK_NAMES = {
    "apply",
    "apply (use data from case)",
    "apply (use data)",
    "apply (use data from figure)",
    "answer",
    "chain",
    "chain 1",
    "chain 2",
    "chain 3",
    "chain 4",
    "complete these",
    "cost to us firm",
    "definition",
    "explain",
    "final answer",
    "link",
    "negative",
    "paragraph 1 point",
    "paragraph 2 point",
    "peal 1 point",
    "peal 1 point (choose one idea)",
    "peal 2 point",
    "peal 2 point (different idea)",
    "point",
    "point 1",
    "point 2",
    "positive",
    "possible benefit points",
    "possible point ideas",
    "possible points",
    "possible risks / limitations (for balance)",
    "question",
    "scaffold step 1",
    "show your workings",
    "step 1",
    "step 2",
    "evaluation 1 point",
    "evaluation 2 point",
    "additional case analysis",
    "other factor changes",
    "price change",
    "supply went from 20 to 45 when price rose from 15 to 35",
    "all production needs the four factors of production",
}

SKIP_TERM_NAMES = {
    "build chains of reasoning",
    "build chains",
    "chains of reasoning",
    "practice case",
    "practice case 1",
    "practice case 2",
    "fill-in definitions",
    "quick definitions to learn",
    "definitions",
    "key concepts and definitions",
    "in a nutshell",
    "key things you must know",
    "however",
    "evaluation 1",
    "evaluation 2",
    "evaluation",
    "possible points to use",
    "possible negative impact points",
    "possible positive / less negative points",
    "possible evaluation angles",
    "possible positive impact points",
    "possible limitations / negative points",
    "arguments for trading blocs",
    "arguments against trading blocs",
    "reasons for globalisation",
    "reasons for emergence of mncs and fdi",
    "reasons for protection",
    "advantages of free trade",
    "disadvantages of free trade",
    "advantages",
    "disadvantages",
    "impacts on different groups",
    "effects of appreciation",
    "effects of depreciation",
    "trade patterns",
    "factors affecting demand and supply of currencies",
    "important relationships",
    "macroeconomic objectives",
    "consumers",
    "producers",
    "workers",
    "governments",
    "environment",
}


def slug(text: str) -> str:
    cleaned = text.lower().replace("&", " and ").replace("/", " ")
    cleaned = re.sub(r"[^a-z0-9]+", "-", cleaned).strip("-")
    return cleaned


def clean_def(text: str) -> str:
    text = re.sub(r"[_\s]+", " ", text).strip(" .:")
    text = text.replace("tecnology", "technology")
    text = text.replace("quanity", "quantity")
    text = text.replace("Goverment", "Government")
    text = re.sub(r"\s+", " ", text)
    if text and not text.endswith("."):
        text += "."
    return text[0].upper() + text[1:] if text else text


def clean_term(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip(" *:-")
    text = text.replace(" / ", " / ")
    return text


def chapter_blocks(text: str) -> list[tuple[list[int], str, str]]:
    header = re.compile(
        r"^(?:Chapter|Chapters)\s+(\d+(?:\s*(?:&|and)\s*\d+)*)\s*:\s*(.+)$",
        re.I | re.M,
    )
    matches = list(header.finditer(text))
    blocks = []
    for i, match in enumerate(matches):
        nums = [int(n) for n in re.findall(r"\d+", match.group(1))]
        title = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        blocks.append((nums, title, text[start:end]))
    return blocks


def definition_windows(body: str) -> list[str]:
    """Keep only the definition-shaped slices of a chapter, not PEAL scaffolds."""
    starts = [
        "Quick definitions to learn",
        "Fill-in definitions",
        "Key concepts and definitions",
        "\nDefinitions\n",
    ]
    stops = (
        "Build chains",
        "Chains of reasoning",
        "Practice Case",
        "Possible ",
        "PEAL ",
        "However",
        "Evaluation",
        "Reasons for",
        "Advantages",
        "Disadvantages",
        "Impacts on",
        "Effects of",
        "Trade patterns",
        "Factors affecting",
        "Important relationships",
        "What is ",
        "Key things you must know",
        "In a nutshell",
    )
    windows = []
    for start in starts:
        idx = body.find(start)
        if idx < 0:
            continue
        chunk = body[idx + len(start) :]
        cut = len(chunk)
        for stop in stops:
            pos = chunk.find(stop)
            if pos >= 0:
                cut = min(cut, pos)
        windows.append(chunk[:cut])
    return windows


def parse_colon_defs(body: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for window in definition_windows(body):
        for match in re.finditer(r"^([A-Za-z][A-Za-z0-9 /()'&+-]{0,70}):\s+(\S.+)$", window, re.M):
            name, definition = clean_term(match.group(1)), match.group(2).strip()
            if name.lower() in SKIP_TERM_NAMES or name.lower() in JUNK_NAMES:
                continue
            if definition.startswith("_") or set(definition) <= {"_", " "}:
                continue
            found.append((name, clean_def(definition)))
        lines = window.splitlines()
        for i, line in enumerate(lines[:-1]):
            m = re.match(r"^([A-Za-z][A-Za-z0-9 /()'&+-]{0,70}):\s*$", line.strip())
            if not m:
                continue
            name = clean_term(m.group(1))
            nxt = lines[i + 1].strip()
            if name.lower() in SKIP_TERM_NAMES or name.lower() in JUNK_NAMES:
                continue
            if not nxt or nxt.startswith("_") or nxt.endswith(":"):
                continue
            found.append((name, clean_def(nxt)))
    return found


def parse_what_is(body: str) -> list[tuple[str, str]]:
    found = []
    lines = body.splitlines()
    for i, line in enumerate(lines[:-1]):
        m = re.match(r"^What is (?:the |a |an )?(.+?)\?\s*$", line.strip(), re.I)
        if not m:
            continue
        name = clean_term(m.group(1))
        nxt = lines[i + 1].strip()
        if nxt and not nxt.startswith("_") and not nxt.endswith("?"):
            found.append((name, clean_def(nxt)))
    return found


def parse_equals_bullets(body: str) -> list[tuple[str, str]]:
    found = []
    for match in re.finditer(r"^\*?\s*([A-Za-z][A-Za-z0-9 /()'&+-]{0,60})\s*=\s+(.+)$", body, re.M):
        name, definition = clean_term(match.group(1)), clean_def(match.group(2))
        if len(definition) < 40:
            continue
        found.append((name, definition))
    return found


def nutshell(body: str) -> str:
    m = re.search(r"In a nutshell\n(.+?)(?:\nKey |\nQuick |\nFill-in |\nWhat is |\nBuild |\nChapter)", body, re.S)
    if not m:
        return ""
    return re.sub(r"\s+", " ", m.group(1)).strip()


def first_apply(body: str) -> str | None:
    matches = re.findall(r"^Apply:\s+(.+)$", body, re.M)
    for item in matches:
        text = item.strip()
        if text and not text.startswith("_") and len(text) > 20:
            return text.rstrip(".") + "."
    return None


def assign_chapter(nums: list[int], term_id: str) -> int:
    if len(nums) == 1:
        return nums[0]
    key = (min(nums), max(nums))
    mapping = SPLIT_ASSIGN.get(key, {})
    if term_id in mapping:
        return mapping[term_id]
    # default: first chapter of the pair unless the name hints otherwise
    lowered = term_id
    if any(token in lowered for token in ("union", "bargain")):
        return max(nums)
    if any(token in lowered for token in ("shift", "substitute", "complement", "tax", "subsidy")):
        return max(nums)
    return min(nums)


def add_term(terms: dict[str, dict], chapter: int, name: str, definition: str, example: str | None = None, aliases: list[str] | None = None) -> None:
    if not name or not definition or len(definition) < 12:
        return
    lowered = name.lower()
    if lowered in SKIP_TERM_NAMES or lowered in JUNK_NAMES:
        return
    if re.match(r"^(peal|apply|explain|link|definition|question|chain|step|point)(\s+\d+)?$", lowered):
        return
    term_id = slug(name)
    if not term_id:
        return
    if term_id in terms and terms[term_id]["chapterId"] != f"ch{chapter}":
        term_id = f"{term_id}-ch{chapter}"
    if term_id in terms:
        # Prefer the longer student-answer wording
        if len(definition) <= len(terms[term_id]["definition"]):
            return
    payload = {
        "id": term_id,
        "chapterId": f"ch{chapter}",
        "term": name[0].upper() + name[1:] if name else name,
        "definition": definition,
    }
    if example:
        payload["example"] = example
    extra_aliases = list(ALIASES.get(slug(name), []))
    if aliases:
        extra_aliases.extend(aliases)
    if extra_aliases:
        payload["aliases"] = sorted(set(extra_aliases))
    terms[term_id] = payload


def extras() -> list[tuple[int, str, str, str | None, list[str]]]:
    """HIS wording for thin later chapters + the savings-ratio note viewed today."""
    return [
        (1, "Point on the PPC", "A point on the PPC means resources are fully employed.", None, ["point on PPC"]),
        (1, "Point inside the PPC", "A point inside the PPC means resources are unemployed or underused.", None, ["point inside PPC"]),
        (1, "Point outside the PPC", "A point outside the PPC is unobtainable with current resources.", None, ["point outside PPC"]),
        (1, "Outward shift of the PPF", "An outward shift shows positive economic growth / a rise in productive capacity.", None, []),
        (1, "Inward shift of the PPF", "An inward shift shows a fall in productive capacity.", None, []),
        (3, "Movement along the demand curve", "A change in price causes a movement along the demand curve, not a shift.", "If cocoa bean prices fell from $3000 to $2000 per tonne, quantity demanded might rise from 1000 to 1500 tonnes.", []),
        (3, "Demand curve", "The demand curve shows the relationship between price and quantity demanded. An increase in demand shifts the curve right.", None, []),
        (4, "Advertising", "Advertising raises awareness so more consumers know about a product and demand increases.", "Pepsi advertising during the Cricket World Cup raises brand awareness and shifts demand right.", []),
        (4, "Income", "When income rises, purchasing power increases, consumers can afford more, and demand for normal goods rises.", None, []),
        (8, "Price inelastic demand", "Price inelastic demand means PED is less than 1, so quantity changes proportionally less than price.", "Petrol is essential for many commuters, so demand changes little when price rises.", ["inelastic demand"]),
        (8, "Price elastic demand", "Demand is price elastic when PED is greater than 1, so a price rise cuts quantity demanded significantly and total revenue falls.", None, ["elastic demand"]),
        (9, "Price inelastic supply", "Price inelastic supply means PES is less than 1. Fresh fish spoils quickly and cannot be stored for long, so supply cannot rise quickly.", None, ["inelastic supply"]),
        (15, "Productivity", "The efficiency with which inputs are converted into outputs.", None, []),
        (17, "Economies of scale", "When average costs fall as a firm increases its output.", "Apple designs its own chips and software, giving huge technical advantages at scale.", []),
        (27, "Unemployment", "People of working age who are willing and able to work but cannot find a job.", "In South Africa, youth unemployment is especially severe, limiting future opportunities.", []),
        (28, "Imports", "Goods and services bought from other countries. When imports exceed exports there is a current account deficit.", None, []),
        (6, "Production costs", "If costs rise, profit per unit falls, producers are less willing to sell, quantity supplied falls at each price, and supply falls.", None, []),
        (6, "Technology (supply)", "If technology improves, output per worker rises, costs fall, more can be produced at each price, and supply rises.", None, ["technology"]),
        (10, "Normal good", "A good with positive YED: when income rises, demand rises.", "YED = 15% / 20% = 0.75. This is a normal good because YED is positive, and it is a necessity because YED is less than 1.", []),
        (10, "Inferior good", "A good with negative YED: when income rises, consumers switch to better alternatives and demand for the inferior good falls.", None, []),
        (11, "Private sector", "Owned by individuals / businesses.", None, []),
        (11, "Public sector", "Owned or funded by government.", None, []),
        (23, "Collective bargaining", "Trade unions use collective bargaining power to negotiate higher wages; employers must agree or face strikes.", "In the US textile industry, a large union can negotiate better terms for workers.", []),
        (5, "Movement along the supply curve", "A change in price causes a movement along the supply curve, not a shift.", "If wheat prices rose from $200 to $250 per tonne, farmers would supply more wheat.", []),
        (7, "Shortage", "A shortage is excess demand: consumers cannot buy all they want at the current price.", None, ["excess demand"]),
        (7, "Surplus", "A surplus is excess supply: unsold stock builds up at the current price.", None, ["excess supply"]),
        (29, "Negative externality", "A cost to third parties not involved in the activity.", "Production increases, more factories operate, emissions rise, pollution rises, and social costs rise.", []),
        (29, "Carbon tax", "A tax that raises the cost of polluting so firms seek cleaner alternatives and pollution falls.", None, []),
        (29, "Regulation", "Government sets limits; firms must comply or face fines, so harmful activity decreases.", None, []),
        (30, "Progressive tax", "Higher earners pay a larger share, government revenue rises, income is redistributed, and inequality falls.", None, []),
        (30, "Benefits", "Low-income households receive support, purchasing power rises, and poverty falls.", None, []),
        (30, "Income inequality", "An uneven distribution of income across households, which governments try to reduce by redistributing income.", None, []),
        (31, "Fiscal policy", "Fiscal policy uses government spending and taxation to influence economic activity.", "The Slovenian government spent €3.05bn on healthcare in 2019, including extra funding to cut waiting times.", []),
        (31, "Budget deficit", "When government spending is greater than tax revenue.", None, []),
        (31, "Budget surplus", "When tax revenue is greater than government spending.", None, []),
        (31, "Disposable income", "Income households keep after taxes, which rises when taxes fall and can raise consumption.", None, []),
        (
            31,
            "Savings ratio",
            "The proportion of household disposable income that is saved rather than spent. It is usually expressed as saving as a percentage of disposable income.",
            "Between January 2015 and July 2017, the UK savings ratio followed a downward overall trend, so households were saving a smaller share of their income by the end of the period.",
            ["saving ratio"],
        ),
        (32, "Monetary policy", "Monetary policy controls interest rates to influence inflation and economic growth.", "China's central bank brought interest rates down to 4.35% when growth was slowing.", []),
        (32, "Central bank", "The institution that sets interest rates to control inflation.", None, []),
        (32, "Interest rates", "The cost of borrowing money or the return on saving.", "If interest rates rise, borrowing becomes more expensive, mortgages and loans cost more, consumption falls, and inflation falls.", []),
        (32, "Aggregate demand", "Total demand in the economy. Lower interest rates can raise borrowing and spending, so aggregate demand rises.", None, ["AD"]),
        (33, "Supply-side policies", "Policies that aim to increase productivity and long-run economic growth.", "Ecuador claimed a 5.8% unemployment rate in October 2017 was the result of supply-side policies.", []),
        (33, "Deregulation", "Fewer rules to follow, so firms save time and money and efficiency rises.", None, []),
        (33, "Education and training", "Workers gain skills, productivity per worker rises, firms produce more, and output increases.", None, []),
        (34, "Trade-off", "When achieving one objective makes it harder to achieve another.", "When unemployment falls, firms compete more for workers, wages rise, costs rise, and inflation may increase.", []),
        (36, "Host country", "The country receiving the investment.", None, []),
        (36, "Job creation from FDI", "An MNC enters a country, a factory is built, jobs are created, household incomes rise, and consumer spending rises.", None, []),
        (36, "Profit repatriation", "Profits sent back to the company's home country.", None, []),
        (39, "Trading bloc", "A group of countries that agree to reduce or remove trade barriers between themselves.", "Switzerland trading with EU neighbours without tariffs benefits consumers.", []),
        (39, "Free trade area", "A group of countries with no tariffs between members.", None, []),
        (39, "Customs union", "A trading bloc with free trade between members and a common external tariff.", None, []),
        (39, "Trade creation", "When lower trade barriers allow countries to buy from lower-cost producers inside the bloc.", None, []),
        (39, "Trade diversion", "When trade shifts from a more efficient outside producer to a less efficient member country.", None, []),
        (40, "World Trade Organization", "An international organisation that promotes freer trade and resolves trade disputes.", None, ["WTO"]),
        (40, "Trade dispute", "A disagreement between countries over trade rules or restrictions.", None, []),
        (40, "Primary product", "A raw material or natural product, such as coffee, oil, or copper.", None, []),
        (40, "Manufactured good", "A product that has been processed or made in factories.", None, []),
        (41, "Exchange rate", "The price of one currency in terms of another currency.", None, []),
        (41, "Appreciation", "An increase in the value of a currency.", None, []),
        (41, "Depreciation", "A decrease in the value of a currency. Depreciation means a fall in the value of the currency.", "A weaker euro made German cars and machinery cheaper for foreign buyers and helped Germany's current account surplus.", []),
        (41, "Demand for a currency", "The desire to buy a currency, usually to buy that country's exports or invest there.", None, []),
        (41, "Supply of a currency", "The amount of a currency being sold, usually to buy imports or invest abroad.", None, []),
        (42, "Revaluation", "An official increase in the value of a currency in a fixed exchange rate system.", None, []),
        (42, "Devaluation", "An official decrease in the value of a currency in a fixed exchange rate system.", None, []),
    ]


def related_for(term: dict, by_chapter: dict[str, list[str]], by_id: dict[str, dict]) -> list[str]:
    own = term["id"]
    same = [tid for tid in by_chapter[term["chapterId"]] if tid != own]
    # keep a few same-chapter links plus obvious name overlaps
    related = same[:6]
    tokens = set(slug(term["term"]).split("-"))
    for other_id, other in by_id.items():
        if other_id == own or other_id in related:
            continue
        other_tokens = set(slug(other["term"]).split("-"))
        if tokens & other_tokens and len(tokens & other_tokens) >= 1 and other["chapterId"] != term["chapterId"]:
            if any(tok in tokens and tok in other_tokens for tok in ("demand", "supply", "inflation", "unemployment", "trade", "tax", "wage", "export", "import", "currency")):
                related.append(other_id)
        if len(related) >= 8:
            break
    return related[:8]


def compile_catalog() -> tuple[list[dict], list[dict]]:
    workbook = WORKBOOK.read_text()
    answers = ANSWERS.read_text()
    terms: dict[str, dict] = {}
    summaries: dict[int, str] = {}
    for nums, _title, body in chapter_blocks(workbook):
        note = nutshell(body)
        for num in nums:
            if num not in CHAPTER_META:
                continue
            summaries[num] = note if len(nums) == 1 and note else CHAPTER_META[num][1]

    for nums, _title, body in chapter_blocks(answers) + chapter_blocks(workbook):
        example = first_apply(body)
        pairs = parse_colon_defs(body) + parse_what_is(body) + parse_equals_bullets(body)
        for name, definition in pairs:
            chapter = assign_chapter(nums, slug(name))
            if chapter not in CHAPTER_META:
                chapter = nums[0]
            add_term(terms, chapter, name, definition, example if slug(name) in {"scarcity", "demand", "supply", "ped", "inflation"} else None)

    for chapter, name, definition, example, aliases in extras():
        add_term(terms, chapter, name, definition, example, aliases)

    # Attach a few HIS examples to core terms
    examples = {
        "opportunity-cost": "The opportunity cost of producing an additional 100 units of capital goods is 200 units of consumer goods.",
        "ped": "People driving to work every day keep buying petrol, so PED for petrol is inelastic.",
        "privatisation": "Austrian Railways may face new competitors after privatisation.",
        "monopoly": "The merged Vodafone-Idea company would have 40% market share and 400 million customers.",
        "unemployment": "In South Africa, youth unemployment is especially severe, limiting future opportunities.",
        "current-account": "Indonesia's deficit reached 3% of GDP, putting pressure on the rupiah.",
        "globalisation": "More production and transport may increase pollution.",
        "protectionism": "Steel tariffs can save jobs in domestic steel mills.",
        "free-trade": "The TPP would have reduced tariffs across Pacific economies, making goods cheaper.",
    }
    for tid, example in examples.items():
        if tid in terms and "example" not in terms[tid]:
            terms[tid]["example"] = example

    # Drop scaffold leftovers and near-duplicate flashcards in the same chapter.
    drop_ids = []
    for term in list(terms.values()):
        if term["term"].lower() in JUNK_NAMES or term["id"] in JUNK_NAMES:
            drop_ids.append(term["id"])
    for tid in drop_ids:
        terms.pop(tid, None)

    grouped: dict[str, list[dict]] = defaultdict(list)
    for term in terms.values():
        grouped[term["chapterId"]].append(term)
    for chapter_terms in grouped.values():
        for first in chapter_terms:
            for second in chapter_terms:
                if first["id"] >= second["id"]:
                    continue
                a = re.sub(r"\b(the|a|an|of)\b", " ", first["term"].lower())
                b = re.sub(r"\b(the|a|an|of)\b", " ", second["term"].lower())
                a, b = re.sub(r"\s+", " ", a).strip(), re.sub(r"\s+", " ", b).strip()
                if a == b:
                    keep, drop = (first, second) if len(first["definition"]) >= len(second["definition"]) else (second, first)
                    if drop["id"] in terms and keep["id"] in terms:
                        terms.pop(drop["id"], None)

    by_chapter: dict[str, list[str]] = defaultdict(list)
    for term in terms.values():
        by_chapter[term["chapterId"]].append(term["id"])
    for term in terms.values():
        related = related_for(term, by_chapter, terms)
        if related:
            term["related"] = related

    chapters = []
    for number, (title, fallback) in CHAPTER_META.items():
        chapters.append(
            {
                "id": f"ch{number}",
                "number": number,
                "title": title,
                "summary": summaries.get(number) or fallback,
            }
        )

    ordered = sorted(terms.values(), key=lambda t: (int(t["chapterId"][2:]), t["term"].lower()))
    return chapters, ordered


def main() -> None:
    if not WORKBOOK.exists() or not ANSWERS.exists():
        raise SystemExit(f"Missing source files: {WORKBOOK} {ANSWERS}")
    chapters, terms = compile_catalog()
    empty = [ch["id"] for ch in chapters if not any(t["chapterId"] == ch["id"] for t in terms)]
    if empty:
        raise SystemExit(f"Chapters with no terms: {empty}")
    (DATA / "chapters.json").write_text(json.dumps(chapters, indent=2) + "\n")
    (DATA / "definitions.json").write_text(json.dumps(terms, indent=2) + "\n")
    counts = defaultdict(int)
    for term in terms:
        counts[term["chapterId"]] += 1
    print(f"Wrote {len(chapters)} chapters and {len(terms)} terms")
    for chapter in chapters:
        print(f"  {chapter['id']:>4} {counts[chapter['id']]:2d}  {chapter['title']}")


if __name__ == "__main__":
    main()

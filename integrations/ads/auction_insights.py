"""Google Ads Auction Insights, imported from the CSV Google exports.

Auction Insights is the only place a competitor's position against your own ads
is reported by Google itself rather than estimated by a third party. It has no
API -- Google serves it in the Ads UI only -- so the report is exported by hand
and parsed here.

What it does and does not contain is worth stating, because the surrounding
agents previously invented both: it names the domains that competed in the same
auctions and how often each appeared, and it says nothing whatsoever about a
competitor's clicks, spend or budget. Those are private to the advertiser. Any
figure claiming otherwise is a model's guess.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("auction_insights")

# Google labels this column differently depending on the report level; any of
# these marks the real header row, below the export's title and date preamble.
DOMAIN_HEADERS = ("display url domain", "domain", "display url")

# The metric columns Google exports. Everything else in the row is kept as-is.
METRIC_COLUMNS = {
    "impression share": "impression_share",
    "impr. share": "impression_share",
    "search impr. share": "impression_share",
    "overlap rate": "overlap_rate",
    "position above rate": "position_above_rate",
    "top of page rate": "top_of_page_rate",
    "abs. top of page rate": "abs_top_of_page_rate",
    "outranking share": "outranking_share",
}


def _percent(raw: Any) -> Optional[float]:
    """A percentage cell as a number, or None when Google did not give one.

    Google writes "< 10%" when a figure is too small to disclose and "--" when
    there is none. Both are answers, and neither is zero -- reading them as 0
    would report a competitor as absent when Google only declined to say.
    """
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text in ("--", "-", "—"):
        return None
    match = re.search(r"(\d+(?:\.\d+)?)", text.replace(",", ""))
    if not match:
        return None
    return round(float(match.group(1)), 2)


def _bound(raw: Any) -> Optional[str]:
    """Whether the figure was disclosed exactly, or only as a bound."""
    text = str(raw or "").strip()
    if text.startswith("<"):
        return "less_than"
    if text.startswith(">"):
        return "greater_than"
    if text in ("--", "-", "—", ""):
        return "not_reported"
    return None


def parse_auction_insights(csv_text: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Optional[str]]:
    """Parse an exported Auction Insights CSV.

    Returns (rows, meta, error). An error means nothing was parsed; it is never
    paired with partial rows presented as if the file had been read.
    """
    if not csv_text or not csv_text.strip():
        return [], {}, "The uploaded file is empty."

    # Google exports UTF-16 with a BOM from some browsers; callers decode, but
    # a stray BOM still reaches us.
    csv_text = csv_text.lstrip("﻿")
    delimiter = "\t" if csv_text.count("\t") > csv_text.count(",") else ","

    try:
        all_rows = list(csv.reader(io.StringIO(csv_text), delimiter=delimiter))
    except Exception as e:
        return [], {}, f"The file could not be read as CSV: {e}"

    header_index = None
    for index, row in enumerate(all_rows[:25]):
        cells = [str(c).strip().lower() for c in row]
        if any(cell in DOMAIN_HEADERS for cell in cells):
            header_index = index
            break

    if header_index is None:
        return [], {}, (
            "No 'Display URL domain' column was found. This does not look like a Google Ads "
            "Auction Insights export -- download it from Google Ads with the Download button "
            "above the auction insights table."
        )

    # The lines above the header carry the report title and its date range. The
    # date is read from the raw text rather than the parsed cells, because the
    # CSV reader splits "Aug 16, 2026" on its own comma and rejoining the cells
    # loses it.
    preamble_text = csv_text.split(chr(10))[:header_index]
    preamble = " ".join(preamble_text)
    date_range = None
    day = r"([A-Z][a-z]{2}\.?\s+\d{1,2},?\s*\d{4})"
    date_match = re.search(day + r"\s*(?:[-–]|to)\s*" + day, preamble)
    if date_match:
        date_range = f"{date_match.group(1).strip()} - {date_match.group(2).strip()}"

    header = [str(c).strip() for c in all_rows[header_index]]
    lowered = [h.lower() for h in header]
    domain_col = next(i for i, h in enumerate(lowered) if h in DOMAIN_HEADERS)

    rows: List[Dict[str, Any]] = []
    for raw_row in all_rows[header_index + 1:]:
        if not raw_row or len(raw_row) <= domain_col:
            continue
        domain = str(raw_row[domain_col]).strip()
        if not domain:
            continue
        # Google appends a totals line to some exports.
        if domain.lower().startswith("total"):
            continue

        entry: Dict[str, Any] = {
            "domain": domain,
            # Google names the advertiser's own row "You".
            "is_you": domain.strip().lower() == "you",
            "metrics": {},
            "bounds": {},
        }
        for col_index, column_name in enumerate(lowered):
            if col_index == domain_col or col_index >= len(raw_row):
                continue
            key = METRIC_COLUMNS.get(column_name)
            if not key:
                continue
            entry["metrics"][key] = _percent(raw_row[col_index])
            bound = _bound(raw_row[col_index])
            if bound:
                entry["bounds"][key] = bound
        rows.append(entry)

    if not rows:
        return [], {}, "The header was found but the file contained no competitor rows."

    meta = {
        "date_range": date_range,
        "columns": [h for h in header if h],
        "row_count": len(rows),
        "source": "Google Ads Auction Insights export",
        "contains_click_or_spend_data": False,
        "note": (
            "Auction Insights reports how often each domain appeared in the same auctions as "
            "you. It contains no click counts, budgets or spend for any competitor -- Google "
            "does not publish those to anyone but the advertiser."
        ),
    }
    return rows, meta, None


def _store_path(data_dir: Path, site_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]", "", site_id) or "ccm"
    return Path(data_dir) / f"auction_insights_{safe}.json"


def save_auction_insights(data_dir: Path, site_id: str, rows: List[Dict[str, Any]],
                          meta: Dict[str, Any], filename: str) -> Dict[str, Any]:
    """Persist one import, replacing whatever was stored for this site."""
    payload = {
        "site_id": site_id,
        "imported_at": datetime.now().isoformat(timespec="seconds"),
        "source_filename": filename,
        "meta": meta,
        "rows": rows,
    }
    path = _store_path(data_dir, site_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return payload


def load_auction_insights(data_dir: Path, site_id: str) -> Optional[Dict[str, Any]]:
    """The stored import for this site, or None when nothing was ever imported."""
    path = _store_path(data_dir, site_id)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Could not read stored auction insights for %s: %s", site_id, e)
        return None


def delete_auction_insights(data_dir: Path, site_id: str) -> bool:
    """Remove a stored import. Returns whether there was one to remove."""
    path = _store_path(data_dir, site_id)
    if not path.exists():
        return False
    path.unlink()
    return True


def summarise_rivals(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Who competed most often, and how you placed against them."""
    you = next((r for r in rows if r["is_you"]), None)
    rivals = [r for r in rows if not r["is_you"]]

    def share(entry: Dict[str, Any]) -> float:
        return entry["metrics"].get("impression_share") or 0.0

    ranked = sorted(rivals, key=share, reverse=True)
    outranking_you = [
        r for r in rivals
        if (r["metrics"].get("position_above_rate") or 0) > 50
    ]

    return {
        "your_impression_share": you["metrics"].get("impression_share") if you else None,
        "your_top_of_page_rate": you["metrics"].get("top_of_page_rate") if you else None,
        "rival_count": len(rivals),
        "top_rivals": ranked[:10],
        "rivals_usually_above_you": [r["domain"] for r in outranking_you],
    }

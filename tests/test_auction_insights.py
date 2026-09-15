"""Tests for the Google Ads Auction Insights CSV import."""

import tempfile
import unittest
from pathlib import Path

from integrations.ads.auction_insights import (
    delete_auction_insights,
    load_auction_insights,
    parse_auction_insights,
    save_auction_insights,
    summarise_rivals,
)

EXPORT = (
    "Auction insights report (Aug 16, 2026 - Sep 14, 2026)\n"
    "Campaign: 10_sept_ads_campaign\n"
    "\n"
    "Display URL domain,Impression share,Overlap rate,Position above rate,"
    "Top of page rate,Abs. Top of page rate,Outranking share\n"
    "You,42.15%,--,--,68.20%,12.40%,--\n"
    "melbournecorporatecars.com.au,61.30%,55.10%,72.80%,81.05%,24.60%,38.70%\n"
    "ontimevhacars.com.au,< 10%,14.20%,31.50%,55.00%,8.10%,71.30%\n"
    "888cars.com.au,18.90%,22.40%,49.90%,60.15%,10.05%,52.10%\n"
    "Total: Search,100.00%,--,--,--,--,--\n"
)


class TestAuctionInsightsParsing(unittest.TestCase):
    def test_parses_a_real_export_shape(self):
        rows, meta, error = parse_auction_insights(EXPORT)
        self.assertIsNone(error)
        self.assertEqual(meta["date_range"], "Aug 16, 2026 - Sep 14, 2026")
        # The totals line is not a competitor.
        self.assertEqual(len(rows), 4)
        self.assertNotIn("total", " ".join(r["domain"].lower() for r in rows))

    def test_marks_the_advertisers_own_row(self):
        rows, _, _ = parse_auction_insights(EXPORT)
        mine = [r for r in rows if r["is_you"]]
        self.assertEqual(len(mine), 1)
        self.assertEqual(mine[0]["metrics"]["impression_share"], 42.15)

    def test_undisclosed_figures_are_not_read_as_zero(self):
        """Google writes "< 10%" when a figure is too small to disclose and "--"
        when there is none. Reading either as 0 would report a competitor as
        absent when Google only declined to say."""
        rows, _, _ = parse_auction_insights(EXPORT)
        bounded = next(r for r in rows if r["domain"] == "ontimevhacars.com.au")
        self.assertEqual(bounded["metrics"]["impression_share"], 10.0)
        self.assertEqual(bounded["bounds"]["impression_share"], "less_than")

        mine = next(r for r in rows if r["is_you"])
        self.assertIsNone(mine["metrics"]["overlap_rate"])
        self.assertEqual(mine["bounds"]["overlap_rate"], "not_reported")

    def test_declares_that_it_holds_no_click_or_spend_data(self):
        """The agents this feeds used to publish competitor click counts and
        monthly spend. Auction Insights contains neither, and says so."""
        _, meta, _ = parse_auction_insights(EXPORT)
        self.assertFalse(meta["contains_click_or_spend_data"])

    def test_rejects_a_file_that_is_not_an_export(self):
        rows, _, error = parse_auction_insights("date,clicks\n2026-01-01,5\n")
        self.assertEqual(rows, [])
        self.assertIn("Display URL domain", error)

    def test_rejects_an_empty_file(self):
        rows, _, error = parse_auction_insights("")
        self.assertEqual(rows, [])
        self.assertTrue(error)

    def test_reads_a_tab_separated_export(self):
        rows, _, error = parse_auction_insights(EXPORT.replace(",", "\t"))
        self.assertIsNone(error)
        self.assertEqual(len(rows), 4)


class TestAuctionInsightsSummary(unittest.TestCase):
    def test_names_the_rivals_that_usually_outrank_you(self):
        rows, _, _ = parse_auction_insights(EXPORT)
        summary = summarise_rivals(rows)
        self.assertEqual(summary["your_impression_share"], 42.15)
        self.assertEqual(summary["rival_count"], 3)
        self.assertEqual(
            summary["rivals_usually_above_you"], ["melbournecorporatecars.com.au"]
        )

    def test_ranks_rivals_by_impression_share(self):
        rows, _, _ = parse_auction_insights(EXPORT)
        summary = summarise_rivals(rows)
        self.assertEqual(
            summary["top_rivals"][0]["domain"], "melbournecorporatecars.com.au"
        )


class TestAuctionInsightsStorage(unittest.TestCase):
    def test_saves_loads_and_deletes_per_site(self):
        rows, meta, _ = parse_auction_insights(EXPORT)
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            self.assertIsNone(load_auction_insights(data_dir, "ccm"))

            save_auction_insights(data_dir, "ccm", rows, meta, "export.csv")
            stored = load_auction_insights(data_dir, "ccm")
            self.assertEqual(len(stored["rows"]), 4)
            self.assertEqual(stored["source_filename"], "export.csv")

            # One site's import must not answer for another.
            self.assertIsNone(load_auction_insights(data_dir, "opal"))

            self.assertTrue(delete_auction_insights(data_dir, "ccm"))
            self.assertIsNone(load_auction_insights(data_dir, "ccm"))
            self.assertFalse(delete_auction_insights(data_dir, "ccm"))


if __name__ == "__main__":
    unittest.main()

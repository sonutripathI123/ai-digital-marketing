"""Ads integrations package."""
from integrations.ads.base import BaseAdsAdapter
from integrations.ads.google_ads import GoogleAdsAdapter
from integrations.ads.meta_ads import MetaAdsAdapter

__all__ = ["BaseAdsAdapter", "GoogleAdsAdapter", "MetaAdsAdapter"]

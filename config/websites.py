"""
Central Multi-Website Registry and Profile Management.

Maintains multi-tenant website profiles, credentials prefixes, target locations,
and analytics properties for all managed chauffeur brands.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from config.settings import LOGS_DIR, ROOT_DIR


class WebsiteProfile(BaseModel):
    site_id: str = Field(..., description="Unique slug for the website, e.g. 'ccm', 'opal', 'sydney-cars'")
    name: str = Field(..., description="Full Brand / Website Name")
    domain: str = Field(..., description="Base domain URL including https://")
    location: str = Field(default="Melbourne, VIC", description="Primary operating location")
    niche: str = Field(default="Luxury Chauffeur & Executive Transfers", description="Core business niche")
    default_category: str = Field(default="Chauffeur Services", description="Default WordPress category")
    gsc_site_url: Optional[str] = None
    ga4_property_id: Optional[str] = None
    google_ads_id: Optional[str] = None
    meta_ads_id: Optional[str] = None
    facebook_url: Optional[str] = None
    instagram_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    is_active: bool = True
    color_accent: str = "#06b6d4"  # Hex color for UI branding badge


DEFAULT_WEBSITES: List[WebsiteProfile] = [
    WebsiteProfile(
        site_id="ccm",
        name="Corporate Cars Melbourne",
        domain="https://corporatecarsmelbourne.com.au",
        location="Melbourne & Tullamarine, VIC",
        niche="Executive Airport Transfers & Corporate Chauffeur",
        default_category="Chauffeur Services",
        gsc_site_url="https://corporatecarsmelbourne.com.au",
        ga4_property_id="corporate-cars-melbourne-ga4",
        google_ads_id="ccm-gads-482",
        meta_ads_id="ccm-meta-891",
        facebook_url="https://facebook.com/corporatecarsmelbourne",
        instagram_url="https://instagram.com/corporatecarsmelbourne",
        linkedin_url="https://linkedin.com/company/corporatecarsmelbourne",
        is_active=True,
        color_accent="#06b6d4"
    ),
    WebsiteProfile(
        site_id="opal",
        name="Opal Chauffeurs",
        domain="https://www.opalchauffeurs.com.au",
        location="Melbourne Metropolitan & Regional VIC",
        niche="Luxury Private Driver & Premium Chauffeur Cars",
        default_category="Airport Transfers",
        gsc_site_url="https://www.opalchauffeurs.com.au",
        ga4_property_id="opal-chauffeurs-ga4",
        google_ads_id="opal-gads-104",
        meta_ads_id="opal-meta-552",
        facebook_url="https://facebook.com/opalchauffeurs",
        instagram_url="https://instagram.com/opalchauffeurs",
        linkedin_url="https://linkedin.com/company/opalchauffeurs",
        is_active=True,
        color_accent="#a855f7"
    )
]


class WebsiteManager:
    """Manages persistent registry of websites with multi-tenant isolation."""

    def __init__(self, storage_file: Optional[Path] = None):
        self.storage_file = storage_file or (LOGS_DIR / "websites_registry.json")
        self._websites: Dict[str, WebsiteProfile] = {}
        self._load_or_initialize()

    def _load_or_initialize(self) -> None:
        if self.storage_file.exists():
            try:
                with open(self.storage_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        profile = WebsiteProfile.model_validate(item)
                        self._websites[profile.site_id] = profile
                if self._websites:
                    return
            except Exception:
                pass

        # Seed with default pre-configured websites
        for site in DEFAULT_WEBSITES:
            self._websites[site.site_id] = site
        self._save_to_disk()

    def _save_to_disk(self) -> None:
        try:
            self.storage_file.parent.mkdir(parents=True, exist_ok=True)
            data = [w.model_dump() for w in self._websites.values()]
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def list_all(self, active_only: bool = False) -> List[WebsiteProfile]:
        sites = list(self._websites.values())
        if active_only:
            sites = [s for s in sites if s.is_active]
        return sites

    def get(self, site_id: str) -> Optional[WebsiteProfile]:
        return self._websites.get(site_id)

    def add_website(self, profile: WebsiteProfile) -> WebsiteProfile:
        self._websites[profile.site_id] = profile
        self._save_to_disk()
        return profile

    def update_website(self, site_id: str, updates: Dict[str, any]) -> Optional[WebsiteProfile]:
        profile = self._websites.get(site_id)
        if not profile:
            return None
        data = profile.model_dump()
        data.update(updates)
        updated_profile = WebsiteProfile.model_validate(data)
        self._websites[site_id] = updated_profile
        self._save_to_disk()
        return updated_profile

    def delete_website(self, site_id: str) -> bool:
        if site_id in self._websites:
            del self._websites[site_id]
            self._save_to_disk()
            return True
        return False

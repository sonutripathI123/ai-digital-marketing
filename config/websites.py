"""
Central Multi-Website Registry and Profile Management.

Maintains multi-tenant website profiles, credentials prefixes, target locations,
and analytics properties for all managed chauffeur brands.
"""

import json
import secrets
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
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
    owner_email: Optional[str] = "sonutripathi9305@gmail.com"
    assigned_client_emails: List[str] = Field(default_factory=list, description="Client emails allowed to manage this site")
    invite_token: Optional[str] = Field(default=None, description="Active secure invite token for client onboarding")
    created_at: Optional[str] = Field(default=None, description="ISO registration timestamp")
    agent_credentials: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="Agent API keys and connection parameters")


DEFAULT_WEBSITES: List[WebsiteProfile] = [
    WebsiteProfile(
        site_id="ccm",
        name="Corporate Cars Melbourne",
        domain="https://corporatecarsmelbourne.com.au",
        location="Melbourne & Tullamarine, VIC",
        niche="Executive Airport Transfers & Corporate Chauffeur",
        default_category="Chauffeur Services",
        gsc_site_url="https://corporatecarsmelbourne.com.au",
        ga4_property_id="550393874",
        google_ads_id="ccm-gads-482",
        meta_ads_id="ccm-meta-891",
        facebook_url="https://facebook.com/corporatecarsmelbourne",
        instagram_url="https://instagram.com/corporatecarsmelbourne",
        linkedin_url="https://linkedin.com/company/corporatecarsmelbourne",
        is_active=True,
        color_accent="#06b6d4",
        owner_email="sonutripathi9305@gmail.com",
        assigned_client_emails=[],
        invite_token="inv_ccm_master_2026",
        created_at="2026-08-01T00:00:00"
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
        color_accent="#a855f7",
        owner_email="sonutripathi9305@gmail.com",
        assigned_client_emails=[],
        invite_token="inv_opal_master_2026",
        created_at="2026-08-15T00:00:00"
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
                        # Ensure default invite token exists if missing
                        if not profile.invite_token:
                            profile.invite_token = f"inv_{profile.site_id}_{secrets.token_hex(4)}"
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
        if not profile.invite_token:
            profile.invite_token = f"inv_{profile.site_id}_{secrets.token_hex(4)}"
        if not profile.created_at:
            profile.created_at = datetime.utcnow().isoformat()
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

    def allot_client(self, site_id: str, client_email: str) -> Optional[WebsiteProfile]:
        """Allot/assign a client email to manage a specific website."""
        email_clean = client_email.strip().lower()
        profile = self.get(site_id)
        if not profile:
            return None
        if email_clean not in profile.assigned_client_emails:
            profile.assigned_client_emails.append(email_clean)
            self._save_to_disk()
        return profile

    def revoke_client(self, site_id: str, client_email: str) -> Optional[WebsiteProfile]:
        """Revoke a client email's access to a specific website."""
        email_clean = client_email.strip().lower()
        profile = self.get(site_id)
        if not profile:
            return None
        if email_clean in profile.assigned_client_emails:
            profile.assigned_client_emails.remove(email_clean)
            self._save_to_disk()
        return profile

    def generate_invite_token(self, site_id: str) -> str:
        """Regenerate a fresh secure invite token for a website."""
        profile = self.get(site_id)
        if not profile:
            raise ValueError(f"Site '{site_id}' not found")
        new_token = f"inv_{site_id}_{secrets.token_hex(6)}"
        profile.invite_token = new_token
        self._save_to_disk()
        return new_token

    def get_by_invite_token(self, token: str) -> Optional[WebsiteProfile]:
        """Find a website profile by its active invite token."""
        token_clean = token.strip()
        for site in self._websites.values():
            if site.invite_token == token_clean:
                return site
        return None

    def get_agent_credentials(self, site_id: str, agent_id: str) -> Dict[str, Any]:
        """Fetch saved credentials for an agent for a specific website."""
        profile = self.get(site_id)
        if not profile or not profile.agent_credentials:
            return {}
        return profile.agent_credentials.get(agent_id, {})

    def save_agent_credentials(self, site_id: str, agent_id: str, credentials: Dict[str, Any]) -> Optional[WebsiteProfile]:
        """Save/update credentials for an agent for a specific website."""
        profile = self.get(site_id)
        if not profile:
            return None
        if profile.agent_credentials is None:
            profile.agent_credentials = {}
        
        # Merge or update
        current = profile.agent_credentials.get(agent_id, {})
        current.update(credentials)
        current["updated_at"] = datetime.utcnow().isoformat()
        current["is_connected"] = True
        profile.agent_credentials[agent_id] = current
        
        # Sync top-level fields if relevant
        if agent_id == "ga4-reporting-agent" and "property_id" in credentials:
            profile.ga4_property_id = credentials["property_id"]
        elif agent_id == "gsc-agent" and "site_url" in credentials:
            profile.gsc_site_url = credentials["site_url"]
        elif agent_id == "google-ads-monitoring-agent" and "customer_id" in credentials:
            profile.google_ads_id = credentials["customer_id"]
        elif agent_id == "meta-ads-monitoring-agent" and "ad_account_id" in credentials:
            profile.meta_ads_id = credentials["ad_account_id"]

        self._save_to_disk()
        return profile

    def disconnect_agent(self, site_id: str, agent_id: str) -> Optional[WebsiteProfile]:
        """Disconnects an agent and removes its credentials for a website."""
        profile = self.get(site_id)
        if not profile or not profile.agent_credentials:
            return profile
        if agent_id in profile.agent_credentials:
            del profile.agent_credentials[agent_id]
            self._save_to_disk()
        return profile

    def get_sites_for_user(self, email: str, is_super_admin: bool = False) -> List[WebsiteProfile]:
        """Returns list of websites accessible by this user."""
        if is_super_admin:
            return list(self._websites.values())
        email_clean = email.strip().lower()
        return [
            s for s in self._websites.values()
            if s.owner_email == email_clean or email_clean in s.assigned_client_emails
        ]

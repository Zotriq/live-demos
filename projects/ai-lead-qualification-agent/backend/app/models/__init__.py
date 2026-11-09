"""
Model package – importing this module registers all ORM classes on
:data:`app.database.Base` so that ``Base.metadata.create_all`` works
correctly without needing to import every model file individually.
"""

from app.models.activity import LeadActivity
from app.models.follow_up_email import FollowUpEmail
from app.models.integration_sync import IntegrationSync
from app.models.lead import Lead
from app.models.settings import Settings

__all__ = [
    "Lead",
    "FollowUpEmail",
    "LeadActivity",
    "IntegrationSync",
    "Settings",
]

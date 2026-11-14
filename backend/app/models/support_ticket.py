"""
Re-export SupportTicket and TicketActivity from app.models.support
to avoid duplicate SQLAlchemy table mappings.
"""
from app.models.support import SupportTicket, TicketActivity

__all__ = ["SupportTicket", "TicketActivity"]

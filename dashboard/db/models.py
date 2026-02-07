"""
C2 dashboard SQLAlchemy models.
Targets, traps, visits, campaigns, networks, jobs, audit log.
"""

from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Target(Base):
    """Individual target for profiling."""

    __tablename__ = "targets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    identifier = Column(String(255), unique=True, nullable=False, index=True)
    platform = Column(String(64))  # twitter, discord, file

    status = Column(String(32), default="queued")  # queued, profiling, profiled, deployed, active, archived
    priority = Column(Integer, default=0)

    raw_data = Column(Text)  # JSON string of scraped social data
    profile = Column(Text)   # JSON PsychologicalProfile
    nlp_metrics = Column(Text)  # JSON NLP analysis results

    created_at = Column(DateTime, default=datetime.utcnow)
    profiled_at = Column(DateTime)
    deployed_at = Column(DateTime)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tags = Column(Text)  # JSON list of strings
    notes = Column(Text)

    traps = relationship("Trap", back_populates="target", cascade="all, delete-orphan")
    campaign_memberships = relationship("CampaignTarget", back_populates="target", cascade="all, delete-orphan")
    visits = relationship("Visit", back_populates="target", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="target", foreign_keys="Job.target_id")


class Trap(Base):
    """Generated psychological trap site."""

    __tablename__ = "traps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    target_id = Column(Integer, ForeignKey("targets.id"), nullable=False, index=True)

    url = Column(String(512), unique=True)
    local_path = Column(String(512))
    deployment_method = Column(String(64))  # netlify, vercel, manual, local

    architecture = Column(String(64))  # feed, hub, wiki, thread, gallery
    design_system = Column(Text)  # JSON

    total_visits = Column(Integer, default=0)
    unique_visitors = Column(Integer, default=0)
    avg_session_duration = Column(Float)
    avg_depth = Column(Float)
    return_rate = Column(Float)

    trap_effectiveness = Column(Float)  # 0-100

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_visit = Column(DateTime)

    campaign_id = Column(Integer, ForeignKey("campaigns.id"), index=True)

    target = relationship("Target", back_populates="traps")
    visits = relationship("Visit", back_populates="trap", cascade="all, delete-orphan")
    campaign = relationship("Campaign", back_populates="traps")


class Visit(Base):
    """Individual visit to a trap."""

    __tablename__ = "visits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trap_id = Column(Integer, ForeignKey("traps.id"), nullable=False, index=True)
    target_id = Column(Integer, ForeignKey("targets.id"), nullable=False, index=True)

    session_id = Column(String(128), index=True)
    visitor_fingerprint = Column(String(128))

    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime)
    duration = Column(Float)

    entry_page = Column(String(256))
    exit_page = Column(String(256))
    pages_visited = Column(Text)  # JSON list
    depth = Column(Integer, default=0)

    scroll_depth = Column(Text)  # JSON
    clicks = Column(Text)  # JSON
    time_per_page = Column(Text)  # JSON

    referrer = Column(String(512))
    utm_params = Column(Text)  # JSON

    trap = relationship("Trap", back_populates="visits")
    target = relationship("Target", back_populates="visits")


class Campaign(Base):
    """Multi-target operation."""

    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)

    goal = Column(String(64))  # attention, influence, recruitment, research
    target_network = Column(String(255))

    campaign_type = Column(String(64))  # individual, network, sequential, coordinated
    orchestration_plan = Column(Text)  # JSON

    status = Column(String(32), default="planning")  # planning, active, paused, completed
    started_at = Column(DateTime)
    ends_at = Column(DateTime)

    total_targets = Column(Integer, default=0)
    deployed_traps = Column(Integer, default=0)
    total_engagement = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)

    targets = relationship("CampaignTarget", back_populates="campaign", cascade="all, delete-orphan")
    traps = relationship("Trap", back_populates="campaign")


class CampaignTarget(Base):
    """Many-to-many: campaigns <-> targets."""

    __tablename__ = "campaign_targets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    target_id = Column(Integer, ForeignKey("targets.id"), nullable=False, index=True)

    phase = Column(Integer, default=0)
    scheduled_deploy = Column(DateTime)
    custom_messaging = Column(Text)  # JSON

    status = Column(String(32), default="queued")  # queued, deployed, active, completed
    deployed_at = Column(DateTime)

    campaign = relationship("Campaign", back_populates="targets")
    target = relationship("Target", back_populates="campaign_memberships")


class Network(Base):
    """Network graph snapshot."""

    __tablename__ = "networks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255))

    nodes = Column(Text)  # JSON
    edges = Column(Text)  # JSON

    communities = Column(Text)  # JSON
    central_nodes = Column(Text)  # JSON
    influence_map = Column(Text)  # JSON

    platform = Column(String(64))
    scraped_at = Column(DateTime, default=datetime.utcnow)
    node_count = Column(Integer, default=0)
    edge_count = Column(Integer, default=0)


class Job(Base):
    """Async job queue."""

    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_type = Column(String(64), nullable=False)  # profile, generate_trap, deploy, scrape

    target_id = Column(Integer, ForeignKey("targets.id"), index=True)
    params = Column(Text)  # JSON

    status = Column(String(32), default="queued")  # queued, running, completed, failed
    progress = Column(Float, default=0.0)
    result = Column(Text)  # JSON
    error = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    priority = Column(Integer, default=0)

    target = relationship("Target", back_populates="jobs", foreign_keys=[target_id])


class AuditLog(Base):
    """Audit log for opsec."""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(128), index=True)
    operation = Column(String(128), nullable=False)
    target_id = Column(Integer, ForeignKey("targets.id"))
    details = Column(Text)  # JSON
    timestamp = Column(DateTime, default=datetime.utcnow)

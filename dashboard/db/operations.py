"""Database operations for C2 dashboard (CRUD and queries)."""

import json
from datetime import datetime
from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import Session

from .models import (
    AuditLog,
    Campaign,
    CampaignTarget,
    Engagement,
    Job,
    Network,
    Target,
    Trap,
    Visit,
)


def _json_load(s: str | None) -> Any:
    if s is None:
        return None
    try:
        return json.loads(s)
    except (TypeError, ValueError):
        return None


def _json_dump(v: Any) -> str | None:
    if v is None:
        return None
    return json.dumps(v) if not isinstance(v, str) else v


# ---- Targets ----
def create_target(
    db: Session,
    identifier: str,
    platform: str | None = None,
    priority: int = 0,
    tags: list[str] | None = None,
    notes: str | None = None,
) -> Target:
    t = Target(
        identifier=identifier,
        platform=platform,
        priority=priority,
        tags=_json_dump(tags),
        notes=notes,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def get_target(db: Session, target_id: int) -> Target | None:
    return db.query(Target).filter(Target.id == target_id).first()


def get_target_by_identifier(db: Session, identifier: str) -> Target | None:
    return db.query(Target).filter(Target.identifier == identifier).first()


def list_targets(
    db: Session,
    status: str | None = None,
    platform: str | None = None,
    tags_contains: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Target]:
    q = db.query(Target)
    if status:
        q = q.filter(Target.status == status)
    if platform:
        q = q.filter(Target.platform == platform)
    if tags_contains:
        q = q.filter(Target.tags.contains(tags_contains))
    return q.order_by(desc(Target.priority), desc(Target.created_at)).offset(offset).limit(limit).all()


def update_target(
    db: Session,
    target_id: int,
    **kwargs: Any,
) -> Target | None:
    t = get_target(db, target_id)
    if not t:
        return None
    for k, v in kwargs.items():
        if hasattr(t, k):
            if k in ("tags", "raw_data", "profile", "nlp_metrics") and v is not None and not isinstance(v, str):
                v = _json_dump(v)
            setattr(t, k, v)
    db.commit()
    db.refresh(t)
    return t


def delete_target(db: Session, target_id: int) -> bool:
    t = get_target(db, target_id)
    if not t:
        return False
    db.delete(t)
    db.commit()
    return True


# ---- Traps ----
def create_trap(
    db: Session,
    target_id: int,
    url: str | None = None,
    local_path: str | None = None,
    deployment_method: str | None = None,
    architecture: str | None = None,
    design_system: dict | None = None,
    campaign_id: int | None = None,
) -> Trap:
    trap = Trap(
        target_id=target_id,
        url=url,
        local_path=local_path,
        deployment_method=deployment_method,
        architecture=architecture,
        design_system=_json_dump(design_system),
        campaign_id=campaign_id,
    )
    db.add(trap)
    db.commit()
    db.refresh(trap)
    return trap


def get_trap(db: Session, trap_id: int) -> Trap | None:
    return db.query(Trap).filter(Trap.id == trap_id).first()


def get_trap_by_url(db: Session, url: str) -> Trap | None:
    return db.query(Trap).filter(Trap.url == url).first()


def list_traps(
    db: Session,
    target_id: int | None = None,
    campaign_id: int | None = None,
    is_active: bool | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Trap]:
    q = db.query(Trap)
    if target_id is not None:
        q = q.filter(Trap.target_id == target_id)
    if campaign_id is not None:
        q = q.filter(Trap.campaign_id == campaign_id)
    if is_active is not None:
        q = q.filter(Trap.is_active == is_active)
    return q.order_by(desc(Trap.created_at)).offset(offset).limit(limit).all()


def update_trap(db: Session, trap_id: int, **kwargs: Any) -> Trap | None:
    t = get_trap(db, trap_id)
    if not t:
        return None
    for k, v in kwargs.items():
        if hasattr(t, k):
            if k == "design_system" and v is not None and not isinstance(v, str):
                v = _json_dump(v)
            setattr(t, k, v)
    db.commit()
    db.refresh(t)
    return t


# ---- Visits ----
def create_visit(
    db: Session,
    trap_id: int,
    target_id: int,
    session_id: str | None = None,
    visitor_fingerprint: str | None = None,
    entry_page: str | None = None,
    referrer: str | None = None,
    utm_params: dict | None = None,
) -> Visit:
    v = Visit(
        trap_id=trap_id,
        target_id=target_id,
        session_id=session_id,
        visitor_fingerprint=visitor_fingerprint,
        entry_page=entry_page,
        referrer=referrer,
        utm_params=_json_dump(utm_params),
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


def update_visit_end(
    db: Session,
    visit_id: int | None = None,
    session_id: str | None = None,
    trap_id: int | None = None,
    duration: float | None = None,
    exit_page: str | None = None,
    pages_visited: list[str] | None = None,
    depth: int | None = None,
    scroll_depth: dict | None = None,
    clicks: dict | None = None,
    time_per_page: dict | None = None,
) -> Visit | None:
    q = db.query(Visit)
    if visit_id:
        q = q.filter(Visit.id == visit_id)
    elif session_id and trap_id:
        q = q.filter(Visit.session_id == session_id, Visit.trap_id == trap_id, Visit.ended_at.is_(None))
    else:
        return None
    v = q.first()
    if not v:
        return None
    v.ended_at = datetime.utcnow()
    if duration is not None:
        v.duration = duration
    if exit_page is not None:
        v.exit_page = exit_page
    if pages_visited is not None:
        v.pages_visited = _json_dump(pages_visited)
    if depth is not None:
        v.depth = depth
    if scroll_depth is not None:
        v.scroll_depth = _json_dump(scroll_depth)
    if clicks is not None:
        v.clicks = _json_dump(clicks)
    if time_per_page is not None:
        v.time_per_page = _json_dump(time_per_page)
    db.commit()
    db.refresh(v)
    return v


def get_visits_for_trap(db: Session, trap_id: int, limit: int = 100) -> list[Visit]:
    return db.query(Visit).filter(Visit.trap_id == trap_id).order_by(desc(Visit.started_at)).limit(limit).all()


# ---- Campaigns ----
def create_campaign(
    db: Session,
    name: str,
    description: str | None = None,
    goal: str | None = None,
    target_network: str | None = None,
    campaign_type: str | None = None,
    orchestration_plan: dict | None = None,
) -> Campaign:
    c = Campaign(
        name=name,
        description=description,
        goal=goal,
        target_network=target_network,
        campaign_type=campaign_type,
        orchestration_plan=_json_dump(orchestration_plan),
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def get_campaign(db: Session, campaign_id: int) -> Campaign | None:
    return db.query(Campaign).filter(Campaign.id == campaign_id).first()


def list_campaigns(db: Session, status: str | None = None, limit: int = 50) -> list[Campaign]:
    q = db.query(Campaign)
    if status:
        q = q.filter(Campaign.status == status)
    return q.order_by(desc(Campaign.created_at)).limit(limit).all()


def add_target_to_campaign(
    db: Session,
    campaign_id: int,
    target_id: int,
    phase: int = 0,
    scheduled_deploy: datetime | None = None,
    custom_messaging: dict | None = None,
) -> CampaignTarget | None:
    c = get_campaign(db, campaign_id)
    if not c:
        return None
    ct = CampaignTarget(
        campaign_id=campaign_id,
        target_id=target_id,
        phase=phase,
        scheduled_deploy=scheduled_deploy,
        custom_messaging=_json_dump(custom_messaging),
    )
    db.add(ct)
    c.total_targets = db.query(CampaignTarget).filter(CampaignTarget.campaign_id == campaign_id).count() + 1
    db.commit()
    db.refresh(ct)
    return ct


def remove_target_from_campaign(db: Session, campaign_id: int, target_id: int) -> bool:
    ct = db.query(CampaignTarget).filter(
        CampaignTarget.campaign_id == campaign_id,
        CampaignTarget.target_id == target_id,
    ).first()
    if not ct:
        return False
    db.delete(ct)
    c = get_campaign(db, campaign_id)
    if c:
        c.total_targets = max(0, (c.total_targets or 0) - 1)
    db.commit()
    return True


# ---- Networks ----
def create_network(
    db: Session,
    name: str,
    nodes: list | None = None,
    edges: list | None = None,
    platform: str | None = None,
    communities: dict | None = None,
    central_nodes: list | None = None,
    influence_map: dict | None = None,
) -> Network:
    n = Network(
        name=name,
        nodes=_json_dump(nodes),
        edges=_json_dump(edges),
        platform=platform,
        communities=_json_dump(communities),
        central_nodes=_json_dump(central_nodes),
        influence_map=_json_dump(influence_map),
        node_count=len(nodes) if nodes else 0,
        edge_count=len(edges) if edges else 0,
    )
    db.add(n)
    db.commit()
    db.refresh(n)
    return n


def get_network(db: Session, network_id: int) -> Network | None:
    return db.query(Network).filter(Network.id == network_id).first()


def list_networks(db: Session, limit: int = 50) -> list[Network]:
    return db.query(Network).order_by(desc(Network.scraped_at)).limit(limit).all()


# ---- Jobs ----
def create_job(
    db: Session,
    job_type: str,
    target_id: int | None = None,
    params: dict | None = None,
    priority: int = 0,
) -> Job:
    j = Job(job_type=job_type, target_id=target_id, params=_json_dump(params), priority=priority)
    db.add(j)
    db.commit()
    db.refresh(j)
    return j


def get_job(db: Session, job_id: int) -> Job | None:
    return db.query(Job).filter(Job.id == job_id).first()


def list_jobs(
    db: Session,
    status: str | None = None,
    job_type: str | None = None,
    limit: int = 50,
) -> list[Job]:
    q = db.query(Job)
    if status:
        q = q.filter(Job.status == status)
    if job_type:
        q = q.filter(Job.job_type == job_type)
    return q.order_by(desc(Job.priority), Job.created_at).limit(limit).all()


def update_job(
    db: Session,
    job_id: int,
    status: str | None = None,
    progress: float | None = None,
    result: dict | None = None,
    error: str | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> Job | None:
    j = get_job(db, job_id)
    if not j:
        return None
    if status is not None:
        j.status = status
    if progress is not None:
        j.progress = progress
    if result is not None:
        j.result = _json_dump(result)
    if error is not None:
        j.error = error
    if started_at is not None:
        j.started_at = started_at
    if completed_at is not None:
        j.completed_at = completed_at
    db.commit()
    db.refresh(j)
    return j


# ---- Audit ----
def audit_log(db: Session, session_id: str | None, operation: str, target_id: int | None = None, details: dict | None = None) -> AuditLog:
    a = AuditLog(
        session_id=session_id,
        operation=operation,
        target_id=target_id,
        details=_json_dump(details),
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


# ---- Engagements ----
def create_engagement(
    db: Session,
    target_id: int,
    platform: str,
    engagement_type: str,
    message_content: str | None = None,
    reference_id: str | None = None,
    included_trap: bool = False,
    framing_strategy: str | None = None,
) -> Engagement:
    e = Engagement(
        target_id=target_id,
        platform=platform,
        engagement_type=engagement_type,
        message_content=message_content,
        reference_id=reference_id,
        included_trap=included_trap,
        framing_strategy=framing_strategy,
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


def get_engagement(db: Session, engagement_id: int) -> Engagement | None:
    return db.query(Engagement).filter(Engagement.id == engagement_id).first()


def list_engagements_for_target(
    db: Session,
    target_id: int,
    limit: int = 100,
) -> list[Engagement]:
    return (
        db.query(Engagement)
        .filter(Engagement.target_id == target_id)
        .order_by(desc(Engagement.sent_at))
        .limit(limit)
        .all()
    )


def update_engagement(
    db: Session,
    engagement_id: int,
    **kwargs: Any,
) -> Engagement | None:
    e = get_engagement(db, engagement_id)
    if not e:
        return None
    for k, v in kwargs.items():
        if hasattr(e, k):
            setattr(e, k, v)
    db.commit()
    db.refresh(e)
    return e

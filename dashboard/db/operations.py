"""Database operations for C2 dashboard (CRUD and queries)."""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session

from .models import (
    AuditLog,
    Campaign,
    CampaignTarget,
    Job,
    Network,
    Target,
    Trap,
    Visit,
)


def _json_load(s: Optional[str]) -> Any:
    if s is None:
        return None
    try:
        return json.loads(s)
    except (TypeError, ValueError):
        return None


def _json_dump(v: Any) -> Optional[str]:
    if v is None:
        return None
    return json.dumps(v) if not isinstance(v, str) else v


# ---- Targets ----
def create_target(
    db: Session,
    identifier: str,
    platform: Optional[str] = None,
    priority: int = 0,
    tags: Optional[List[str]] = None,
    notes: Optional[str] = None,
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


def get_target(db: Session, target_id: int) -> Optional[Target]:
    return db.query(Target).filter(Target.id == target_id).first()


def get_target_by_identifier(db: Session, identifier: str) -> Optional[Target]:
    return db.query(Target).filter(Target.identifier == identifier).first()


def list_targets(
    db: Session,
    status: Optional[str] = None,
    platform: Optional[str] = None,
    tags_contains: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Target]:
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
) -> Optional[Target]:
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
    url: Optional[str] = None,
    local_path: Optional[str] = None,
    deployment_method: Optional[str] = None,
    architecture: Optional[str] = None,
    design_system: Optional[Dict] = None,
    campaign_id: Optional[int] = None,
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


def get_trap(db: Session, trap_id: int) -> Optional[Trap]:
    return db.query(Trap).filter(Trap.id == trap_id).first()


def get_trap_by_url(db: Session, url: str) -> Optional[Trap]:
    return db.query(Trap).filter(Trap.url == url).first()


def list_traps(
    db: Session,
    target_id: Optional[int] = None,
    campaign_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Trap]:
    q = db.query(Trap)
    if target_id is not None:
        q = q.filter(Trap.target_id == target_id)
    if campaign_id is not None:
        q = q.filter(Trap.campaign_id == campaign_id)
    if is_active is not None:
        q = q.filter(Trap.is_active == is_active)
    return q.order_by(desc(Trap.created_at)).offset(offset).limit(limit).all()


def update_trap(db: Session, trap_id: int, **kwargs: Any) -> Optional[Trap]:
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
    session_id: Optional[str] = None,
    visitor_fingerprint: Optional[str] = None,
    entry_page: Optional[str] = None,
    referrer: Optional[str] = None,
    utm_params: Optional[Dict] = None,
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
    visit_id: Optional[int] = None,
    session_id: Optional[str] = None,
    trap_id: Optional[int] = None,
    duration: Optional[float] = None,
    exit_page: Optional[str] = None,
    pages_visited: Optional[List[str]] = None,
    depth: Optional[int] = None,
    scroll_depth: Optional[Dict] = None,
    clicks: Optional[Dict] = None,
    time_per_page: Optional[Dict] = None,
) -> Optional[Visit]:
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


def get_visits_for_trap(db: Session, trap_id: int, limit: int = 100) -> List[Visit]:
    return db.query(Visit).filter(Visit.trap_id == trap_id).order_by(desc(Visit.started_at)).limit(limit).all()


# ---- Campaigns ----
def create_campaign(
    db: Session,
    name: str,
    description: Optional[str] = None,
    goal: Optional[str] = None,
    target_network: Optional[str] = None,
    campaign_type: Optional[str] = None,
    orchestration_plan: Optional[Dict] = None,
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


def get_campaign(db: Session, campaign_id: int) -> Optional[Campaign]:
    return db.query(Campaign).filter(Campaign.id == campaign_id).first()


def list_campaigns(db: Session, status: Optional[str] = None, limit: int = 50) -> List[Campaign]:
    q = db.query(Campaign)
    if status:
        q = q.filter(Campaign.status == status)
    return q.order_by(desc(Campaign.created_at)).limit(limit).all()


def add_target_to_campaign(
    db: Session,
    campaign_id: int,
    target_id: int,
    phase: int = 0,
    scheduled_deploy: Optional[datetime] = None,
    custom_messaging: Optional[Dict] = None,
) -> Optional[CampaignTarget]:
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
    nodes: Optional[List] = None,
    edges: Optional[List] = None,
    platform: Optional[str] = None,
    communities: Optional[Dict] = None,
    central_nodes: Optional[List] = None,
    influence_map: Optional[Dict] = None,
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


def get_network(db: Session, network_id: int) -> Optional[Network]:
    return db.query(Network).filter(Network.id == network_id).first()


def list_networks(db: Session, limit: int = 50) -> List[Network]:
    return db.query(Network).order_by(desc(Network.scraped_at)).limit(limit).all()


# ---- Jobs ----
def create_job(
    db: Session,
    job_type: str,
    target_id: Optional[int] = None,
    params: Optional[Dict] = None,
    priority: int = 0,
) -> Job:
    j = Job(job_type=job_type, target_id=target_id, params=_json_dump(params), priority=priority)
    db.add(j)
    db.commit()
    db.refresh(j)
    return j


def get_job(db: Session, job_id: int) -> Optional[Job]:
    return db.query(Job).filter(Job.id == job_id).first()


def list_jobs(
    db: Session,
    status: Optional[str] = None,
    job_type: Optional[str] = None,
    limit: int = 50,
) -> List[Job]:
    q = db.query(Job)
    if status:
        q = q.filter(Job.status == status)
    if job_type:
        q = q.filter(Job.job_type == job_type)
    return q.order_by(desc(Job.priority), Job.created_at).limit(limit).all()


def update_job(
    db: Session,
    job_id: int,
    status: Optional[str] = None,
    progress: Optional[float] = None,
    result: Optional[Dict] = None,
    error: Optional[str] = None,
    started_at: Optional[datetime] = None,
    completed_at: Optional[datetime] = None,
) -> Optional[Job]:
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
def audit_log(db: Session, session_id: Optional[str], operation: str, target_id: Optional[int] = None, details: Optional[Dict] = None) -> AuditLog:
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

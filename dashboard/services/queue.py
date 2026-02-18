"""
Async job queue for expensive operations: profile, generate_trap, deploy, scrape.
Wired to HoleSpawn ingest, profile, and site_builder.
"""

import time
from collections.abc import Callable
from dataclasses import asdict, fields
from datetime import datetime
from pathlib import Path
from typing import Any

from dashboard.db import get_db
from dashboard.db import operations as ops


def _profile_from_dict(data: dict[str, Any]):
    """Build PsychologicalProfile from stored JSON (only known fields)."""
    from holespawn.profile import PsychologicalProfile
    valid = {f.name for f in fields(PsychologicalProfile)}
    kwargs = {}
    for k, v in data.items():
        if k not in valid:
            continue
        if k == "themes" and isinstance(v, list):
            kwargs[k] = [tuple(x) if isinstance(x, (list, tuple)) else x for x in v]
        else:
            kwargs[k] = v
    return PsychologicalProfile(**kwargs)


class JobQueue:
    """
    Async job processing for C2 operations.
    Enqueue jobs; a worker (or inline) processes them.
    """

    def __init__(self, runner: Callable[[str, int | None, dict], Any] | None = None):
        self._runner = runner  # (job_type, target_id, params) -> result or raise

    def enqueue(self, job_type: str, target_id: int | None = None, params: dict | None = None, priority: int = 0) -> int:
        """Add job to queue; returns job_id."""
        with get_db() as db:
            j = ops.create_job(db, job_type=job_type, target_id=target_id, params=params, priority=priority)
            return j.id

    def get_status(self, job_id: int) -> dict[str, Any] | None:
        """Get job status and progress."""
        with get_db() as db:
            j = ops.get_job(db, job_id)
            if not j:
                return None
            return {
                "id": j.id,
                "job_type": j.job_type,
                "target_id": j.target_id,
                "status": j.status,
                "progress": j.progress,
                "result": ops._json_load(j.result) if getattr(j, "result", None) else None,
                "error": j.error,
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "started_at": j.started_at.isoformat() if j.started_at else None,
                "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            }

    def process_one(self, job_id: int) -> bool:
        """Process a single job by id. Returns True if processed, False if not found or not queued."""
        with get_db() as db:
            j = ops.get_job(db, job_id)
            if not j or j.status != "queued":
                return False
            ops.update_job(db, job_id, status="running", started_at=datetime.utcnow())
            db.commit()

        params = ops._json_load(j.params) if j.params else {}
        try:
            if self._runner:
                result = self._runner(j.job_type, j.target_id, params or {})
            else:
                result = self._execute_job(j.job_type, j.target_id, params or {})
            with get_db() as db:
                ops.update_job(db, job_id, status="completed", progress=100.0, result=result, completed_at=datetime.utcnow())
            return True
        except Exception as e:
            with get_db() as db:
                ops.update_job(db, job_id, status="failed", error=str(e), completed_at=datetime.utcnow())
            return False

    def _execute_job(self, job_type: str, target_id: int | None, params: dict) -> dict[str, Any]:
        """Execute a job based on its type using HoleSpawn pipelines."""
        if job_type == "profile":
            return self._run_profile(target_id, params)
        if job_type == "generate_trap":
            return self._run_generate_trap(target_id, params)
        if job_type == "deploy":
            return self._run_deploy(params)
        if job_type == "scrape":
            return self._run_scrape(target_id, params)
        raise ValueError(f"Unknown job type: {job_type}")

    def _run_profile(self, target_id: int | None, params: dict) -> dict[str, Any]:
        """Build psychological profile for target from raw_data."""
        if target_id is None:
            raise ValueError("profile job requires target_id")
        with get_db() as db:
            target = ops.get_target(db, target_id)
            if not target:
                raise ValueError(f"Target {target_id} not found")
            raw = ops._json_load(target.raw_data)
        if not raw:
            raise ValueError("Target has no raw_data; add Discord export or text first")

        use_nlp = params.get("use_nlp", True)
        use_llm = params.get("use_llm", True)
        use_local = params.get("use_local", False)

        if isinstance(raw, dict) and raw.get("messages"):
            from holespawn.profile.discord_profile_builder import build_discord_profile
            profile = build_discord_profile(
                raw,
                use_nlp=use_nlp,
                use_llm=use_llm,
                use_local=use_local,
                local_preset=params.get("local_preset"),
                api_base=params.get("api_base"),
                model=params.get("model"),
            )
        else:
            from holespawn.ingest import load_from_text
            from holespawn.profile import build_profile
            text = raw.get("text", raw.get("content", "")) if isinstance(raw, dict) else str(raw)
            content = load_from_text(text)
            if not list(content.iter_posts()):
                raise ValueError("No posts in raw_data text")
            profile = build_profile(content)

        profile_dict = asdict(profile)
        with get_db() as db:
            ops.update_target(
                db,
                target_id,
                profile=profile_dict,
                profiled_at=datetime.utcnow(),
                status="profiled",
            )
        return {"status": "completed", "target_id": target_id}

    def _run_generate_trap(self, target_id: int | None, params: dict) -> dict[str, Any]:
        """Generate trap site from target profile."""
        if target_id is None:
            raise ValueError("generate_trap job requires target_id")
        with get_db() as db:
            target = ops.get_target(db, target_id)
            if not target:
                raise ValueError(f"Target {target_id} not found")
            profile_data = ops._json_load(target.profile)
        if not profile_data:
            raise ValueError("Target not profiled; queue profile job first")

        profile = _profile_from_dict(profile_data)
        root = Path(__file__).resolve().parent.parent.parent
        base_out = root / "outputs" / "traps"
        base_out.mkdir(parents=True, exist_ok=True)
        output_dir = base_out / f"trap_{target_id}_{int(time.time())}"
        output_dir.mkdir(parents=True, exist_ok=True)

        from holespawn.site_builder.pure_generator import generate_site_from_profile
        structure = generate_site_from_profile(
            profile,
            output_dir,
            skip_validation=params.get("skip_validation", False),
        )
        architecture = getattr(profile, "browsing_style", None) or "feed"
        design_system = profile_data.get("color_palette") or profile_data.get("layout_style")
        design_json = {k: profile_data.get(k) for k in ("color_palette", "layout_style", "typography_vibe") if profile_data.get(k)}

        with get_db() as db:
            trap = ops.create_trap(
                db,
                target_id=target_id,
                local_path=str(output_dir),
                deployment_method="local",
                architecture=architecture,
                design_system=design_json,
                campaign_id=params.get("campaign_id"),
            )
        return {"status": "completed", "trap_id": trap.id, "path": str(output_dir)}

    def _run_deploy(self, params: dict) -> dict[str, Any]:
        """Mark trap as deployed (placeholder; wire to Netlify/Vercel later)."""
        trap_id = params.get("trap_id")
        if trap_id is None:
            raise ValueError("deploy job requires trap_id in params")
        with get_db() as db:
            trap = ops.get_trap(db, trap_id)
            if not trap:
                raise ValueError(f"Trap {trap_id} not found")
            url = params.get("url") or f"https://trap-{trap_id}.local"
            ops.update_trap(db, trap_id, url=url, is_active=True)
        return {"status": "completed", "url": url, "trap_id": trap_id}

    def _run_scrape(self, target_id: int | None, params: dict) -> dict[str, Any]:
        """Placeholder for scrape; wire to Apify or ingest when needed."""
        return {"status": "stub", "target_id": target_id, "message": "Scrape not implemented; add data via API or import"}

    def process_jobs(self, max_jobs: int = 10) -> int:
        """Process up to max_jobs queued jobs. Returns number processed."""
        with get_db() as db:
            jobs = ops.list_jobs(db, status="queued", limit=max_jobs)
        processed = 0
        for j in jobs:
            if self.process_one(j.id):
                processed += 1
        return processed

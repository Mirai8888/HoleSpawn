"""
Execute HoleSpawn agent tools: profiling, traps, deploy, social engagement.
Single entry point for the autonomous operator.
"""

from typing import Any

from . import social_executor


def execute(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Execute a single tool by name with given arguments. Returns result dict."""
    if tool_name in social_executor.TOOL_EXECUTORS:
        fn = social_executor.TOOL_EXECUTORS[tool_name]
        import inspect
        valid_params = set(inspect.signature(fn).parameters.keys())
        kwargs = {k: v for k, v in arguments.items() if k in valid_params}
        return fn(**kwargs)

    # Core tools (dashboard queue / ops)
    if tool_name == "profile_target":
        from dashboard.services.queue import JobQueue

        q = JobQueue()
        job_id = q.enqueue(
            "profile",
            target_id=arguments.get("target_id"),
            params={
                "use_nlp": arguments.get("use_nlp", True),
                "use_llm": arguments.get("use_llm", True),
            },
            priority=1,
        )
        q.process_one(job_id)
        return {"job_id": job_id, "status": "completed"}

    if tool_name == "generate_trap":
        from dashboard.services.queue import JobQueue

        q = JobQueue()
        job_id = q.enqueue("generate_trap", target_id=arguments.get("target_id"), priority=1)
        q.process_one(job_id)
        return {"job_id": job_id, "status": "completed"}

    if tool_name == "deploy_trap":
        from dashboard.db import get_db
        from dashboard.db import operations as ops

        trap_id = arguments.get("trap_id")
        url = arguments.get("url") or f"https://trap-{trap_id}.local"
        with get_db() as db:
            t = ops.update_trap(db, trap_id, url=url, is_active=True)
        return (
            {"status": "completed", "url": url, "trap_id": trap_id}
            if t
            else {"status": "failed", "error": "trap not found"}
        )

    if tool_name == "get_trap_effectiveness":
        from dashboard.services.monitor import get_monitor

        trap_id = arguments.get("trap_id")
        score = get_monitor().get_trap_effectiveness(trap_id)
        return {"trap_id": trap_id, "effectiveness": score}

    if tool_name == "analyze_network":
        from dashboard.services.network_analysis import NetworkAnalysisService

        svc = NetworkAnalysisService()
        nid = svc.build_from_profiles_dir(
            arguments.get("dir_path", ""),
            name=arguments.get("name"),
        )
        return (
            {"network_id": nid, "status": "completed"}
            if nid
            else {"status": "failed", "error": "no profiles or analyzer error"}
        )

    if tool_name == "get_operation_status":
        from dashboard.db import get_db
        from dashboard.db import operations as ops

        with get_db() as db:
            targets = ops.list_targets(db, limit=500)
            traps = ops.list_traps(db, limit=500)
            jobs = ops.list_jobs(db, limit=50)
            engagements = []
            for t in targets[:100]:
                engagements.extend(ops.list_engagements_for_target(db, t.id, limit=5))
        traps_active = [x for x in traps if x.is_active]
        high_effectiveness = [x for x in traps_active if (x.trap_effectiveness or 0) >= 70]
        return {
            "targets_count": len(targets),
            "traps_count": len(traps),
            "traps_active": len(traps_active),
            "traps_70_plus": len(high_effectiveness),
            "jobs_recent": len(jobs),
            "engagements_count": len(engagements),
        }

    return {"status": "unknown_tool", "name": tool_name}

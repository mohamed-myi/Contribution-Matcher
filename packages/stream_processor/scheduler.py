"""
Continuous Scheduler.

APScheduler-based scheduler for 24/7 discovery operation.
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Callable, Dict, List, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


# Discovery strategies with priority
DISCOVERY_STRATEGIES = [
    {
        "name": "good_first_issues",
        "query": 'is:open is:issue label:"good first issue" sort:updated-desc',
        "priority": "high",
        "interval_minutes": 30,
        "max_results": 200,
    },
    {
        "name": "help_wanted",
        "query": 'is:open is:issue label:"help wanted" sort:updated-desc',
        "priority": "high",
        "interval_minutes": 30,
        "max_results": 200,
    },
    {
        "name": "beginner_friendly",
        "query": 'is:open is:issue label:"beginner friendly" OR label:"beginner-friendly" sort:updated-desc',
        "priority": "medium",
        "interval_minutes": 60,
        "max_results": 100,
    },
    {
        "name": "python_issues",
        "query": 'is:open is:issue label:"good first issue" language:python sort:stars-desc',
        "priority": "medium",
        "interval_minutes": 60,
        "max_results": 100,
    },
    {
        "name": "javascript_issues",
        "query": 'is:open is:issue label:"good first issue" language:javascript sort:stars-desc',
        "priority": "medium",
        "interval_minutes": 60,
        "max_results": 100,
    },
    {
        "name": "typescript_issues",
        "query": 'is:open is:issue label:"good first issue" language:typescript sort:stars-desc',
        "priority": "medium",
        "interval_minutes": 60,
        "max_results": 100,
    },
    {
        "name": "documentation",
        "query": 'is:open is:issue label:"documentation" label:"good first issue" sort:updated-desc',
        "priority": "low",
        "interval_minutes": 120,
        "max_results": 50,
    },
    {
        "name": "trending_repos",
        "query": 'is:open is:issue stars:>1000 label:"good first issue" sort:updated-desc',
        "priority": "low",
        "interval_minutes": 120,
        "max_results": 100,
    },
]


class DiscoveryScheduler:
    """
    Continuous discovery scheduler using APScheduler.
    
    Features:
    - Multiple discovery strategies with different priorities
    - Configurable intervals per strategy
    - Graceful shutdown handling
    - Statistics tracking
    """
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self.stats: Dict[str, Dict] = {}
        self._discovery_callback: Optional[Callable] = None
        self._running = False
    
    def set_discovery_callback(self, callback: Callable) -> None:
        """
        Set the callback function for discovery operations.
        
        The callback should accept (strategy_name, query, max_results)
        and return the number of issues discovered.
        """
        self._discovery_callback = callback
    
    def add_discovery_jobs(self) -> None:
        """Add all discovery strategy jobs to the scheduler."""
        for strategy in DISCOVERY_STRATEGIES:
            job_id = f"discovery_{strategy['name']}"
            
            self.scheduler.add_job(
                self._run_strategy,
                trigger=IntervalTrigger(minutes=strategy["interval_minutes"]),
                id=job_id,
                name=f"Discovery: {strategy['name']}",
                kwargs={"strategy": strategy},
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
            
            self.stats[strategy["name"]] = {
                "last_run": None,
                "issues_discovered": 0,
                "runs": 0,
                "errors": 0,
            }
            
            logger.info(f"Added job: {job_id} (every {strategy['interval_minutes']} min)")
    
    def add_staleness_check_job(
        self,
        callback: Callable,
        interval_hours: int = 6,
    ) -> None:
        """Add job to check for stale (closed) issues."""
        self.scheduler.add_job(
            callback,
            trigger=IntervalTrigger(hours=interval_hours),
            id="staleness_check",
            name="Staleness Check",
            replace_existing=True,
            max_instances=1,
        )
        logger.info(f"Added staleness check job (every {interval_hours} hours)")
    
    async def _run_strategy(self, strategy: Dict) -> None:
        """Execute a discovery strategy."""
        name = strategy["name"]
        
        if not self._discovery_callback:
            logger.warning(f"No discovery callback set, skipping {name}")
            return
        
        logger.info(f"Running strategy: {name}")
        start_time = datetime.utcnow()
        
        try:
            count = await self._discovery_callback(
                strategy_name=name,
                query=strategy["query"],
                max_results=strategy["max_results"],
            )
            
            self.stats[name]["last_run"] = start_time.isoformat()
            self.stats[name]["issues_discovered"] += count
            self.stats[name]["runs"] += 1
            
            logger.info(f"Strategy {name} completed: {count} issues")
        
        except Exception as e:
            self.stats[name]["errors"] += 1
            logger.error(f"Strategy {name} failed: {e}")
    
    def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            return
        
        self.scheduler.start()
        self._running = True
        logger.info("Scheduler started")
    
    def stop(self) -> None:
        """Stop the scheduler gracefully."""
        if not self._running:
            return
        
        self.scheduler.shutdown(wait=True)
        self._running = False
        logger.info("Scheduler stopped")
    
    def get_stats(self) -> Dict:
        """Get scheduler statistics."""
        jobs = []
        for job in self.scheduler.get_jobs():
            # APScheduler 3.x uses next_run_time attribute
            next_run = getattr(job, 'next_run_time', None)
            if next_run is None:
                # Fallback for different APScheduler versions
                try:
                    next_run = job.trigger.get_next_fire_time(None, datetime.utcnow())
                except (AttributeError, TypeError):
                    next_run = None
            
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": next_run.isoformat() if next_run else None,
            })
        
        return {
            "running": self._running,
            "strategies": self.stats,
            "jobs": jobs,
        }
    
    def trigger_strategy(self, strategy_name: str) -> bool:
        """Manually trigger a discovery strategy."""
        job_id = f"discovery_{strategy_name}"
        job = self.scheduler.get_job(job_id)
        
        if job:
            job.modify(next_run_time=datetime.utcnow())
            return True
        
        return False


async def run_continuous_discovery():
    """
    Main entry point for continuous discovery.
    
    Sets up the scheduler and runs until interrupted.
    """
    from packages.stream_processor.github import GitHubStreamClient
    from packages.stream_processor.queue import QueueProducer
    
    scheduler = DiscoveryScheduler()
    
    async def discovery_callback(
        strategy_name: str,
        query: str,
        max_results: int,
    ) -> int:
        """Discovery callback that uses the stream client and queue producer."""
        token = os.getenv("PAT_TOKEN") or os.getenv("GITHUB_TOKEN")
        if not token:
            logger.error("No GitHub token available")
            return 0
        
        count = 0
        
        with QueueProducer() as producer:
            async with GitHubStreamClient(token) as client:
                async for issue in client.search_issues(query, max_results=max_results):
                    if producer.publish(issue):
                        count += 1
        
        return count
    
    scheduler.set_discovery_callback(discovery_callback)
    scheduler.add_discovery_jobs()
    scheduler.start()
    
    try:
        # Run forever
        while True:
            await asyncio.sleep(60)
            logger.info(f"Stats: {scheduler.get_stats()}")
    except asyncio.CancelledError:
        scheduler.stop()
        logger.info("Discovery stopped")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_continuous_discovery())

import logging
import os
import signal as sig
from collections import deque
from threading import Event, Thread
from typing import Deque, Dict, Optional

from sqlmodel import asc, desc, or_, select, func

from ..context import ServerContext
from ..models.job import Job, JobRunnerHistoryItem, JobStatus, RunState
from ..models.novel import Novel
from ..models.user import User
from ..models.enums import JobPriority
from croniter import croniter
from datetime import datetime, timezone

from ..utils.time_utils import current_timestamp
from .cleaner import microtask as cleaner_task
from .runner import microtask

logger = logging.getLogger(__name__)

CONCURRENCY = 2


class JobScheduler:
    def __init__(self, ctx: ServerContext) -> None:
        self.ctx = ctx
        self.db = ctx.db
        self.start_ts: int = 0
        self.last_cleanup_ts: int = 0
        self.signal: Optional[Event] = None
        self.threads: Dict[str, Thread] = {}
        self.history: Deque[JobRunnerHistoryItem] = deque(maxlen=50)
        self.idle_since_ts: int = 0
        self.last_schedule_check_ts: int = 0

        self.has_run_jobs: bool = False

    def close(self):
        self.stop()

    @property
    def running(self) -> bool:
        if not self.signal:
            return False
        return not self.signal.is_set()

    def start(self):
        if self.running:
            return
        self.signal = Event()
        self.start_ts = current_timestamp()
        Thread(
            target=self.run,
            args=[self.signal],
            daemon=True,
        ).start()

    def stop(self):
        if not self.signal:
            return
        self.signal.set()
        self.signal = None

    def run(self, signal=Event()):
        logger.info("Scheduler started")
        pending_restart = False
        cfg = self.ctx.config.app
        reset_interval = cfg.scheduler_reset_interval * 1000
        try:
            while not signal.is_set():
                signal.wait(cfg.runner_cooldown)
                if signal.is_set():
                    return
                self.__free()
                self.__add_cleaner(signal)
                self.__check_schedules(signal)

                if len(self.threads) < CONCURRENCY:
                    self.__add_job(signal)

                # check for idleness
                self.__check_idle_and_restart(signal)

                if current_timestamp() - self.start_ts > reset_interval:
                    pending_restart = True
                    self.stop()
        except KeyboardInterrupt:
            signal.set()
        finally:
            logger.info("Scheduler stoppped")
            if pending_restart:
                self.start()

    def __check_idle_and_restart(self, signal=Event()):
        # Do not restart if the worker has neever run any jobs
        if not self.has_run_jobs:
            return

        # Do not restart if there are active threads
        if len(self.threads) > 0:
            self.idle_since_ts = 0  # reset idle timer
            return

        # Do not restart if there are pending jobs
        with self.db.session() as sess:
            stmt = select(func.count()).select_from(Job).where(Job.status == JobStatus.PENDING)
            pending_jobs = sess.exec(stmt).one()
        if pending_jobs > 0:
            self.idle_since_ts = 0  # reset idle timer
            return

        # If we are here, the worker is idle
        logger.debug("Scheduler is idle. No actrive or pending jobs.")
        if self.idle_since_ts == 0:
            self.idle_since_ts = current_timestamp()
            return

        # check if idle time exceeds threshold
        cfg = self.ctx.config.app
        idle_duration_ms = current_timestamp() - self.idle_since_ts
        restart_threshold_ms = cfg.idle_restart_threshold * 1000

        if idle_duration_ms > restart_threshold_ms:
            logger.info(f"Scheduler has been iddle for {idle_duration_ms // 1000}s. Restarting to free memory.")
            signal.set()  # stop the scheduler
            os.kill(1, sig.SIGTERM)  # restart the whole server process

    def __free(self):
        logger.debug("Cleaning up finished job threads")
        threads_to_remove = []
        # Iterate over a copy to allow safe modification
        for key, thread in list(self.threads.items()):
            if not thread.is_alive():
                threads_to_remove.append(key)

        # remove all collected dead threads in a separate loop
        for key in threads_to_remove:
            del self.threads[key]
            logger.debug(f"Removed finished thread for job: {key}")

    def __add_job(self, signal=Event()):
        logger.debug("Running new task")
        with self.db.session() as sess:
            # fetch jobs based on priority
            stmt = select(Job)
            stmt = stmt.where(
                or_(
                    Job.status == JobStatus.PENDING,
                    Job.status == JobStatus.RUNNING,
                )
            )
            stmt = stmt.order_by(
                desc(Job.priority),
                asc(Job.created_at),
            )
            jobs = sess.exec(stmt).all()

            for job in jobs:
                # cancel duplicate jobs
                if not job.novel_id:
                    job.status = JobStatus.COMPLETED
                    job.run_state = RunState.FAILED
                    job.error = "Attached novel is not found"
                    sess.add(job)
                    sess.commit()
                    continue

                if job.novel_id in self.threads:
                    if job.status != JobStatus.RUNNING:
                        job.status = JobStatus.COMPLETED
                        job.run_state = RunState.CANCELED
                        job.error = "Canceled as a duplicate job"
                        sess.add(job)
                        sess.commit()
                    continue

                # if queue is full, wait for the next round,
                # but continue processing pending jobs to detect duplicates
                if len(self.threads) >= CONCURRENCY:
                    continue

                # mark as it executed at least one job
                self.has_run_jobs = True

                # create and start threads
                t = Thread(
                    target=microtask,
                    args=[job.id, signal],
                    # daemon=True,
                )
                t.start()
                self.threads[job.novel_id] = t

                # log this to history
                self.history.append(
                    JobRunnerHistoryItem(
                        time=current_timestamp(),
                        job_id=job.id,
                        user_id=job.user_id,
                        novel_id=job.novel_id,
                        status=job.status,
                        run_state=job.run_state,
                    )
                )

    def __add_cleaner(self, signal=Event()):
        # skip if another cleaner is already running
        if "cleaner" in self.threads:
            return

        # skip if cleaner has run recently
        timeout = self.ctx.config.app.cleaner_cooldown * 1000
        if current_timestamp() - self.last_cleanup_ts < timeout:
            return
        self.last_cleanup_ts = current_timestamp()

        # create and start threads
        t = Thread(
            target=cleaner_task,
            args=[signal],
        )
        t.start()
        self.threads["cleaner"] = t

    def __check_schedules(self, signal=Event()):
        # Run every minute
        if current_timestamp() - self.last_schedule_check_ts < 60 * 1000:
            return
        self.last_schedule_check_ts = current_timestamp()

        logger.debug("Checking schedules")
        with self.db.session() as sess:
            novels = sess.exec(select(Novel)).all()
            for novel in novels:
                if not novel.extra:
                    continue
                
                schedule = novel.extra.get('schedule')
                if not schedule or not schedule.get('enabled'):
                    continue
                
                cron_expr = schedule.get('cron')
                if not cron_expr:
                    continue
                
                next_run_ts = schedule.get('next_run')
                now_ts = current_timestamp() / 1000 # seconds
                
                should_run = False
                if not next_run_ts:
                    should_run = True
                    logger.debug(f"Novel {novel.id}: First run (next_run_ts is None)")
                elif next_run_ts <= now_ts:
                    should_run = True
                    logger.debug(f"Novel {novel.id}: Due run (next_run_ts {next_run_ts} <= now_ts {now_ts})")
                
                if should_run:

                    logger.info(f"Scheduled job triggered for novel: {novel.title}")
                    
                    # Get a user for the job (use the first available user)
                    user = sess.exec(select(User)).first()
                    if not user:
                        logger.warning("No user found to assign scheduled job")
                        continue

                    # Create job
                    job = Job(
                        user_id=user.id,
                        novel_id=novel.id,
                        url=novel.url,
                        priority=JobPriority.LOW,
                    )
                    sess.add(job)
                    
                    # Update next_run
                    try:
                        local_tz = datetime.now().astimezone().tzinfo
                        now_local = datetime.fromtimestamp(now_ts, local_tz)
                        iter = croniter(cron_expr, now_local)
                        next_run = iter.get_next(float)
                        logger.info(f"Novel {novel.id}: Updating next_run to {next_run}")
                        
                        # Create a deep copy or new dict to ensure SQLAlchemy detects change
                        new_extra = dict(novel.extra)
                        new_schedule = dict(schedule)
                        new_schedule['next_run'] = next_run
                        new_extra['schedule'] = new_schedule
                        novel.extra = new_extra
                        
                        sess.add(novel)
                        sess.commit()
                    except Exception as e:
                        logger.error(f"Failed to schedule novel {novel.id}: {e}")

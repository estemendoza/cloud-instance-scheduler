import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import (
    APIRouter, BackgroundTasks, Depends, HTTPException,
    Query, status,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_db, require_role
from app.models.user import User
from app.models.cloud_account import CloudAccount
from app.models.pricing_job import PricingJobRun
from app.services.pricing_fetcher import PricingFetcher
from app.schemas.pricing_job import (
    PricingJobRunResponse,
    PricingJobTriggerRequest,
    PricingJobTriggerResponse,
    PricingStatusSummary,
    ProviderStatus,
    GcpAccountOption,
)
from app.services.encryption import decrypt_credentials
from app.services.scheduler import scheduler_service

logger = logging.getLogger(__name__)

router = APIRouter()

VALID_PROVIDERS = ["aws", "azure", "gcp"]


@router.get(
    "/status",
    response_model=PricingStatusSummary,
)
async def get_pricing_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Get pricing update status summary."""
    providers: dict[str, ProviderStatus] = {}

    for ptype in VALID_PROVIDERS:
        result = await db.execute(
            select(PricingJobRun)
            .where(
                PricingJobRun.provider_type == ptype,
                PricingJobRun.status.in_(
                    ["completed", "failed"]
                ),
            )
            .order_by(PricingJobRun.started_at.desc())
            .limit(1)
        )
        last_run = result.scalar_one_or_none()

        if last_run is None:
            pstatus = "never_run"
        elif last_run.status == "failed":
            pstatus = "failed"
        else:
            pstatus = "success"

        providers[ptype] = ProviderStatus(
            last_run=(
                PricingJobRunResponse.model_validate(
                    last_run
                )
                if last_run else None
            ),
            status=pstatus,
        )

    # Check if any job is currently running
    running_result = await db.execute(
        select(PricingJobRun)
        .where(
            PricingJobRun.status.in_(
                ["running", "pending"]
            )
        )
        .limit(1)
    )
    is_running = (
        running_result.scalar_one_or_none() is not None
    )

    # Get next scheduled time from APScheduler
    next_scheduled = None
    try:
        job = scheduler_service.scheduler.get_job(
            "pricing_update_job"
        )
        if job and job.next_run_time:
            next_scheduled = (
                job.next_run_time.strftime(
                    "%Y-%m-%d %H:%M UTC"
                )
            )
    except Exception:
        pass

    return PricingStatusSummary(
        next_scheduled_utc=next_scheduled,
        is_running=is_running,
        providers=providers,
    )


@router.get(
    "/gcp-accounts",
    response_model=List[GcpAccountOption],
)
async def list_gcp_accounts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """List GCP cloud accounts available for pricing."""
    result = await db.execute(
        select(CloudAccount).where(
            CloudAccount.provider_type == "gcp",
            CloudAccount.is_active.is_(True),
        )
    )
    accounts = result.scalars().all()

    options = []
    for acct in accounts:
        project_id = None
        try:
            creds = decrypt_credentials(
                acct.credentials_encrypted
            )
            project_id = creds.get("project_id")
        except Exception:
            pass
        options.append(GcpAccountOption(
            id=acct.id,
            name=acct.name,
            project_id=project_id,
        ))

    return options


@router.get(
    "/",
    response_model=List[PricingJobRunResponse],
)
async def list_pricing_jobs(
    provider_type: Optional[str] = Query(None),
    job_status: Optional[str] = Query(
        None, alias="status",
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """List pricing job history."""
    query = select(PricingJobRun)

    if provider_type:
        query = query.where(
            PricingJobRun.provider_type == provider_type
        )
    if job_status:
        query = query.where(
            PricingJobRun.status == job_status
        )

    query = (
        query
        .order_by(PricingJobRun.started_at.desc())
        .offset(offset)
        .limit(limit)
    )

    result = await db.execute(query)
    jobs = result.scalars().all()
    return jobs


@router.post(
    "/trigger",
    response_model=PricingJobTriggerResponse,
)
async def trigger_pricing_update(
    request: PricingJobTriggerRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Trigger a manual pricing update (runs in background)."""
    # Check for already-running jobs
    running_result = await db.execute(
        select(PricingJobRun)
        .where(
            PricingJobRun.status.in_(
                ["running", "pending"]
            )
        )
        .limit(1)
    )
    if running_result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A pricing update is already in progress."
                " Please wait for it to complete."
            ),
        )

    # Validate GCP account if specified
    if request.gcp_pricing_account_id:
        gcp_result = await db.execute(
            select(CloudAccount).where(
                CloudAccount.id
                == request.gcp_pricing_account_id,
                CloudAccount.provider_type == "gcp",
                CloudAccount.is_active.is_(True),
            )
        )
        if gcp_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GCP cloud account not found or"
                " inactive",
            )

    # Determine which providers to update
    if request.provider_type:
        if request.provider_type not in VALID_PROVIDERS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Invalid provider_type:"
                    f" {request.provider_type}."
                    f" Must be one of {VALID_PROVIDERS}"
                ),
            )
        providers = [request.provider_type]
    else:
        providers = VALID_PROVIDERS

    # Create pending job records
    job_ids: list[uuid.UUID] = []
    for ptype in providers:
        job = PricingJobRun(
            provider_type=ptype,
            status="pending",
            trigger="manual",
        )
        db.add(job)
        await db.flush()
        job_ids.append(job.id)

    await db.commit()

    # Launch background task
    gcp_acct_id = None
    if request.gcp_pricing_account_id:
        gcp_acct_id = str(request.gcp_pricing_account_id)

    background_tasks.add_task(
        _run_manual_pricing_update,
        job_ids,
        providers,
        gcp_acct_id,
    )

    provider_label = (
        request.provider_type.upper()
        if request.provider_type
        else "all providers"
    )
    return PricingJobTriggerResponse(
        job_ids=job_ids,
        message=(
            f"Pricing update triggered for"
            f" {provider_label}"
        ),
    )


@router.get(
    "/{job_id}",
    response_model=PricingJobRunResponse,
)
async def get_pricing_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Get a specific pricing job run."""
    result = await db.execute(
        select(PricingJobRun).where(
            PricingJobRun.id == job_id
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pricing job not found",
        )
    return job


async def _run_manual_pricing_update(
    job_ids: list[uuid.UUID],
    providers: list[str],
    gcp_pricing_account_id: str | None = None,
):
    """Background task for manual pricing updates."""
    if not scheduler_service.async_session:
        logger.error(
            "Scheduler not initialized — cannot run"
            " manual pricing update"
        )
        return

    async with scheduler_service.async_session() as db:
        for i, ptype in enumerate(providers):
            result = await db.execute(
                select(PricingJobRun).where(
                    PricingJobRun.id == job_ids[i]
                )
            )
            job = result.scalar_one_or_none()
            if not job:
                continue

            # Collect regions for this provider
            regions = (
                await
                scheduler_service
                ._collect_regions_for_provider(
                    db, ptype,
                )
            )

            if not regions:
                job.status = "completed"
                job.records_updated = 0
                job.error_message = (
                    "No regions found for this provider"
                )
                job.completed_at = datetime.now(
                    timezone.utc
                )
                job.duration_seconds = 0.0
                await db.commit()
                continue

            job.status = "running"
            job.regions_requested = len(regions)
            job.started_at = datetime.now(timezone.utc)
            await db.commit()

            try:
                # Get GCP credentials if needed
                gcp_json = None
                if ptype == "gcp":
                    gcp_json = await (
                        scheduler_service
                        ._get_gcp_credentials_json(
                            db, gcp_pricing_account_id,
                        )
                    )

                fetcher = PricingFetcher(
                    db, gcp_credentials_json=gcp_json,
                )
                region_list = sorted(list(regions))
                updated = await fetcher.update_pricing_db(
                    region_list, provider_type=ptype,
                )
                job.status = "completed"
                job.records_updated = updated
            except Exception as e:
                job.status = "failed"
                job.error_message = str(e)
                logger.error(
                    f"Manual pricing update failed for"
                    f" {ptype}: {e}",
                    exc_info=True,
                )
            finally:
                job.completed_at = datetime.now(
                    timezone.utc
                )
                job.duration_seconds = (
                    job.completed_at - job.started_at
                ).total_seconds()
                await db.commit()

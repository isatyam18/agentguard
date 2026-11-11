"""API routes for firewall policies."""

from typing import List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from agentguard.core.config import get_settings
from agentguard.core.database import get_db
from agentguard.core.errors import EntityNotFoundError
from agentguard.models.audit_log import AuditLog
from agentguard.models.policy import Policy
from agentguard.schemas.policy import PolicyCreate, PolicyResponse, PolicyUpdate

router = APIRouter(prefix="/policies", tags=["Policies"])


def verify_policy_admin(
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token"),
) -> None:
    """Verify administrator authorization for policy creation and modifications."""
    settings = get_settings()
    expected = settings.admin_api_key.get_secret_value()

    # If header provided, strictly validate token
    if x_admin_token is not None:
        if x_admin_token.strip() != expected:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid administrative credentials for policy management.",
            )
    elif settings.env == "production":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Administrative authentication (X-Admin-Token) required in production.",
        )


@router.post(
    "",
    response_model=PolicyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a firewall policy",
    dependencies=[Depends(verify_policy_admin)],
)
def create_policy(payload: PolicyCreate, db: Session = Depends(get_db)) -> Policy:
    """Create a new spending policy for the firewall."""
    policy = Policy(
        max_transaction_amount=payload.max_transaction_amount,
        daily_spending_limit=payload.daily_spending_limit,
        allowed_merchants=payload.allowed_merchants,
        require_human_approval=payload.require_human_approval,
        is_active=payload.is_active,
    )
    db.add(policy)
    db.flush()

    audit_entry = AuditLog(
        event_type="POLICY_CREATED",
        actor="admin:api",
        details={
            "policy_id": policy.id,
            "max_transaction_amount": str(policy.max_transaction_amount),
            "daily_spending_limit": str(policy.daily_spending_limit),
            "require_human_approval": policy.require_human_approval,
        },
    )
    db.add(audit_entry)
    db.commit()
    db.refresh(policy)
    return policy


@router.get(
    "",
    response_model=List[PolicyResponse],
    summary="List policies",
)
def list_policies(
    active_only: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> List[Policy]:
    """Retrieve all configured firewall policies."""
    query = select(Policy)
    if active_only:
        query = query.where(Policy.is_active.is_(True))
    return list(db.scalars(query).all())


@router.get(
    "/{policy_id}",
    response_model=PolicyResponse,
    summary="Get policy by ID",
)
def get_policy(policy_id: str, db: Session = Depends(get_db)) -> Policy:
    """Retrieve details for a specific firewall policy."""
    policy = db.get(Policy, policy_id)
    if not policy:
        raise EntityNotFoundError("Policy", policy_id)
    return policy


@router.patch(
    "/{policy_id}",
    response_model=PolicyResponse,
    summary="Update a policy",
    dependencies=[Depends(verify_policy_admin)],
)
def update_policy(
    policy_id: str, payload: PolicyUpdate, db: Session = Depends(get_db)
) -> Policy:
    """Partially update an existing policy."""
    policy = db.get(Policy, policy_id)
    if not policy:
        raise EntityNotFoundError("Policy", policy_id)

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(policy, field, value)

    audit_entry = AuditLog(
        event_type="POLICY_UPDATED",
        actor="admin:api",
        details={"policy_id": policy.id, "updated_fields": list(update_data.keys())},
    )
    db.add(audit_entry)
    db.commit()
    db.refresh(policy)
    return policy


@router.put(
    "/{policy_id}",
    response_model=PolicyResponse,
    summary="Replace or update a policy",
    dependencies=[Depends(verify_policy_admin)],
)
def replace_policy(
    policy_id: str, payload: PolicyUpdate, db: Session = Depends(get_db)
) -> Policy:
    """Update an existing policy (PUT compatibility alias for frontend clients)."""
    return update_policy(policy_id=policy_id, payload=payload, db=db)

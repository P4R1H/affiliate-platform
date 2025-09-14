"""
Client management endpoints.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session, selectinload
import time
from app.api.deps import get_db, require_admin
from app.models.db import Client, User, Campaign
from app.models.schemas.clients import ClientCreate, ClientRead, ClientUpdate, ClientWithUsers, ClientWithRelations
from app.models.schemas.base import ResponseBase
from app.utils import get_logger, log_business_event, log_performance

router = APIRouter()
logger = get_logger(__name__)

@router.post(
    "/",
    response_model=ClientRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create new client",
    description="Create a new client organization (admin only)"
)
async def create_client(
    client_data: ClientCreate,
    request: Request,
    admin=Depends(require_admin),
    db: Session = Depends(get_db)
) -> ClientRead:
    """Create a new client organization."""
    start_time = time.time()
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logger.info(
        "Client creation started",
        client_name=client_data.name,
        admin_id=admin.id,
        request_id=request_id
    )
    
    try:
        # Check for duplicate client name
        existing_client = db.query(Client).filter(Client.name == client_data.name).first()
        if existing_client:
            logger.warning(
                "Client creation failed: duplicate name",
                client_name=client_data.name,
                existing_client_id=existing_client.id,
                request_id=request_id
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Client with name '{client_data.name}' already exists"
            )
        
        # Create new client
        new_client = Client(
            name=client_data.name
        )
        
        db.add(new_client)
        db.commit()
        db.refresh(new_client)
        
        log_business_event(
            event_type="client_created",
            details={
                "client_id": new_client.id,
                "client_name": new_client.name,
                "created_by_admin_id": admin.id
            },
            user_id=admin.id,
            request_id=request_id
        )
        
        duration_ms = (time.time() - start_time) * 1000
        log_performance(
            operation="create_client",
            duration_ms=duration_ms,
            additional_data={"client_id": new_client.id}
        )
        
        logger.info(
            "Client created successfully",
            client_id=new_client.id,
            client_name=new_client.name,
            request_id=request_id
        )
        
        return ClientRead.model_validate(new_client)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Client creation failed with unexpected error",
            error=str(e),
            client_name=client_data.name,
            request_id=request_id,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create client"
        )

@router.get(
    "/",
    response_model=List[ClientWithUsers],
    summary="List all clients",
    description="Get list of all clients with user counts (admin only)"
)
async def list_clients(
    request: Request,
    admin=Depends(require_admin),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
) -> List[ClientWithUsers]:
    """Get list of all clients with user and campaign counts."""
    start_time = time.time()
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logger.info(
        "Client list request started",
        admin_id=admin.id,
        skip=skip,
        limit=limit,
        request_id=request_id
    )
    
    try:
        clients = db.query(Client).offset(skip).limit(limit).all()
        
        # Add user and campaign counts
        result = []
        for client in clients:
            user_count = db.query(User).filter(User.client_id == client.id).count()
            campaign_count = db.query(Campaign).filter(Campaign.client_id == client.id).count()
            
            # Create base client data using model_validate
            client_base = ClientRead.model_validate(client)
            client_data = ClientWithUsers(
                **client_base.model_dump(),
                user_count=user_count,
                campaign_count=campaign_count
            )
            result.append(client_data)
        
        duration_ms = (time.time() - start_time) * 1000
        log_performance(
            operation="list_clients",
            duration_ms=duration_ms,
            additional_data={"client_count": len(result)}
        )
        
        logger.info(
            "Client list retrieved successfully",
            client_count=len(result),
            request_id=request_id
        )
        
        return result
        
    except Exception as e:
        logger.error(
            "Client list retrieval failed",
            error=str(e),
            request_id=request_id,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve clients"
        )

@router.get(
    "/{client_id}",
    response_model=ClientWithRelations,
    summary="Get client details",
    description="Get detailed client information with users and campaigns (admin only)"
)
async def get_client(
    client_id: int,
    request: Request,
    admin=Depends(require_admin),
    db: Session = Depends(get_db)
) -> ClientWithRelations:
    """Get detailed client information."""
    start_time = time.time()
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logger.info(
        "Client detail request started",
        client_id=client_id,
        admin_id=admin.id,
        request_id=request_id
    )
    
    try:
        client = db.query(Client).options(
            selectinload(Client.users),
            selectinload(Client.campaigns)
        ).filter(Client.id == client_id).first()
        
        if not client:
            logger.warning(
                "Client not found",
                client_id=client_id,
                request_id=request_id
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Client with ID {client_id} not found"
            )
        
        duration_ms = (time.time() - start_time) * 1000
        log_performance(
            operation="get_client",
            duration_ms=duration_ms,
            additional_data={"client_id": client_id}
        )
        
        logger.info(
            "Client details retrieved successfully",
            client_id=client_id,
            user_count=len(client.users),
            campaign_count=len(client.campaigns),
            request_id=request_id
        )
        
        return ClientWithRelations.model_validate(client)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Client detail retrieval failed",
            error=str(e),
            client_id=client_id,
            request_id=request_id,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve client details"
        )

@router.put(
    "/{client_id}",
    response_model=ClientRead,
    summary="Update client",
    description="Update client information (admin only)"
)
async def update_client(
    client_id: int,
    client_data: ClientUpdate,
    request: Request,
    admin=Depends(require_admin),
    db: Session = Depends(get_db)
) -> ClientRead:
    """Update client information."""
    start_time = time.time()
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logger.info(
        "Client update started",
        client_id=client_id,
        admin_id=admin.id,
        request_id=request_id
    )
    
    try:
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            logger.warning(
                "Client update failed: not found",
                client_id=client_id,
                request_id=request_id
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Client with ID {client_id} not found"
            )
        
        # Update fields
        update_data = client_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(client, field, value)
        
        db.commit()
        db.refresh(client)
        
        log_business_event(
            event_type="client_updated",
            details={
                "client_id": client.id,
                "client_name": client.name,
                "updated_by_admin_id": admin.id
            },
            user_id=admin.id,
            request_id=request_id
        )
        
        duration_ms = (time.time() - start_time) * 1000
        log_performance(
            operation="update_client",
            duration_ms=duration_ms,
            additional_data={"client_id": client_id}
        )
        
        logger.info(
            "Client updated successfully",
            client_id=client_id,
            request_id=request_id
        )
        
        return ClientRead.model_validate(client)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Client update failed",
            error=str(e),
            client_id=client_id,
            request_id=request_id,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update client"
        )

@router.delete(
    "/{client_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete client",
    description="Delete a client (admin only) - Will fail if client has users or campaigns"
)
async def delete_client(
    client_id: int,
    request: Request,
    admin=Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Delete a client."""
    start_time = time.time()
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logger.info(
        "Client deletion started",
        client_id=client_id,
        admin_id=admin.id,
        request_id=request_id
    )
    
    try:
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            logger.warning(
                "Client deletion failed: not found",
                client_id=client_id,
                request_id=request_id
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Client with ID {client_id} not found"
            )
        
        # Check for dependent records
        user_count = db.query(User).filter(User.client_id == client_id).count()
        campaign_count = db.query(Campaign).filter(Campaign.client_id == client_id).count()
        
        if user_count > 0 or campaign_count > 0:
            logger.warning(
                "Client deletion failed: has dependent records",
                client_id=client_id,
                user_count=user_count,
                campaign_count=campaign_count,
                request_id=request_id
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot delete client: has {user_count} users and {campaign_count} campaigns"
            )
        
        client_name = client.name
        db.delete(client)
        db.commit()
        
        log_business_event(
            event_type="client_deleted",
            details={
                "client_id": client_id,
                "client_name": client_name,
                "deleted_by_admin_id": admin.id
            },
            user_id=admin.id,
            request_id=request_id
        )
        
        duration_ms = (time.time() - start_time) * 1000
        log_performance(
            operation="delete_client",
            duration_ms=duration_ms,
            additional_data={"client_id": client_id}
        )
        
        logger.info(
            "Client deleted successfully",
            client_id=client_id,
            client_name=client_name,
            request_id=request_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Client deletion failed",
            error=str(e),
            client_id=client_id,
            request_id=request_id,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete client"
        )
# backend/modules/sms/routers/template_router.py

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from sqlalchemy.orm import Session

from core.database import get_db
from core.auth import get_current_user
from modules.sms.services.template_service import SMSTemplateService
from modules.sms.schemas.sms_schemas import (
    SMSTemplateCreate, SMSTemplateUpdate, SMSTemplateResponse
)
from modules.sms.models.sms_models import SMSTemplateCategory

router = APIRouter(prefix="/api/v1/sms/templates", tags=["SMS Templates"])


@router.post("/", response_model=SMSTemplateResponse)
async def create_template(
    template_data: SMSTemplateCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create a new SMS template"""
    try:
        template_service = SMSTemplateService(db)
        template = template_service.create_template(template_data, current_user.id)
        return template
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create template: {str(e)}")


@router.get("/", response_model=List[SMSTemplateResponse])
async def list_templates(
    category: Optional[SMSTemplateCategory] = Query(None),
    is_active: Optional[bool] = Query(True),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """List SMS templates with filters"""
    template_service = SMSTemplateService(db)
    templates = template_service.list_templates(
        category=category,
        is_active=is_active,
        limit=limit,
        offset=offset
    )
    return templates


@router.get("/{template_id}", response_model=SMSTemplateResponse)
async def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get a specific SMS template"""
    template_service = SMSTemplateService(db)
    template = template_service.get_template(template_id)
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return template


@router.get("/name/{template_name}", response_model=SMSTemplateResponse)
async def get_template_by_name(
    template_name: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get a template by name"""
    template_service = SMSTemplateService(db)
    template = template_service.get_template_by_name(template_name)
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return template


@router.put("/{template_id}", response_model=SMSTemplateResponse)
async def update_template(
    template_id: int,
    template_data: SMSTemplateUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update an SMS template"""
    try:
        template_service = SMSTemplateService(db)
        template = template_service.update_template(template_id, template_data, current_user.id)
        return template
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update template: {str(e)}")


@router.delete("/{template_id}")
async def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Delete (deactivate) an SMS template"""
    try:
        template_service = SMSTemplateService(db)
        success = template_service.delete_template(template_id)
        return {"success": success, "message": "Template deactivated"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete template: {str(e)}")


@router.post("/{template_id}/preview")
async def preview_template(
    template_id: int,
    variables: dict,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Preview a template with variables"""
    try:
        template_service = SMSTemplateService(db)
        rendered = template_service.render_template(template_id, variables)
        
        # Calculate segments
        segments = template_service._calculate_segments(rendered)
        
        return {
            "template_id": template_id,
            "rendered_message": rendered,
            "character_count": len(rendered),
            "estimated_segments": segments
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to preview template: {str(e)}")


@router.post("/create-defaults")
async def create_default_templates(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create default SMS templates"""
    try:
        template_service = SMSTemplateService(db)
        templates = template_service.create_default_templates()
        return {
            "success": True,
            "created_count": len(templates),
            "templates": [t.name for t in templates]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create default templates: {str(e)}")
# backend/modules/sms/services/template_service.py

import logging
import re
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_

from modules.sms.models.sms_models import SMSTemplate, SMSTemplateCategory
from modules.sms.schemas.sms_schemas import SMSTemplateCreate, SMSTemplateUpdate

logger = logging.getLogger(__name__)


class SMSTemplateService:
    """Service for managing SMS templates"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_template(
        self,
        template_data: SMSTemplateCreate,
        user_id: Optional[int] = None
    ) -> SMSTemplate:
        """
        Create a new SMS template
        
        Args:
            template_data: Template creation data
            user_id: ID of the user creating the template
        
        Returns:
            Created SMSTemplate
        """
        # Check for duplicate name
        existing = self.db.query(SMSTemplate).filter(
            SMSTemplate.name == template_data.name
        ).first()
        
        if existing:
            raise ValueError(f"Template with name '{template_data.name}' already exists")
        
        # Extract variables from template body
        variables = self._extract_variables(template_data.template_body)
        
        # Calculate estimated segments
        estimated_segments = self._calculate_segments(template_data.template_body)
        
        template = SMSTemplate(
            name=template_data.name,
            category=template_data.category,
            description=template_data.description,
            template_body=template_data.template_body,
            variables=variables or template_data.variables,
            is_active=template_data.is_active,
            max_length=template_data.max_length,
            estimated_segments=estimated_segments,
            created_by=user_id
        )
        
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        
        logger.info(f"Created SMS template: {template.name}")
        return template
    
    def update_template(
        self,
        template_id: int,
        template_data: SMSTemplateUpdate,
        user_id: Optional[int] = None
    ) -> SMSTemplate:
        """
        Update an existing SMS template
        
        Args:
            template_id: ID of the template to update
            template_data: Updated template data
            user_id: ID of the user updating the template
        
        Returns:
            Updated SMSTemplate
        """
        template = self.db.query(SMSTemplate).filter(
            SMSTemplate.id == template_id
        ).first()
        
        if not template:
            raise ValueError(f"Template with ID {template_id} not found")
        
        # Create a new version if template body changes
        if template_data.template_body and template_data.template_body != template.template_body:
            # Archive current version
            template.is_active = False
            self.db.commit()
            
            # Create new version
            new_template = SMSTemplate(
                name=template_data.name or template.name,
                category=template.category,
                description=template_data.description or template.description,
                template_body=template_data.template_body,
                variables=self._extract_variables(template_data.template_body),
                is_active=template_data.is_active if template_data.is_active is not None else True,
                max_length=template_data.max_length or template.max_length,
                estimated_segments=self._calculate_segments(template_data.template_body),
                version=template.version + 1,
                parent_template_id=template.parent_template_id or template.id,
                created_by=user_id
            )
            
            self.db.add(new_template)
            self.db.commit()
            self.db.refresh(new_template)
            
            logger.info(f"Created new version of template: {new_template.name} v{new_template.version}")
            return new_template
        
        # Update existing template for minor changes
        if template_data.name:
            template.name = template_data.name
        if template_data.description:
            template.description = template_data.description
        if template_data.is_active is not None:
            template.is_active = template_data.is_active
        if template_data.max_length:
            template.max_length = template_data.max_length
        
        self.db.commit()
        self.db.refresh(template)
        
        logger.info(f"Updated SMS template: {template.name}")
        return template
    
    def get_template(self, template_id: int) -> Optional[SMSTemplate]:
        """Get a template by ID"""
        return self.db.query(SMSTemplate).filter(
            SMSTemplate.id == template_id
        ).first()
    
    def get_template_by_name(self, name: str) -> Optional[SMSTemplate]:
        """Get a template by name"""
        return self.db.query(SMSTemplate).filter(
            and_(
                SMSTemplate.name == name,
                SMSTemplate.is_active == True
            )
        ).first()
    
    def list_templates(
        self,
        category: Optional[SMSTemplateCategory] = None,
        is_active: Optional[bool] = True,
        limit: int = 100,
        offset: int = 0
    ) -> List[SMSTemplate]:
        """
        List SMS templates with filters
        
        Args:
            category: Filter by category
            is_active: Filter by active status
            limit: Maximum number of results
            offset: Pagination offset
        
        Returns:
            List of SMS templates
        """
        query = self.db.query(SMSTemplate)
        
        if category:
            query = query.filter(SMSTemplate.category == category)
        
        if is_active is not None:
            query = query.filter(SMSTemplate.is_active == is_active)
        
        return query.order_by(SMSTemplate.name).offset(offset).limit(limit).all()
    
    def render_template(
        self,
        template_id: int,
        variables: Dict[str, Any]
    ) -> str:
        """
        Render a template with variables
        
        Args:
            template_id: ID of the template
            variables: Dictionary of variable values
        
        Returns:
            Rendered message body
        """
        template = self.get_template(template_id)
        
        if not template:
            raise ValueError(f"Template with ID {template_id} not found")
        
        if not template.is_active:
            raise ValueError(f"Template '{template.name}' is not active")
        
        # Render template
        message_body = template.template_body
        
        # Replace variables
        for var_name, var_value in variables.items():
            placeholder = f"{{{{{var_name}}}}}"
            message_body = message_body.replace(placeholder, str(var_value))
        
        # Check for missing variables
        remaining_vars = self._extract_variables(message_body)
        if remaining_vars:
            raise ValueError(f"Missing template variables: {remaining_vars}")
        
        # Update usage tracking
        template.usage_count += 1
        template.last_used_at = datetime.utcnow()
        self.db.commit()
        
        return message_body
    
    def delete_template(self, template_id: int) -> bool:
        """
        Soft delete a template (mark as inactive)
        
        Args:
            template_id: ID of the template to delete
        
        Returns:
            True if deleted successfully
        """
        template = self.get_template(template_id)
        
        if not template:
            raise ValueError(f"Template with ID {template_id} not found")
        
        template.is_active = False
        self.db.commit()
        
        logger.info(f"Deactivated SMS template: {template.name}")
        return True
    
    def _extract_variables(self, template_body: str) -> List[str]:
        """Extract variable names from template body"""
        pattern = r'\{\{(\w+)\}\}'
        variables = re.findall(pattern, template_body)
        return list(set(variables))  # Remove duplicates
    
    def _calculate_segments(self, message_body: str) -> int:
        """Calculate number of SMS segments for a message"""
        # GSM 7-bit encoding: 160 chars for 1 segment, 153 for multi-segment
        # Unicode: 70 chars for 1 segment, 67 for multi-segment
        
        # Check if message contains Unicode characters
        try:
            message_body.encode('ascii')
            is_unicode = False
        except UnicodeEncodeError:
            is_unicode = True
        
        message_length = len(message_body)
        
        if is_unicode:
            if message_length <= 70:
                return 1
            else:
                return (message_length - 1) // 67 + 1
        else:
            if message_length <= 160:
                return 1
            else:
                return (message_length - 1) // 153 + 1
    
    def create_default_templates(self) -> List[SMSTemplate]:
        """Create default SMS templates"""
        default_templates = [
            {
                'name': 'reservation_confirmation',
                'category': SMSTemplateCategory.RESERVATION,
                'description': 'Reservation confirmation message',
                'template_body': 'Hi {{customer_name}}, your reservation for {{party_size}} at {{restaurant_name}} on {{date}} at {{time}} is confirmed. Confirmation code: {{confirmation_code}}'
            },
            {
                'name': 'reservation_reminder',
                'category': SMSTemplateCategory.REMINDER,
                'description': 'Reservation reminder message',
                'template_body': 'Reminder: You have a reservation for {{party_size}} at {{restaurant_name}} today at {{time}}. See you soon!'
            },
            {
                'name': 'order_ready',
                'category': SMSTemplateCategory.ORDER,
                'description': 'Order ready for pickup',
                'template_body': 'Hi {{customer_name}}, your order #{{order_number}} is ready for pickup at {{restaurant_name}}!'
            },
            {
                'name': 'order_delivered',
                'category': SMSTemplateCategory.ORDER,
                'description': 'Order delivered confirmation',
                'template_body': 'Your order #{{order_number}} has been delivered. Thank you for choosing {{restaurant_name}}!'
            },
            {
                'name': 'authentication_code',
                'category': SMSTemplateCategory.AUTHENTICATION,
                'description': 'Two-factor authentication code',
                'template_body': 'Your {{restaurant_name}} verification code is: {{code}}. This code expires in 10 minutes.'
            },
            {
                'name': 'marketing_promotion',
                'category': SMSTemplateCategory.MARKETING,
                'description': 'Marketing promotion message',
                'template_body': '{{restaurant_name}}: {{promotion_text}} Use code {{promo_code}} to save {{discount}}% on your next order! Reply STOP to opt out.'
            }
        ]
        
        created_templates = []
        
        for template_data in default_templates:
            try:
                existing = self.get_template_by_name(template_data['name'])
                if not existing:
                    template = self.create_template(
                        SMSTemplateCreate(**template_data, is_active=True)
                    )
                    created_templates.append(template)
                    logger.info(f"Created default template: {template.name}")
            except Exception as e:
                logger.error(f"Error creating default template {template_data['name']}: {str(e)}")
        
        return created_templates
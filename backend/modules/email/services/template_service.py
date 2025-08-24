# backend/modules/email/services/template_service.py

import logging
import re
from typing import Optional, Dict, Any, List, Set
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_
from jinja2 import Template, Environment, select_autoescape, TemplateError

from modules.email.models.email_models import EmailTemplate, EmailTemplateCategory
from modules.email.schemas.email_schemas import EmailTemplateCreate, EmailTemplateUpdate

logger = logging.getLogger(__name__)


class EmailTemplateService:
    """Service for managing email templates"""
    
    def __init__(self, db: Session):
        self.db = db
        
        # Initialize Jinja2 environment with auto-escaping
        self.jinja_env = Environment(
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
    
    def create_template(
        self,
        template_data: EmailTemplateCreate,
        user_id: Optional[int] = None
    ) -> EmailTemplate:
        """
        Create a new email template
        
        Args:
            template_data: Template creation data
            user_id: ID of the user creating the template
        
        Returns:
            Created EmailTemplate
        """
        # Check for duplicate name
        existing = self.db.query(EmailTemplate).filter(
            EmailTemplate.name == template_data.name
        ).first()
        
        if existing:
            raise ValueError(f"Template with name '{template_data.name}' already exists")
        
        # Extract variables from templates
        variables = self._extract_all_variables(
            template_data.subject_template,
            template_data.html_body_template,
            template_data.text_body_template
        )
        
        # Validate templates
        self._validate_template(template_data.subject_template, "subject")
        self._validate_template(template_data.html_body_template, "html_body")
        if template_data.text_body_template:
            self._validate_template(template_data.text_body_template, "text_body")
        
        # Create template
        template = EmailTemplate(
            name=template_data.name,
            description=template_data.description,
            category=template_data.category,
            subject_template=template_data.subject_template,
            html_body_template=template_data.html_body_template,
            text_body_template=template_data.text_body_template,
            sendgrid_template_id=template_data.sendgrid_template_id,
            ses_template_name=template_data.ses_template_name,
            variables=list(variables),
            default_values=template_data.default_values,
            is_active=template_data.is_active,
            is_transactional=template_data.is_transactional,
            created_by=user_id
        )
        
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        
        logger.info(f"Created email template: {template.name} (ID: {template.id})")
        return template
    
    def update_template(
        self,
        template_id: int,
        template_data: EmailTemplateUpdate,
        user_id: Optional[int] = None
    ) -> EmailTemplate:
        """
        Update an existing email template
        
        Args:
            template_id: ID of template to update
            template_data: Update data
            user_id: ID of the user updating the template
        
        Returns:
            Updated EmailTemplate
        """
        template = self.db.query(EmailTemplate).filter(
            EmailTemplate.id == template_id
        ).first()
        
        if not template:
            raise ValueError(f"Template with ID {template_id} not found")
        
        # Check for duplicate name if changing
        if template_data.name and template_data.name != template.name:
            existing = self.db.query(EmailTemplate).filter(
                and_(
                    EmailTemplate.name == template_data.name,
                    EmailTemplate.id != template_id
                )
            ).first()
            
            if existing:
                raise ValueError(f"Template with name '{template_data.name}' already exists")
        
        # Update fields
        update_data = template_data.model_dump(exclude_unset=True)
        
        # If updating any template content, re-extract variables
        if any(field in update_data for field in ['subject_template', 'html_body_template', 'text_body_template']):
            subject = update_data.get('subject_template', template.subject_template)
            html_body = update_data.get('html_body_template', template.html_body_template)
            text_body = update_data.get('text_body_template', template.text_body_template)
            
            # Validate templates
            self._validate_template(subject, "subject")
            self._validate_template(html_body, "html_body")
            if text_body:
                self._validate_template(text_body, "text_body")
            
            variables = self._extract_all_variables(subject, html_body, text_body)
            update_data['variables'] = list(variables)
        
        for field, value in update_data.items():
            setattr(template, field, value)
        
        self.db.commit()
        self.db.refresh(template)
        
        logger.info(f"Updated email template: {template.name} (ID: {template.id})")
        return template
    
    def get_template(self, template_id: int) -> Optional[EmailTemplate]:
        """Get template by ID"""
        return self.db.query(EmailTemplate).filter(
            EmailTemplate.id == template_id
        ).first()
    
    def get_template_by_name(self, name: str) -> Optional[EmailTemplate]:
        """Get template by name"""
        return self.db.query(EmailTemplate).filter(
            EmailTemplate.name == name
        ).first()
    
    def list_templates(
        self,
        category: Optional[EmailTemplateCategory] = None,
        is_active: Optional[bool] = None,
        is_transactional: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[EmailTemplate]:
        """
        List templates with filters
        
        Args:
            category: Filter by category
            is_active: Filter by active status
            is_transactional: Filter by transactional status
            limit: Maximum number of results
            offset: Pagination offset
        
        Returns:
            List of templates
        """
        query = self.db.query(EmailTemplate)
        
        if category:
            query = query.filter(EmailTemplate.category == category)
        
        if is_active is not None:
            query = query.filter(EmailTemplate.is_active == is_active)
        
        if is_transactional is not None:
            query = query.filter(EmailTemplate.is_transactional == is_transactional)
        
        return query.order_by(EmailTemplate.name).offset(offset).limit(limit).all()
    
    def render_template(
        self,
        template_id: int,
        variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Render template with variables
        
        Args:
            template_id: Template ID
            variables: Variables to substitute
        
        Returns:
            Dict with rendered subject, html_body, text_body, and template
        """
        template = self.get_template(template_id)
        
        if not template:
            raise ValueError(f"Template with ID {template_id} not found")
        
        if not template.is_active:
            raise ValueError(f"Template '{template.name}' is not active")
        
        # Merge with default values
        render_vars = {}
        if template.default_values:
            render_vars.update(template.default_values)
        render_vars.update(variables)
        
        try:
            # Render subject
            subject_template = self.jinja_env.from_string(template.subject_template)
            subject = subject_template.render(**render_vars)
            
            # Render HTML body
            html_template = self.jinja_env.from_string(template.html_body_template)
            html_body = html_template.render(**render_vars)
            
            # Render text body if present
            text_body = None
            if template.text_body_template:
                text_template = self.jinja_env.from_string(template.text_body_template)
                text_body = text_template.render(**render_vars)
            
            return {
                'subject': subject,
                'html_body': html_body,
                'text_body': text_body,
                'template': template
            }
            
        except TemplateError as e:
            logger.error(f"Error rendering template {template.name}: {str(e)}")
            raise ValueError(f"Template rendering error: {str(e)}")
    
    def _extract_all_variables(
        self,
        subject: str,
        html_body: str,
        text_body: Optional[str]
    ) -> Set[str]:
        """Extract all variables from templates"""
        variables = set()
        
        variables.update(self._extract_variables(subject))
        variables.update(self._extract_variables(html_body))
        if text_body:
            variables.update(self._extract_variables(text_body))
        
        return variables
    
    def _extract_variables(self, template_string: str) -> Set[str]:
        """
        Extract Jinja2 variables from template string
        
        Args:
            template_string: Template content
        
        Returns:
            Set of variable names
        """
        # Pattern to match {{ variable }} and {{ variable.attribute }}
        pattern = r'\{\{\s*(\w+)(?:\.\w+)*\s*\}\}'
        matches = re.findall(pattern, template_string)
        
        # Also look for control structures like {% for item in items %}
        control_pattern = r'\{%\s*for\s+\w+\s+in\s+(\w+)\s*%\}'
        control_matches = re.findall(control_pattern, template_string)
        
        return set(matches + control_matches)
    
    def _validate_template(self, template_string: str, template_type: str) -> None:
        """
        Validate template syntax
        
        Args:
            template_string: Template content
            template_type: Type of template (for error messages)
        
        Raises:
            ValueError: If template is invalid
        """
        try:
            self.jinja_env.from_string(template_string)
        except TemplateError as e:
            raise ValueError(f"Invalid {template_type} template: {str(e)}")
    
    def delete_template(self, template_id: int) -> bool:
        """
        Delete a template (soft delete by marking inactive)
        
        Args:
            template_id: Template ID
        
        Returns:
            True if successful
        """
        template = self.get_template(template_id)
        
        if not template:
            return False
        
        template.is_active = False
        self.db.commit()
        
        logger.info(f"Deactivated email template: {template.name} (ID: {template.id})")
        return True
    
    def clone_template(
        self,
        template_id: int,
        new_name: str,
        user_id: Optional[int] = None
    ) -> EmailTemplate:
        """
        Clone an existing template
        
        Args:
            template_id: ID of template to clone
            new_name: Name for the new template
            user_id: ID of the user creating the clone
        
        Returns:
            New EmailTemplate
        """
        source_template = self.get_template(template_id)
        
        if not source_template:
            raise ValueError(f"Template with ID {template_id} not found")
        
        # Create new template with cloned data
        template_data = EmailTemplateCreate(
            name=new_name,
            description=f"Cloned from {source_template.name}",
            category=source_template.category,
            subject_template=source_template.subject_template,
            html_body_template=source_template.html_body_template,
            text_body_template=source_template.text_body_template,
            variables=source_template.variables,
            default_values=source_template.default_values,
            is_active=True,
            is_transactional=source_template.is_transactional
        )
        
        return self.create_template(template_data, user_id)
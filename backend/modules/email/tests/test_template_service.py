# backend/modules/email/tests/test_template_service.py

"""
Unit tests for template service
"""

import pytest
from unittest.mock import Mock, patch
from modules.email.services.template_service import TemplateService
from modules.email.models.email_models import EmailTemplate
from modules.email.schemas.email_schemas import EmailTemplateCreate, EmailTemplateUpdate


class TestTemplateService:
    """Test template service functionality"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        db = Mock()
        db.query = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.refresh = Mock()
        return db
    
    @pytest.fixture
    def template_service(self, mock_db):
        """Create template service instance"""
        return TemplateService(mock_db)
    
    @pytest.fixture
    def sample_template(self):
        """Sample email template"""
        template = Mock(spec=EmailTemplate)
        template.id = 1
        template.name = "test_template"
        template.subject = "Test Subject {{name}}"
        template.body_html = "<h1>Hello {{name}}</h1>"
        template.body_text = "Hello {{name}}"
        template.category = "transactional"
        template.is_active = True
        template.variables = {"name": "string"}
        return template
    
    def test_render_template(self, template_service, sample_template):
        """Test template rendering with variables"""
        variables = {"name": "John Doe"}
        
        rendered = template_service.render_template(sample_template, variables)
        
        assert rendered["subject"] == "Test Subject John Doe"
        assert rendered["body_html"] == "<h1>Hello John Doe</h1>"
        assert rendered["body_text"] == "Hello John Doe"
    
    def test_render_template_missing_variable(self, template_service, sample_template):
        """Test template rendering with missing variable"""
        variables = {}  # Missing 'name' variable
        
        # Should not raise error, Jinja2 will leave variable blank
        rendered = template_service.render_template(sample_template, variables)
        
        assert rendered["subject"] == "Test Subject "
        assert rendered["body_html"] == "<h1>Hello </h1>"
        assert rendered["body_text"] == "Hello "
    
    def test_render_template_with_conditional(self, template_service):
        """Test template with conditional logic"""
        template = Mock(spec=EmailTemplate)
        template.subject = "Order Update"
        template.body_html = """
        {% if status == 'completed' %}
        <h1>Your order is complete!</h1>
        {% else %}
        <h1>Your order is {{status}}</h1>
        {% endif %}
        """
        template.body_text = "Order status: {{status}}"
        
        # Test with completed status
        variables = {"status": "completed"}
        rendered = template_service.render_template(template, variables)
        assert "Your order is complete!" in rendered["body_html"]
        
        # Test with other status
        variables = {"status": "preparing"}
        rendered = template_service.render_template(template, variables)
        assert "Your order is preparing" in rendered["body_html"]
    
    def test_get_template_by_name(self, template_service, mock_db, sample_template):
        """Test getting template by name"""
        mock_db.query().filter().first.return_value = sample_template
        
        result = template_service.get_template_by_name("test_template")
        
        assert result == sample_template
        mock_db.query().filter.assert_called_once()
    
    def test_get_template_by_name_not_found(self, template_service, mock_db):
        """Test getting non-existent template"""
        mock_db.query().filter().first.return_value = None
        
        result = template_service.get_template_by_name("non_existent")
        
        assert result is None
    
    def test_create_template(self, template_service, mock_db):
        """Test creating new template"""
        template_data = EmailTemplateCreate(
            name="new_template",
            subject="New Subject",
            body_html="<h1>New</h1>",
            body_text="New",
            category="marketing"
        )
        
        result = template_service.create_template(template_data)
        
        assert isinstance(result, EmailTemplate)
        assert result.name == "new_template"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
    
    def test_update_template(self, template_service, mock_db, sample_template):
        """Test updating template"""
        mock_db.query().filter().first.return_value = sample_template
        
        update_data = EmailTemplateUpdate(
            subject="Updated Subject",
            is_active=False
        )
        
        result = template_service.update_template(1, update_data)
        
        assert result == sample_template
        assert sample_template.subject == "Updated Subject"
        assert sample_template.is_active == False
        mock_db.commit.assert_called_once()
    
    def test_delete_template(self, template_service, mock_db, sample_template):
        """Test deleting template"""
        mock_db.query().filter().first.return_value = sample_template
        mock_db.delete = Mock()
        
        result = template_service.delete_template(1)
        
        assert result == True
        mock_db.delete.assert_called_once_with(sample_template)
        mock_db.commit.assert_called_once()
    
    def test_list_templates(self, template_service, mock_db):
        """Test listing templates with filters"""
        mock_templates = [Mock(spec=EmailTemplate) for _ in range(3)]
        mock_query = mock_db.query()
        mock_query.filter.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_templates
        
        result = template_service.list_templates(
            category="transactional",
            is_active=True,
            skip=0,
            limit=10
        )
        
        assert len(result) == 3
        assert mock_query.filter.called
    
    def test_validate_template_variables(self, template_service):
        """Test template variable validation"""
        template_content = "Hello {{name}}, your order {{order_id}} is ready!"
        
        variables = template_service.validate_template_variables(template_content)
        
        assert "name" in variables
        assert "order_id" in variables
        assert len(variables) == 2
    
    def test_preview_template(self, template_service, mock_db, sample_template):
        """Test template preview"""
        mock_db.query().filter().first.return_value = sample_template
        
        preview_data = {"name": "Preview User"}
        result = template_service.preview_template(1, preview_data)
        
        assert result["subject"] == "Test Subject Preview User"
        assert result["body_html"] == "<h1>Hello Preview User</h1>"
        assert result["body_text"] == "Hello Preview User"
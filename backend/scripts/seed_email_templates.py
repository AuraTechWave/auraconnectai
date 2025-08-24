# backend/scripts/seed_email_templates.py

"""
Script to seed email templates into the database
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from core.database import SessionLocal, engine
from modules.email.models.email_models import EmailTemplate
from modules.email.templates.base_templates import EMAIL_TEMPLATES
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_email_templates(db: Session):
    """Seed email templates from base_templates.py"""
    
    for template_data in EMAIL_TEMPLATES:
        # Check if template already exists
        existing = db.query(EmailTemplate).filter(
            EmailTemplate.name == template_data["name"]
        ).first()
        
        if existing:
            logger.info(f"Template '{template_data['name']}' already exists, updating...")
            # Update existing template
            for key, value in template_data.items():
                setattr(existing, key, value)
        else:
            logger.info(f"Creating template '{template_data['name']}'...")
            # Create new template
            template = EmailTemplate(**template_data)
            db.add(template)
    
    db.commit()
    logger.info("Email templates seeded successfully!")


def main():
    """Main function"""
    db = SessionLocal()
    
    try:
        seed_email_templates(db)
    except Exception as e:
        logger.error(f"Error seeding templates: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
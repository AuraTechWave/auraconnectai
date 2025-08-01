# backend/modules/feedback/services/moderation_service.py

import re
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc

from modules.feedback.models.feedback_models import (
    Review, Feedback, ReviewStatus, FeedbackStatus, SentimentScore
)
from modules.feedback.services.sentiment_service import sentiment_service
from core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ModerationResult:
    """Result of content moderation"""
    action: str  # approve, reject, flag, review
    confidence: float
    reasons: List[str]
    auto_moderated: bool
    flagged_content: List[str]
    severity_score: float


class ContentModerationService:
    """Service for moderating reviews and feedback content"""
    
    def __init__(self, db: Session):
        self.db = db
        self.profanity_words = self._load_profanity_list()
        self.spam_patterns = self._load_spam_patterns()
        self.moderation_rules = self._load_moderation_rules()
    
    def moderate_review(
        self,
        review: Review,
        auto_moderate: bool = True
    ) -> ModerationResult:
        """Moderate a review for inappropriate content"""
        
        # Combine title and content for analysis
        content_to_check = ""
        if review.title:
            content_to_check += review.title + " "
        content_to_check += review.content
        
        # Run moderation checks
        moderation_result = self._analyze_content(
            content_to_check,
            {
                "content_type": "review",
                "rating": review.rating,
                "is_verified": review.is_verified_purchase,
                "review_type": review.review_type.value
            }
        )
        
        # Apply auto-moderation if enabled
        if auto_moderate:
            self._apply_auto_moderation(review, moderation_result)
        
        # Log moderation action
        logger.info(f"Moderated review {review.id}: {moderation_result.action} (confidence: {moderation_result.confidence})")
        
        return moderation_result
    
    def moderate_feedback(
        self,
        feedback: Feedback,
        auto_moderate: bool = True
    ) -> ModerationResult:
        """Moderate feedback for inappropriate content"""
        
        # Combine subject and message for analysis
        content_to_check = feedback.subject + " " + feedback.message
        
        # Run moderation checks
        moderation_result = self._analyze_content(
            content_to_check,
            {
                "content_type": "feedback",
                "feedback_type": feedback.feedback_type.value,
                "priority": feedback.priority.value
            }
        )
        
        # Apply auto-moderation if enabled
        if auto_moderate:
            self._apply_auto_moderation_feedback(feedback, moderation_result)
        
        # Log moderation action
        logger.info(f"Moderated feedback {feedback.id}: {moderation_result.action} (confidence: {moderation_result.confidence})")
        
        return moderation_result
    
    def bulk_moderate_reviews(
        self,
        review_ids: List[int],
        moderator_id: int,
        action: str,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Bulk moderate multiple reviews"""
        
        reviews = self.db.query(Review).filter(Review.id.in_(review_ids)).all()
        
        if not reviews:
            return {"success": False, "message": "No reviews found"}
        
        moderated_count = 0
        errors = []
        
        for review in reviews:
            try:
                if action == "approve":
                    review.status = ReviewStatus.APPROVED
                elif action == "reject":
                    review.status = ReviewStatus.REJECTED
                elif action == "flag":
                    review.status = ReviewStatus.FLAGGED
                elif action == "hide":
                    review.status = ReviewStatus.HIDDEN
                
                review.moderated_at = datetime.utcnow()
                review.moderated_by = moderator_id
                if notes:
                    review.moderation_notes = notes
                
                moderated_count += 1
                
            except Exception as e:
                errors.append(f"Review {review.id}: {str(e)}")
        
        self.db.commit()
        
        return {
            "success": True,
            "moderated_count": moderated_count,
            "total_requested": len(review_ids),
            "errors": errors
        }
    
    def get_moderation_queue(
        self,
        content_type: str = "review",
        priority: str = "all",
        page: int = 1,
        per_page: int = 20
    ) -> Dict[str, Any]:
        """Get items pending moderation"""
        
        if content_type == "review":
            query = self.db.query(Review).filter(
                Review.status.in_([ReviewStatus.PENDING, ReviewStatus.FLAGGED])
            )
            
            # Sort by priority (flagged first, then by sentiment, then by date)
            query = query.order_by(
                desc(Review.status == ReviewStatus.FLAGGED),
                desc(Review.sentiment_score == SentimentScore.VERY_NEGATIVE),
                desc(Review.created_at)
            )
            
        elif content_type == "feedback":
            query = self.db.query(Feedback).filter(
                Feedback.status == FeedbackStatus.NEW
            )
            
            if priority != "all":
                from modules.feedback.models.feedback_models import FeedbackPriority
                query = query.filter(Feedback.priority == FeedbackPriority(priority))
            
            # Sort by priority and date
            query = query.order_by(
                desc(Feedback.priority),
                desc(Feedback.created_at)
            )
        
        else:
            return {"error": "Invalid content type"}
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        offset = (page - 1) * per_page
        items = query.offset(offset).limit(per_page).all()
        
        # Format items for response
        formatted_items = []
        for item in items:
            if content_type == "review":
                formatted_items.append({
                    "id": item.id,
                    "type": "review",
                    "title": item.title,
                    "content": item.content[:200] + "..." if len(item.content) > 200 else item.content,
                    "rating": item.rating,
                    "status": item.status.value,
                    "sentiment": item.sentiment_score.value if item.sentiment_score else None,
                    "created_at": item.created_at,
                    "customer_id": item.customer_id
                })
            else:  # feedback
                formatted_items.append({
                    "id": item.id,
                    "type": "feedback",
                    "subject": item.subject,
                    "message": item.message[:200] + "..." if len(item.message) > 200 else item.message,
                    "feedback_type": item.feedback_type.value,
                    "priority": item.priority.value,
                    "status": item.status.value,
                    "created_at": item.created_at,
                    "customer_id": item.customer_id
                })
        
        return {
            "items": formatted_items,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": (total + per_page - 1) // per_page
            }
        }
    
    def get_moderation_stats(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get moderation statistics"""
        
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()
        
        # Review moderation stats
        review_stats = {}
        for status in ReviewStatus:
            count = self.db.query(Review).filter(
                and_(
                    Review.status == status,
                    Review.moderated_at.between(start_date, end_date)
                )
            ).count()
            review_stats[status.value] = count
        
        # Feedback moderation stats
        feedback_stats = {}
        for status in FeedbackStatus:
            count = self.db.query(Feedback).filter(
                and_(
                    Feedback.status == status,
                    Feedback.created_at.between(start_date, end_date)
                )
            ).count()
            feedback_stats[status.value] = count
        
        # Auto-moderation effectiveness
        total_reviews = self.db.query(Review).filter(
            Review.created_at.between(start_date, end_date)
        ).count()
        
        auto_approved = self.db.query(Review).filter(
            and_(
                Review.created_at.between(start_date, end_date),
                Review.status == ReviewStatus.APPROVED,
                Review.moderated_by.is_(None)  # Auto-moderated
            )
        ).count()
        
        auto_moderation_rate = (auto_approved / total_reviews * 100) if total_reviews > 0 else 0
        
        # Pending items
        pending_reviews = self.db.query(Review).filter(
            Review.status == ReviewStatus.PENDING
        ).count()
        
        pending_feedback = self.db.query(Feedback).filter(
            Feedback.status == FeedbackStatus.NEW
        ).count()
        
        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "review_moderation": review_stats,
            "feedback_moderation": feedback_stats,
            "auto_moderation_rate": round(auto_moderation_rate, 2),
            "pending_items": {
                "reviews": pending_reviews,
                "feedback": pending_feedback,
                "total": pending_reviews + pending_feedback
            },
            "efficiency_metrics": {
                "total_items_processed": sum(review_stats.values()) + sum(feedback_stats.values()),
                "auto_approved_percentage": round(auto_moderation_rate, 2)
            }
        }
    
    def _analyze_content(
        self,
        content: str,
        context: Dict[str, Any] = None
    ) -> ModerationResult:
        """Analyze content for moderation issues"""
        
        reasons = []
        flagged_content = []
        severity_scores = []
        
        # Check for profanity
        profanity_result = self._check_profanity(content)
        if profanity_result["found"]:
            reasons.append("contains_profanity")
            flagged_content.extend(profanity_result["words"])
            severity_scores.append(profanity_result["severity"])
        
        # Check for spam patterns
        spam_result = self._check_spam_patterns(content)
        if spam_result["is_spam"]:
            reasons.append("spam_detected")
            flagged_content.extend(spam_result["patterns"])
            severity_scores.append(spam_result["severity"])
        
        # Check for personal information
        pii_result = self._check_personal_information(content)
        if pii_result["found"]:
            reasons.append("contains_personal_info")
            flagged_content.extend(pii_result["items"])
            severity_scores.append(pii_result["severity"])
        
        # Check content quality
        quality_result = self._check_content_quality(content, context)
        if quality_result["low_quality"]:
            reasons.append("low_quality_content")
            severity_scores.append(quality_result["severity"])
        
        # Check for fake/suspicious content
        authenticity_result = self._check_authenticity(content, context)
        if authenticity_result["suspicious"]:
            reasons.append("suspicious_content")
            severity_scores.append(authenticity_result["severity"])
        
        # Calculate overall severity
        overall_severity = max(severity_scores) if severity_scores else 0.0
        
        # Determine action based on severity and rules
        action, confidence = self._determine_moderation_action(
            overall_severity, reasons, context
        )
        
        return ModerationResult(
            action=action,
            confidence=confidence,
            reasons=reasons,
            auto_moderated=True,
            flagged_content=flagged_content,
            severity_score=overall_severity
        )
    
    def _check_profanity(self, content: str) -> Dict[str, Any]:
        """Check for profane language"""
        
        content_lower = content.lower()
        found_words = []
        severity = 0.0
        
        for word, score in self.profanity_words.items():
            if word in content_lower:
                found_words.append(word)
                severity = max(severity, score)
        
        return {
            "found": len(found_words) > 0,
            "words": found_words,
            "severity": severity,
            "count": len(found_words)
        }
    
    def _check_spam_patterns(self, content: str) -> Dict[str, Any]:
        """Check for spam patterns"""
        
        matched_patterns = []
        severity = 0.0
        
        for pattern, score in self.spam_patterns.items():
            if re.search(pattern, content, re.IGNORECASE):
                matched_patterns.append(pattern)
                severity = max(severity, score)
        
        # Additional spam indicators
        # Excessive repetition
        words = content.lower().split()
        word_counts = {}
        for word in words:
            word_counts[word] = word_counts.get(word, 0) + 1
        
        max_repetition = max(word_counts.values()) if word_counts else 0
        if max_repetition > 5:
            matched_patterns.append("excessive_repetition")
            severity = max(severity, 0.6)
        
        # Excessive capitalization
        if len(content) > 20:
            caps_ratio = sum(1 for c in content if c.isupper()) / len(content)
            if caps_ratio > 0.7:
                matched_patterns.append("excessive_caps")
                severity = max(severity, 0.4)
        
        return {
            "is_spam": severity > 0.3,
            "patterns": matched_patterns,
            "severity": severity
        }
    
    def _check_personal_information(self, content: str) -> Dict[str, Any]:
        """Check for personal information that should be redacted"""
        
        found_items = []
        severity = 0.0
        
        # Email patterns
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        if re.search(email_pattern, content):
            found_items.append("email_address")
            severity = max(severity, 0.8)
        
        # Phone number patterns
        phone_patterns = [
            r'\b\d{3}-\d{3}-\d{4}\b',  # 123-456-7890
            r'\b\(\d{3}\)\s*\d{3}-\d{4}\b',  # (123) 456-7890
            r'\b\d{10}\b'  # 1234567890
        ]
        
        for pattern in phone_patterns:
            if re.search(pattern, content):
                found_items.append("phone_number")
                severity = max(severity, 0.8)
                break
        
        # Credit card patterns (basic)
        cc_pattern = r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'
        if re.search(cc_pattern, content):
            found_items.append("credit_card")
            severity = max(severity, 1.0)
        
        # Social security numbers
        ssn_pattern = r'\b\d{3}-\d{2}-\d{4}\b'
        if re.search(ssn_pattern, content):
            found_items.append("ssn")
            severity = max(severity, 1.0)
        
        return {
            "found": len(found_items) > 0,
            "items": found_items,
            "severity": severity
        }
    
    def _check_content_quality(self, content: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Check content quality"""
        
        quality_issues = []
        severity = 0.0
        
        # Length checks
        if len(content.strip()) < 10:
            quality_issues.append("too_short")
            severity = max(severity, 0.6)
        
        # Repetitive content
        if len(set(content.lower().split())) < len(content.split()) * 0.3:
            quality_issues.append("repetitive")
            severity = max(severity, 0.4)
        
        # No meaningful content (just symbols/numbers)
        meaningful_chars = sum(1 for c in content if c.isalpha())
        if meaningful_chars < len(content) * 0.5:
            quality_issues.append("no_meaningful_content")
            severity = max(severity, 0.7)
        
        # All caps (except if short)
        if len(content) > 20 and content.isupper():
            quality_issues.append("all_caps")
            severity = max(severity, 0.3)
        
        return {
            "low_quality": severity > 0.4,
            "issues": quality_issues,
            "severity": severity
        }
    
    def _check_authenticity(self, content: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Check for fake or suspicious content"""
        
        suspicious_indicators = []
        severity = 0.0
        
        # Generic/template-like content
        generic_phrases = [
            "this product is good",
            "i like this",
            "very good product",
            "recommend to everyone",
            "five stars"
        ]
        
        content_lower = content.lower()
        for phrase in generic_phrases:
            if phrase in content_lower:
                suspicious_indicators.append("generic_content")
                severity = max(severity, 0.3)
                break
        
        # Rating-content mismatch (if context available)
        if context and "rating" in context:
            # Analyze sentiment vs rating
            sentiment_result = sentiment_service.analyze_review_sentiment(
                type('MockReview', (), {
                    'title': '',
                    'content': content,
                    'rating': context["rating"],
                    'is_verified_purchase': context.get("is_verified", False),
                    'review_type': type('MockType', (), {'value': context.get("review_type", "product")})(),
                    'sentiment_score': None,
                    'sentiment_confidence': None,
                    'sentiment_analysis_data': None
                })()
            )
            
            rating = context["rating"]
            sentiment_score = sentiment_result.score
            
            # Check for major mismatches
            if rating >= 4.0 and sentiment_score in ["negative", "very_negative"]:
                suspicious_indicators.append("rating_sentiment_mismatch")
                severity = max(severity, 0.6)
            elif rating <= 2.0 and sentiment_score in ["positive", "very_positive"]:
                suspicious_indicators.append("rating_sentiment_mismatch")
                severity = max(severity, 0.6)
        
        return {
            "suspicious": severity > 0.4,
            "indicators": suspicious_indicators,
            "severity": severity
        }
    
    def _determine_moderation_action(
        self,
        severity: float,
        reasons: List[str],
        context: Dict[str, Any] = None
    ) -> Tuple[str, float]:
        """Determine what moderation action to take"""
        
        # High severity issues
        if severity >= 0.8:
            if "contains_personal_info" in reasons or "credit_card" in reasons:
                return "reject", 0.95
            if "contains_profanity" in reasons:
                return "flag", 0.9
        
        # Medium severity issues
        if severity >= 0.5:
            if "spam_detected" in reasons:
                return "reject", 0.8
            if "suspicious_content" in reasons:
                return "flag", 0.7
            return "review", 0.6
        
        # Low severity issues
        if severity >= 0.3:
            return "review", 0.5
        
        # No significant issues
        return "approve", 0.9
    
    def _apply_auto_moderation(self, review: Review, result: ModerationResult) -> None:
        """Apply auto-moderation action to a review"""
        
        if result.action == "approve":
            review.status = ReviewStatus.APPROVED
        elif result.action == "reject":
            review.status = ReviewStatus.REJECTED
        elif result.action == "flag":
            review.status = ReviewStatus.FLAGGED
        else:  # review
            review.status = ReviewStatus.PENDING
        
        # Add moderation metadata
        moderation_metadata = {
            "auto_moderated": True,
            "moderation_result": {
                "action": result.action,
                "confidence": result.confidence,
                "reasons": result.reasons,
                "severity": result.severity_score
            },
            "moderated_at": datetime.utcnow().isoformat()
        }
        
        review.metadata = {**(review.metadata or {}), **moderation_metadata}
        
        if result.action in ["reject", "flag"]:
            review.moderation_notes = f"Auto-moderated: {', '.join(result.reasons)}"
    
    def _apply_auto_moderation_feedback(self, feedback: Feedback, result: ModerationResult) -> None:
        """Apply auto-moderation action to feedback"""
        
        # Feedback doesn't have the same status options as reviews
        # We mainly use this for flagging and adding metadata
        
        if result.severity_score >= 0.8:
            # High severity - might need special handling
            feedback.priority = getattr(feedback, 'priority', None) or "high"
        
        # Add moderation metadata
        moderation_metadata = {
            "auto_moderated": True,
            "moderation_result": {
                "action": result.action,
                "confidence": result.confidence,
                "reasons": result.reasons,
                "severity": result.severity_score
            },
            "moderated_at": datetime.utcnow().isoformat()
        }
        
        feedback.metadata = {**(feedback.metadata or {}), **moderation_metadata}
    
    def _load_profanity_list(self) -> Dict[str, float]:
        """Load profanity words with severity scores"""
        
        # This would typically be loaded from a file or database
        return {
            # Mild profanity (0.3-0.5)
            "damn": 0.3, "hell": 0.3, "crap": 0.4,
            
            # Moderate profanity (0.6-0.8)
            "stupid": 0.6, "idiot": 0.6, "moron": 0.7,
            
            # Strong profanity (0.9-1.0)
            # Add actual profanity words as needed
        }
    
    def _load_spam_patterns(self) -> Dict[str, float]:
        """Load spam detection patterns with severity scores"""
        
        return {
            # Promotional patterns
            r'\b(buy now|click here|limited time|act fast)\b': 0.7,
            r'\b(free money|make money|work from home)\b': 0.8,
            r'\b(viagra|cialis|pharmacy)\b': 0.9,
            
            # Suspicious patterns
            r'www\.[a-zA-Z0-9-]+\.[a-z]{2,}': 0.5,  # URLs
            r'\b[A-Z]{5,}\b': 0.4,  # Excessive caps
            r'[!]{3,}': 0.3,  # Excessive punctuation
            
            # Fake review patterns
            r'\b(best product ever|changed my life|miracle)\b': 0.4,
            r'\b(must buy|everyone should|tell everyone)\b': 0.5
        }
    
    def _load_moderation_rules(self) -> Dict[str, Any]:
        """Load moderation rules configuration"""
        
        return {
            "auto_approve_threshold": 0.8,
            "auto_reject_threshold": 0.9,
            "require_human_review_threshold": 0.5,
            "escalate_to_supervisor_threshold": 0.95
        }


# Service factory function
def create_moderation_service(db: Session) -> ContentModerationService:
    """Create a moderation service instance"""
    return ContentModerationService(db)
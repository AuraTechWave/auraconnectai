# backend/modules/feedback/services/sentiment_service.py

import re
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime
import asyncio
import aiohttp
import json

from backend.modules.feedback.models.feedback_models import (
    Review, Feedback, SentimentScore
)
from backend.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class SentimentResult:
    """Sentiment analysis result"""
    score: SentimentScore
    confidence: float
    raw_data: Dict[str, Any]
    processing_time_ms: float


class SentimentAnalysisService:
    """Service for analyzing sentiment of reviews and feedback"""
    
    def __init__(self):
        self.sentiment_keywords = self._load_sentiment_keywords()
        self.processing_cache = {}  # Simple in-memory cache
    
    def analyze_review_sentiment(
        self,
        review: Review,
        force_reanalysis: bool = False
    ) -> SentimentResult:
        """Analyze sentiment of a review"""
        
        # Check if already analyzed and not forcing reanalysis
        if not force_reanalysis and review.sentiment_score and review.sentiment_confidence:
            return SentimentResult(
                score=review.sentiment_score,
                confidence=review.sentiment_confidence,
                raw_data=review.sentiment_analysis_data or {},
                processing_time_ms=0.0
            )
        
        # Combine title and content for analysis
        text_to_analyze = ""
        if review.title:
            text_to_analyze += review.title + " "
        text_to_analyze += review.content
        
        # Include rating in analysis context
        rating_context = {
            "rating": review.rating,
            "review_type": review.review_type.value,
            "is_verified": review.is_verified_purchase
        }
        
        return self._analyze_text_sentiment(text_to_analyze, rating_context)
    
    def analyze_feedback_sentiment(
        self,
        feedback: Feedback,
        force_reanalysis: bool = False
    ) -> SentimentResult:
        """Analyze sentiment of feedback"""
        
        # Check if already analyzed and not forcing reanalysis
        if not force_reanalysis and feedback.sentiment_score and feedback.sentiment_confidence:
            return SentimentResult(
                score=feedback.sentiment_score,
                confidence=feedback.sentiment_confidence,
                raw_data=feedback.sentiment_analysis_data or {},
                processing_time_ms=0.0
            )
        
        # Combine subject and message for analysis
        text_to_analyze = feedback.subject + " " + feedback.message
        
        # Include feedback type and priority in context
        feedback_context = {
            "feedback_type": feedback.feedback_type.value,
            "priority": feedback.priority.value,
            "category": feedback.category
        }
        
        return self._analyze_text_sentiment(text_to_analyze, feedback_context)
    
    def _analyze_text_sentiment(
        self,
        text: str,
        context: Dict[str, Any] = None
    ) -> SentimentResult:
        """Analyze sentiment of text using multiple methods"""
        
        start_time = datetime.utcnow()
        
        # Clean and preprocess text
        cleaned_text = self._preprocess_text(text)
        
        # Use multiple analysis methods and combine results
        keyword_result = self._keyword_based_analysis(cleaned_text, context)
        pattern_result = self._pattern_based_analysis(cleaned_text, context)
        
        # Combine results (could also integrate with external APIs here)
        combined_result = self._combine_sentiment_results([keyword_result, pattern_result])
        
        # Apply context adjustments
        if context:
            combined_result = self._apply_context_adjustments(combined_result, context)
        
        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return SentimentResult(
            score=combined_result["score"],
            confidence=combined_result["confidence"],
            raw_data=combined_result["details"],
            processing_time_ms=processing_time
        )
    
    def _preprocess_text(self, text: str) -> str:
        """Clean and preprocess text for analysis"""
        
        # Convert to lowercase
        text = text.lower()
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters but keep punctuation that affects sentiment
        text = re.sub(r'[^\w\s!?.,;:-]', ' ', text)
        
        # Handle negations (expand contractions)
        negation_patterns = [
            (r"don't", "do not"),
            (r"won't", "will not"),
            (r"can't", "cannot"),
            (r"n't", " not"),
            (r"'re", " are"),
            (r"'ve", " have"),
            (r"'ll", " will"),
            (r"'d", " would")
        ]
        
        for pattern, replacement in negation_patterns:
            text = re.sub(pattern, replacement, text)
        
        return text.strip()
    
    def _keyword_based_analysis(
        self,
        text: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Analyze sentiment using keyword matching"""
        
        words = text.split()
        sentiment_scores = []
        matched_keywords = []
        
        # Analyze each word/phrase
        for i, word in enumerate(words):
            # Check for negation context
            is_negated = self._check_negation_context(words, i)
            
            # Single word analysis
            if word in self.sentiment_keywords:
                base_score = self.sentiment_keywords[word]
                # Flip score if negated
                score = -base_score if is_negated else base_score
                sentiment_scores.append(score)
                matched_keywords.append({
                    "word": word,
                    "base_score": base_score,
                    "final_score": score,
                    "negated": is_negated
                })
            
            # Bigram analysis (two-word phrases)
            if i < len(words) - 1:
                bigram = f"{word} {words[i + 1]}"
                if bigram in self.sentiment_keywords:
                    base_score = self.sentiment_keywords[bigram]
                    score = -base_score if is_negated else base_score
                    sentiment_scores.append(score)
                    matched_keywords.append({
                        "phrase": bigram,
                        "base_score": base_score,
                        "final_score": score,
                        "negated": is_negated
                    })
        
        # Calculate overall sentiment
        if sentiment_scores:
            avg_score = sum(sentiment_scores) / len(sentiment_scores)
            confidence = min(len(sentiment_scores) / 10.0, 1.0)  # More keywords = higher confidence
        else:
            avg_score = 0.0
            confidence = 0.1  # Low confidence for no keywords
        
        # Convert score to sentiment enum
        sentiment_score = self._score_to_sentiment(avg_score)
        
        return {
            "method": "keyword_based",
            "score": sentiment_score,
            "confidence": confidence,
            "raw_score": avg_score,
            "matched_keywords": matched_keywords,
            "total_keywords": len(matched_keywords)
        }
    
    def _pattern_based_analysis(
        self,
        text: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Analyze sentiment using pattern matching"""
        
        sentiment_patterns = [
            # Very positive patterns
            (r'\b(excellent|amazing|outstanding|fantastic|perfect|love|adore)\b', 2.0),
            (r'\b(highly recommend|best ever|extremely happy|very satisfied)\b', 1.8),
            
            # Positive patterns
            (r'\b(good|great|nice|happy|satisfied|pleased|recommend)\b', 1.0),
            (r'\b(pretty good|quite nice|fairly happy)\b', 0.8),
            
            # Negative patterns
            (r'\b(bad|poor|disappointing|unsatisfied|unhappy|dislike)\b', -1.0),
            (r'\b(not good|not happy|not satisfied|could be better)\b', -0.8),
            
            # Very negative patterns
            (r'\b(terrible|awful|horrible|hate|disgusting|worst)\b', -2.0),
            (r'\b(completely disappointed|total waste|never again|extremely poor)\b', -1.8),
            
            # Intensity modifiers
            (r'\b(very|extremely|really|super|incredibly|absolutely)\s+(\w+)', 1.5),  # Multiplier
            (r'\b(somewhat|kind of|sort of|a bit)\s+(\w+)', 0.7),  # Reducer
        ]
        
        pattern_scores = []
        matched_patterns = []
        
        for pattern, score in sentiment_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                pattern_scores.append(score)
                matched_patterns.append({
                    "pattern": pattern,
                    "match": match.group(),
                    "score": score,
                    "position": match.span()
                })
        
        # Calculate overall sentiment
        if pattern_scores:
            avg_score = sum(pattern_scores) / len(pattern_scores)
            confidence = min(len(pattern_scores) / 8.0, 1.0)
        else:
            avg_score = 0.0
            confidence = 0.1
        
        sentiment_score = self._score_to_sentiment(avg_score)
        
        return {
            "method": "pattern_based",
            "score": sentiment_score,
            "confidence": confidence,
            "raw_score": avg_score,
            "matched_patterns": matched_patterns,
            "total_patterns": len(matched_patterns)
        }
    
    def _combine_sentiment_results(
        self,
        results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Combine multiple sentiment analysis results"""
        
        if not results:
            return {
                "score": SentimentScore.NEUTRAL,
                "confidence": 0.0,
                "details": {}
            }
        
        # Weight results by confidence
        total_weight = 0
        weighted_score = 0
        combined_confidence = 0
        
        for result in results:
            weight = result["confidence"]
            total_weight += weight
            weighted_score += result["raw_score"] * weight
            combined_confidence += result["confidence"]
        
        if total_weight > 0:
            final_score = weighted_score / total_weight
            final_confidence = combined_confidence / len(results)
        else:
            final_score = 0.0
            final_confidence = 0.0
        
        return {
            "score": self._score_to_sentiment(final_score),
            "confidence": min(final_confidence, 1.0),
            "raw_score": final_score,
            "details": {
                "individual_results": results,
                "combination_method": "weighted_average",
                "total_weight": total_weight
            }
        }
    
    def _apply_context_adjustments(
        self,
        result: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply context-based adjustments to sentiment analysis"""
        
        adjusted_score = result["raw_score"]
        adjustments = []
        
        # Rating-based adjustments for reviews
        if "rating" in context:
            rating = context["rating"]
            if rating >= 4.0 and result["score"] in [SentimentScore.NEGATIVE, SentimentScore.VERY_NEGATIVE]:
                # High rating but negative sentiment - might be sarcasm or complex review
                adjusted_score *= 0.5
                adjustments.append("rating_sentiment_mismatch")
            elif rating <= 2.0 and result["score"] in [SentimentScore.POSITIVE, SentimentScore.VERY_POSITIVE]:
                # Low rating but positive sentiment - might be constructive criticism
                adjusted_score *= 0.7
                adjustments.append("rating_sentiment_mismatch")
        
        # Feedback type adjustments
        if "feedback_type" in context:
            feedback_type = context["feedback_type"]
            if feedback_type == "complaint":
                # Complaints are inherently negative, adjust confidence up for negative sentiment
                if result["score"] in [SentimentScore.NEGATIVE, SentimentScore.VERY_NEGATIVE]:
                    result["confidence"] = min(result["confidence"] * 1.2, 1.0)
                    adjustments.append("complaint_type_boost")
            elif feedback_type == "compliment":
                # Compliments are inherently positive
                if result["score"] in [SentimentScore.POSITIVE, SentimentScore.VERY_POSITIVE]:
                    result["confidence"] = min(result["confidence"] * 1.2, 1.0)
                    adjustments.append("compliment_type_boost")
        
        # Verified purchase adjustment
        if context.get("is_verified"):
            result["confidence"] = min(result["confidence"] * 1.1, 1.0)
            adjustments.append("verified_purchase_boost")
        
        # Update result with adjustments
        result["raw_score"] = adjusted_score
        result["score"] = self._score_to_sentiment(adjusted_score)
        result["details"]["context_adjustments"] = adjustments
        
        return result
    
    def _check_negation_context(self, words: List[str], position: int) -> bool:
        """Check if a word is in a negation context"""
        
        negation_words = ["not", "no", "never", "none", "nothing", "nobody", "nowhere", "neither"]
        negation_window = 3  # Look back 3 words
        
        start = max(0, position - negation_window)
        context_words = words[start:position]
        
        return any(word in negation_words for word in context_words)
    
    def _score_to_sentiment(self, score: float) -> SentimentScore:
        """Convert numerical score to sentiment enum"""
        
        if score >= 1.5:
            return SentimentScore.VERY_POSITIVE
        elif score >= 0.5:
            return SentimentScore.POSITIVE
        elif score <= -1.5:
            return SentimentScore.VERY_NEGATIVE
        elif score <= -0.5:
            return SentimentScore.NEGATIVE
        else:
            return SentimentScore.NEUTRAL
    
    def _load_sentiment_keywords(self) -> Dict[str, float]:
        """Load sentiment keywords with their scores"""
        
        # This could be loaded from a file or database
        return {
            # Very positive (1.5 to 2.0)
            "excellent": 2.0, "amazing": 2.0, "outstanding": 2.0, "fantastic": 2.0,
            "perfect": 2.0, "wonderful": 2.0, "incredible": 2.0, "exceptional": 2.0,
            "love": 1.8, "adore": 1.8, "brilliant": 1.8, "superb": 1.8,
            
            # Positive (0.5 to 1.5)
            "good": 1.0, "great": 1.2, "nice": 0.8, "happy": 1.0,
            "satisfied": 1.0, "pleased": 1.0, "like": 0.8, "enjoy": 1.0,
            "recommend": 1.2, "useful": 0.8, "helpful": 1.0, "quality": 0.8,
            "fast": 0.6, "quick": 0.6, "efficient": 0.8, "professional": 0.8,
            
            # Neutral modifiers
            "okay": 0.2, "fine": 0.2, "average": 0.0, "acceptable": 0.3,
            
            # Negative (-1.5 to -0.5)
            "bad": -1.0, "poor": -1.0, "disappointing": -1.2, "unsatisfied": -1.0,
            "unhappy": -1.0, "dislike": -0.8, "problem": -0.6, "issue": -0.6,
            "slow": -0.6, "expensive": -0.4, "difficult": -0.6, "confusing": -0.6,
            "annoying": -0.8, "frustrating": -1.0, "inconvenient": -0.6,
            
            # Very negative (-2.0 to -1.5)
            "terrible": -2.0, "awful": -2.0, "horrible": -2.0, "hate": -1.8,
            "disgusting": -2.0, "worst": -1.8, "useless": -1.6, "broken": -1.4,
            "failed": -1.4, "waste": -1.6, "scam": -2.0, "fraud": -2.0,
            
            # Phrases (bigrams)
            "highly recommend": 1.8, "very good": 1.4, "really good": 1.4,
            "very bad": -1.4, "really bad": -1.4, "not good": -1.0,
            "not bad": 0.4, "not great": -0.6, "could be better": -0.4,
            "works well": 1.0, "works great": 1.2, "doesn't work": -1.4,
            "money well spent": 1.6, "waste of money": -1.8, "value for money": 1.0,
            "poor quality": -1.2, "high quality": 1.2, "good quality": 1.0,
            "customer service": 0.0, "excellent service": 1.8, "poor service": -1.2,
            "fast delivery": 1.0, "slow delivery": -0.8, "on time": 0.8,
            "easy to use": 1.0, "hard to use": -0.8, "user friendly": 1.0
        }
    
    async def analyze_batch_async(
        self,
        items: List[Dict[str, Any]],
        batch_size: int = 10
    ) -> List[SentimentResult]:
        """Analyze sentiment for multiple items asynchronously"""
        
        results = []
        
        # Process in batches to avoid overwhelming the system
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            batch_tasks = []
            
            for item in batch:
                if "text" in item:
                    # Direct text analysis
                    task = asyncio.create_task(
                        self._analyze_text_sentiment_async(
                            item["text"],
                            item.get("context", {})
                        )
                    )
                    batch_tasks.append(task)
            
            # Wait for batch to complete
            batch_results = await asyncio.gather(*batch_tasks)
            results.extend(batch_results)
        
        return results
    
    async def _analyze_text_sentiment_async(
        self,
        text: str,
        context: Dict[str, Any] = None
    ) -> SentimentResult:
        """Async version of text sentiment analysis"""
        
        # For now, just wrap the sync version
        # In production, this could use async HTTP calls to external APIs
        return await asyncio.get_event_loop().run_in_executor(
            None,
            self._analyze_text_sentiment,
            text,
            context
        )
    
    def get_sentiment_summary(
        self,
        items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Get summary statistics for sentiment analysis results"""
        
        if not items:
            return {
                "total_items": 0,
                "sentiment_distribution": {},
                "average_confidence": 0.0,
                "insights": []
            }
        
        # Count sentiment distribution
        sentiment_counts = {}
        confidences = []
        
        for item in items:
            if "sentiment_score" in item:
                sentiment = item["sentiment_score"]
                sentiment_counts[sentiment] = sentiment_counts.get(sentiment, 0) + 1
            
            if "sentiment_confidence" in item:
                confidences.append(item["sentiment_confidence"])
        
        # Calculate percentages
        total = len(items)
        sentiment_distribution = {
            sentiment: (count / total) * 100
            for sentiment, count in sentiment_counts.items()
        }
        
        # Calculate average confidence
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        # Generate insights
        insights = []
        positive_pct = sentiment_distribution.get(SentimentScore.POSITIVE.value, 0) + \
                      sentiment_distribution.get(SentimentScore.VERY_POSITIVE.value, 0)
        negative_pct = sentiment_distribution.get(SentimentScore.NEGATIVE.value, 0) + \
                      sentiment_distribution.get(SentimentScore.VERY_NEGATIVE.value, 0)
        
        if positive_pct > 70:
            insights.append("Predominantly positive sentiment - customers are generally satisfied")
        elif negative_pct > 30:
            insights.append("Significant negative sentiment - attention needed for customer satisfaction")
        
        if avg_confidence < 0.5:
            insights.append("Low confidence in sentiment analysis - consider manual review")
        
        return {
            "total_items": total,
            "sentiment_distribution": sentiment_distribution,
            "average_confidence": round(avg_confidence, 3),
            "insights": insights,
            "positive_percentage": round(positive_pct, 1),
            "negative_percentage": round(negative_pct, 1),
            "neutral_percentage": round(sentiment_distribution.get(SentimentScore.NEUTRAL.value, 0), 1)
        }


# Global sentiment analysis service instance
sentiment_service = SentimentAnalysisService()
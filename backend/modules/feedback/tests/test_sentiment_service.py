# backend/modules/feedback/tests/test_sentiment_service.py

import pytest
from unittest.mock import Mock, patch
import asyncio

from backend.modules.feedback.services.sentiment_service import (
    SentimentAnalysisService, SentimentResult, sentiment_service
)
from backend.modules.feedback.models.feedback_models import (
    Review, Feedback, SentimentScore, ReviewType, FeedbackType, FeedbackPriority
)


class TestSentimentAnalysisService:
    """Test cases for SentimentAnalysisService"""
    
    def test_analyze_positive_review(self, sentiment_service: SentimentAnalysisService, sample_review):
        """Test analysis of positive review content"""
        # Update review with positive content
        sample_review.content = "This product is absolutely amazing! I love it so much. Excellent quality and fantastic value for money. Highly recommend!"
        sample_review.rating = 5.0
        
        result = sentiment_service.analyze_review_sentiment(sample_review)
        
        assert isinstance(result, SentimentResult)
        assert result.score in [SentimentScore.POSITIVE, SentimentScore.VERY_POSITIVE]
        assert result.confidence > 0.5
        assert result.processing_time_ms >= 0
        assert "positive" in str(result.raw_data).lower() or "keyword" in str(result.raw_data).lower()
    
    def test_analyze_negative_review(self, sentiment_service: SentimentAnalysisService, sample_review):
        """Test analysis of negative review content"""
        sample_review.content = "This product is terrible and awful. Complete waste of money. I hate it and would never recommend it to anyone."
        sample_review.rating = 1.0
        
        result = sentiment_service.analyze_review_sentiment(sample_review)
        
        assert result.score in [SentimentScore.NEGATIVE, SentimentScore.VERY_NEGATIVE]
        assert result.confidence > 0.5
    
    def test_analyze_neutral_review(self, sentiment_service: SentimentAnalysisService, sample_review):
        """Test analysis of neutral review content"""
        sample_review.content = "The product is okay. It works as described and does what it's supposed to do. Average quality and price."
        sample_review.rating = 3.0
        
        result = sentiment_service.analyze_review_sentiment(sample_review)
        
        assert result.score == SentimentScore.NEUTRAL
    
    def test_analyze_mixed_sentiment_review(self, sentiment_service: SentimentAnalysisService, sample_review):
        """Test analysis of review with mixed sentiment"""
        sample_review.content = "I love the design and quality of this product, but I hate the price. It's great but too expensive."
        sample_review.rating = 3.5
        
        result = sentiment_service.analyze_review_sentiment(sample_review)
        
        # Mixed sentiment should result in neutral or slight positive/negative
        assert result.score in [SentimentScore.NEUTRAL, SentimentScore.POSITIVE, SentimentScore.NEGATIVE]
        assert result.confidence > 0
    
    def test_analyze_review_with_negation(self, sentiment_service: SentimentAnalysisService, sample_review):
        """Test handling of negation in review content"""
        sample_review.content = "This product is not bad at all. It's not terrible and I don't hate it. Not disappointed."
        sample_review.rating = 4.0
        
        result = sentiment_service.analyze_review_sentiment(sample_review)
        
        # Negation handling should affect sentiment
        assert result.score in [SentimentScore.NEUTRAL, SentimentScore.POSITIVE]
    
    def test_analyze_review_with_title(self, sentiment_service: SentimentAnalysisService, sample_review):
        """Test analysis including review title"""
        sample_review.title = "Excellent Product!"
        sample_review.content = "Great quality and fast delivery."
        sample_review.rating = 5.0
        
        result = sentiment_service.analyze_review_sentiment(sample_review)
        
        assert result.score in [SentimentScore.POSITIVE, SentimentScore.VERY_POSITIVE]
        # Title should contribute to positive sentiment
    
    def test_analyze_feedback_positive(self, sentiment_service: SentimentAnalysisService, sample_feedback):
        """Test analysis of positive feedback"""
        sample_feedback.subject = "Great service!"
        sample_feedback.message = "Your customer service is excellent. Very helpful and professional staff."
        
        result = sentiment_service.analyze_feedback_sentiment(sample_feedback)
        
        assert result.score in [SentimentScore.POSITIVE, SentimentScore.VERY_POSITIVE]
        assert result.confidence > 0.5
    
    def test_analyze_feedback_complaint(self, sentiment_service: SentimentAnalysisService, sample_feedback):
        """Test analysis of complaint feedback"""
        sample_feedback.feedback_type = FeedbackType.COMPLAINT
        sample_feedback.subject = "Poor service"
        sample_feedback.message = "I'm very disappointed with the service. The product was defective and customer support was unhelpful."
        
        result = sentiment_service.analyze_feedback_sentiment(sample_feedback)
        
        assert result.score in [SentimentScore.NEGATIVE, SentimentScore.VERY_NEGATIVE]
    
    def test_context_adjustments_rating_mismatch(self, sentiment_service: SentimentAnalysisService, sample_review):
        """Test context adjustments for rating-sentiment mismatch"""
        # High rating but negative words (might be sarcasm or complex review)
        sample_review.rating = 5.0
        sample_review.content = "This product is bad but I still love it somehow. Not sure why but it works for me."
        
        result = sentiment_service.analyze_review_sentiment(sample_review)
        
        # Context adjustment should be applied
        assert "rating_sentiment_mismatch" in str(result.raw_data)
    
    def test_verified_purchase_boost(self, sentiment_service: SentimentAnalysisService, sample_review):
        """Test confidence boost for verified purchases"""
        sample_review.is_verified_purchase = True
        sample_review.content = "Good product, works well."
        
        result = sentiment_service.analyze_review_sentiment(sample_review)
        
        # Should have higher confidence due to verification
        assert "verified_purchase_boost" in str(result.raw_data)
    
    def test_feedback_type_adjustments(self, sentiment_service: SentimentAnalysisService, sample_feedback):
        """Test sentiment adjustments based on feedback type"""
        # Test complaint type adjustment
        sample_feedback.feedback_type = FeedbackType.COMPLAINT
        sample_feedback.message = "The product broke after one day."
        
        result = sentiment_service.analyze_feedback_sentiment(sample_feedback)
        
        # Complaints should boost confidence for negative sentiment
        context_adjustments = result.raw_data.get("details", {}).get("context_adjustments", [])
        if result.score in [SentimentScore.NEGATIVE, SentimentScore.VERY_NEGATIVE]:
            assert "complaint_type_boost" in context_adjustments
    
    def test_keyword_based_analysis(self, sentiment_service: SentimentAnalysisService):
        """Test keyword-based sentiment analysis"""
        text = "excellent amazing outstanding fantastic perfect love"
        
        result = sentiment_service._analyze_text_sentiment(text)
        
        assert result.score in [SentimentScore.VERY_POSITIVE, SentimentScore.POSITIVE]
        assert result.confidence > 0.7
    
    def test_pattern_based_analysis(self, sentiment_service: SentimentAnalysisService):
        """Test pattern-based sentiment analysis"""
        text = "highly recommend best ever extremely happy very satisfied"
        
        result = sentiment_service._analyze_text_sentiment(text)
        
        assert result.score in [SentimentScore.VERY_POSITIVE, SentimentScore.POSITIVE]
    
    def test_text_preprocessing(self, sentiment_service: SentimentAnalysisService):
        """Test text preprocessing functionality"""
        messy_text = "   This    is GREAT!!!   Won't   you   agree???   "
        
        cleaned = sentiment_service._preprocess_text(messy_text)
        
        assert cleaned == "this is great will not you agree"
        assert "  " not in cleaned  # No double spaces
        assert cleaned.islower()  # Lowercase
    
    def test_negation_detection(self, sentiment_service: SentimentAnalysisService):
        """Test negation context detection"""
        words = ["this", "is", "not", "good", "at", "all"]
        
        # "good" is at position 3, "not" is at position 2
        is_negated = sentiment_service._check_negation_context(words, 3)
        
        assert is_negated is True
        
        # Test word not in negation context
        is_negated = sentiment_service._check_negation_context(words, 0)
        assert is_negated is False
    
    def test_score_to_sentiment_conversion(self, sentiment_service: SentimentAnalysisService):
        """Test score to sentiment enum conversion"""
        # Test boundary values
        assert sentiment_service._score_to_sentiment(2.0) == SentimentScore.VERY_POSITIVE
        assert sentiment_service._score_to_sentiment(1.0) == SentimentScore.POSITIVE
        assert sentiment_service._score_to_sentiment(0.0) == SentimentScore.NEUTRAL
        assert sentiment_service._score_to_sentiment(-1.0) == SentimentScore.NEGATIVE
        assert sentiment_service._score_to_sentiment(-2.0) == SentimentScore.VERY_NEGATIVE
    
    def test_force_reanalysis(self, sentiment_service: SentimentAnalysisService, sample_review):
        """Test forcing reanalysis of already analyzed content"""
        # Set existing sentiment
        sample_review.sentiment_score = SentimentScore.NEUTRAL
        sample_review.sentiment_confidence = 0.5
        
        # Force reanalysis
        result = sentiment_service.analyze_review_sentiment(sample_review, force_reanalysis=True)
        
        # Should perform new analysis regardless of existing data
        assert isinstance(result, SentimentResult)
        assert result.processing_time_ms > 0
    
    def test_cached_analysis(self, sentiment_service: SentimentAnalysisService, sample_review):
        """Test using cached sentiment analysis"""
        # Set existing sentiment
        sample_review.sentiment_score = SentimentScore.POSITIVE
        sample_review.sentiment_confidence = 0.8
        sample_review.sentiment_analysis_data = {"method": "cached"}
        
        # Should return cached result
        result = sentiment_service.analyze_review_sentiment(sample_review, force_reanalysis=False)
        
        assert result.score == SentimentScore.POSITIVE
        assert result.confidence == 0.8
        assert result.processing_time_ms == 0.0  # No processing needed
    
    @pytest.mark.asyncio
    async def test_batch_analysis_async(self, sentiment_service: SentimentAnalysisService):
        """Test asynchronous batch sentiment analysis"""
        items = [
            {"text": "This is excellent and amazing!", "context": {}},
            {"text": "This is terrible and awful.", "context": {}},
            {"text": "This is okay, nothing special.", "context": {}},
        ]
        
        results = await sentiment_service.analyze_batch_async(items, batch_size=2)
        
        assert len(results) == 3
        
        # Check that results have appropriate sentiments
        positive_count = sum(1 for r in results if r.score in [SentimentScore.POSITIVE, SentimentScore.VERY_POSITIVE])
        negative_count = sum(1 for r in results if r.score in [SentimentScore.NEGATIVE, SentimentScore.VERY_NEGATIVE])
        neutral_count = sum(1 for r in results if r.score == SentimentScore.NEUTRAL)
        
        assert positive_count >= 1
        assert negative_count >= 1
        # neutral_count might be 0 depending on analysis
    
    def test_sentiment_summary_generation(self, sentiment_service: SentimentAnalysisService):
        """Test sentiment summary statistics"""
        items = [
            {"sentiment_score": SentimentScore.VERY_POSITIVE.value, "sentiment_confidence": 0.9},
            {"sentiment_score": SentimentScore.POSITIVE.value, "sentiment_confidence": 0.8},
            {"sentiment_score": SentimentScore.NEUTRAL.value, "sentiment_confidence": 0.6},
            {"sentiment_score": SentimentScore.NEGATIVE.value, "sentiment_confidence": 0.7},
            {"sentiment_score": SentimentScore.VERY_NEGATIVE.value, "sentiment_confidence": 0.95},
        ]
        
        summary = sentiment_service.get_sentiment_summary(items)
        
        assert summary["total_items"] == 5
        assert summary["average_confidence"] > 0
        assert summary["positive_percentage"] == 40.0  # 2 out of 5
        assert summary["negative_percentage"] == 40.0  # 2 out of 5
        assert summary["neutral_percentage"] == 20.0   # 1 out of 5
        assert len(summary["insights"]) > 0
    
    def test_empty_content_handling(self, sentiment_service: SentimentAnalysisService, sample_review):
        """Test handling of empty or minimal content"""
        sample_review.content = ""
        sample_review.title = None
        
        result = sentiment_service.analyze_review_sentiment(sample_review)
        
        # Should still return a result, likely neutral with low confidence
        assert isinstance(result, SentimentResult)
        assert result.confidence <= 0.5
    
    def test_very_long_content(self, sentiment_service: SentimentAnalysisService, sample_review):
        """Test analysis of very long content"""
        # Create very long content
        long_content = "This product is excellent. " * 200  # Very long review
        sample_review.content = long_content
        
        result = sentiment_service.analyze_review_sentiment(sample_review)
        
        # Should handle long content gracefully
        assert isinstance(result, SentimentResult)
        assert result.score == SentimentScore.POSITIVE  # Should detect repeated positive phrase
    
    def test_special_characters_and_unicode(self, sentiment_service: SentimentAnalysisService, sample_review):
        """Test handling of special characters and unicode"""
        sample_review.content = "Great product! 😊👍 Très bien! 很好! Отлично! 🌟⭐️"
        
        result = sentiment_service.analyze_review_sentiment(sample_review)
        
        # Should handle unicode characters without errors
        assert isinstance(result, SentimentResult)
        # Positive words should still be detected
        assert result.score in [SentimentScore.POSITIVE, SentimentScore.VERY_POSITIVE, SentimentScore.NEUTRAL]
    
    def test_html_and_markup_handling(self, sentiment_service: SentimentAnalysisService, sample_review):
        """Test handling of HTML and markup in content"""
        sample_review.content = "This product is <strong>excellent</strong> and I <em>love</em> it! Visit www.example.com for more info."
        
        result = sentiment_service.analyze_review_sentiment(sample_review)
        
        # Should extract sentiment despite markup
        assert result.score in [SentimentScore.POSITIVE, SentimentScore.VERY_POSITIVE]
    
    def test_multiple_languages_basic(self, sentiment_service: SentimentAnalysisService, sample_review):
        """Test basic handling of non-English content"""
        # Note: Our simple sentiment analyzer primarily works with English
        sample_review.content = "Excelente producto, muy bueno"  # Spanish for "Excellent product, very good"
        
        result = sentiment_service.analyze_review_sentiment(sample_review)
        
        # Should return some result, though accuracy may be limited for non-English
        assert isinstance(result, SentimentResult)
    
    def test_sarcasm_detection_basic(self, sentiment_service: SentimentAnalysisService, sample_review):
        """Test basic sarcasm detection through context"""
        sample_review.rating = 1.0  # Very low rating
        sample_review.content = "Oh great, another broken product. Just what I needed."
        
        result = sentiment_service.analyze_review_sentiment(sample_review)
        
        # Context adjustment should help identify the sarcasm
        assert result.score in [SentimentScore.NEGATIVE, SentimentScore.VERY_NEGATIVE]
    
    def test_intensity_modifiers(self, sentiment_service: SentimentAnalysisService, sample_review):
        """Test handling of intensity modifiers"""
        sample_review.content = "This product is extremely excellent and incredibly amazing!"
        
        result = sentiment_service.analyze_review_sentiment(sample_review)
        
        # Intensity modifiers should boost the sentiment
        assert result.score == SentimentScore.VERY_POSITIVE
        assert result.confidence > 0.7
    
    def test_combined_analysis_methods(self, sentiment_service: SentimentAnalysisService):
        """Test that keyword and pattern analysis are properly combined"""
        text = "excellent quality highly recommend very satisfied"
        
        result = sentiment_service._analyze_text_sentiment(text)
        
        # Should combine results from both keyword and pattern analysis
        details = result.raw_data.get("details", {})
        individual_results = details.get("individual_results", [])
        
        # Should have results from both methods
        methods = [r.get("method") for r in individual_results]
        assert "keyword_based" in methods
        assert "pattern_based" in methods
    
    def test_confidence_calculation(self, sentiment_service: SentimentAnalysisService):
        """Test confidence calculation logic"""
        # Text with many sentiment indicators should have high confidence
        high_confidence_text = "excellent amazing outstanding fantastic perfect wonderful brilliant superb"
        result = sentiment_service._analyze_text_sentiment(high_confidence_text)
        high_confidence = result.confidence
        
        # Text with few sentiment indicators should have lower confidence
        low_confidence_text = "good"
        result = sentiment_service._analyze_text_sentiment(low_confidence_text)
        low_confidence = result.confidence
        
        assert high_confidence > low_confidence
    
    def test_error_handling_malformed_input(self, sentiment_service: SentimentAnalysisService):
        """Test error handling for malformed input"""
        # Test with None input
        with pytest.raises((AttributeError, TypeError)):
            sentiment_service._analyze_text_sentiment(None)
        
        # Test with empty string should work
        result = sentiment_service._analyze_text_sentiment("")
        assert isinstance(result, SentimentResult)


class TestSentimentServiceIntegration:
    """Integration tests for sentiment service with other components"""
    
    def test_sentiment_service_singleton(self):
        """Test that sentiment_service is properly configured as singleton"""
        from backend.modules.feedback.services.sentiment_service import sentiment_service
        
        assert sentiment_service is not None
        assert isinstance(sentiment_service, SentimentAnalysisService)
    
    def test_sentiment_keywords_loading(self, sentiment_service: SentimentAnalysisService):
        """Test that sentiment keywords are properly loaded"""
        keywords = sentiment_service.sentiment_keywords
        
        assert len(keywords) > 0
        assert "excellent" in keywords
        assert "terrible" in keywords
        assert keywords["excellent"] > 0  # Positive score
        assert keywords["terrible"] < 0   # Negative score
    
    def test_performance_with_realistic_content(self, sentiment_service: SentimentAnalysisService):
        """Test performance with realistic review content"""
        realistic_content = """
        I purchased this product last month and have been using it regularly. 
        The build quality is excellent and it feels very sturdy. The design is 
        modern and fits well with my home decor. Setup was straightforward and 
        the instructions were clear. Performance has been consistent and reliable.
        The price point is reasonable for the quality you get. Customer service 
        was helpful when I had a question about warranty. Overall, I'm satisfied 
        with this purchase and would recommend it to others looking for a similar product.
        """
        
        import time
        start_time = time.time()
        
        result = sentiment_service._analyze_text_sentiment(realistic_content)
        
        processing_time = time.time() - start_time
        
        # Should complete quickly (under 1 second for this content)
        assert processing_time < 1.0
        assert isinstance(result, SentimentResult)
        assert result.score in [SentimentScore.POSITIVE, SentimentScore.VERY_POSITIVE]
    
    @pytest.mark.asyncio
    async def test_concurrent_analysis(self, sentiment_service: SentimentAnalysisService):
        """Test concurrent sentiment analysis"""
        texts = [
            "This is excellent!",
            "This is terrible!",
            "This is okay.",
            "Amazing product!",
            "Waste of money."
        ] * 10  # 50 texts total
        
        items = [{"text": text, "context": {}} for text in texts]
        
        start_time = time.time()
        results = await sentiment_service.analyze_batch_async(items, batch_size=10)
        processing_time = time.time() - start_time
        
        assert len(results) == 50
        # Batch processing should be reasonably fast
        assert processing_time < 5.0  # Should complete within 5 seconds
        
        # Verify sentiment distribution makes sense
        positive_count = sum(1 for r in results if r.score in [SentimentScore.POSITIVE, SentimentScore.VERY_POSITIVE])
        negative_count = sum(1 for r in results if r.score in [SentimentScore.NEGATIVE, SentimentScore.VERY_NEGATIVE])
        
        # Should have detected positive and negative sentiments
        assert positive_count > 0
        assert negative_count > 0
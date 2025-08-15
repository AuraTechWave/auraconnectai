# backend/modules/analytics/services/ai_query_processor.py

"""
AI Query Processor for Analytics Assistant.

This service handles natural language processing of user queries,
interprets intent, extracts entities, and converts them to analytics queries.
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, date, timedelta
from dateutil import parser as date_parser
import json

from ..schemas.ai_assistant_schemas import (
    AnalyticsQuery,
    QueryIntent,
    QueryContext,
    ChatMessage,
    MessageRole,
    ChartType,
)

logger = logging.getLogger(__name__)


class AIQueryProcessor:
    """Process natural language queries for analytics"""

    def __init__(self):
        self.intent_patterns = self._initialize_intent_patterns()
        self.entity_extractors = self._initialize_entity_extractors()
        self.metric_keywords = self._initialize_metric_keywords()
        self.time_patterns = self._initialize_time_patterns()

    def _initialize_intent_patterns(self) -> Dict[QueryIntent, List[re.Pattern]]:
        """Initialize regex patterns for intent detection"""
        return {
            QueryIntent.SALES_REPORT: [
                re.compile(
                    r"\b(sales|revenue|income|earnings)\s*(report|summary|overview)?",
                    re.I,
                ),
                re.compile(r"\b(show|get|display|give)\s*me?\s*(the)?\s*sales", re.I),
                re.compile(r"how much (did we|have we) (sell|sold|make|made)", re.I),
            ],
            QueryIntent.REVENUE_ANALYSIS: [
                re.compile(
                    r"\b(revenue|income|earnings)\s*(analysis|trend|growth)", re.I
                ),
                re.compile(r"analyze\s*(the)?\s*revenue", re.I),
                re.compile(r"revenue\s*(by|per|for)", re.I),
            ],
            QueryIntent.STAFF_PERFORMANCE: [
                re.compile(
                    r"\b(staff|employee|team|worker)\s*(performance|productivity|efficiency)",
                    re.I,
                ),
                re.compile(
                    r"(best|top|worst|bottom)\s*(performing)?\s*(staff|employees)", re.I
                ),
                re.compile(r"who\s*(sold|made|performed)", re.I),
            ],
            QueryIntent.PRODUCT_ANALYSIS: [
                re.compile(
                    r"\b(product|item|menu)\s*(performance|analysis|popularity)", re.I
                ),
                re.compile(r"(best|top|worst)\s*selling\s*(products|items)", re.I),
                re.compile(r"what\s*(products|items)\s*(are|were)", re.I),
            ],
            QueryIntent.TREND_ANALYSIS: [
                re.compile(r"\b(trend|pattern|change)\s*(in|for|of)", re.I),
                re.compile(r"(increasing|decreasing|growing|declining)", re.I),
                re.compile(r"over\s*time", re.I),
            ],
            QueryIntent.COMPARISON: [
                re.compile(r"\b(compare|comparison|versus|vs\.?)\b", re.I),
                re.compile(r"\b(difference|between|against)\b", re.I),
                re.compile(r"(this|last)\s*(week|month|year)\s*vs", re.I),
            ],
            QueryIntent.FORECAST: [
                re.compile(r"\b(forecast|predict|projection|estimate)\b", re.I),
                re.compile(r"(will|going to|expected)\s*(be|have|make)", re.I),
                re.compile(r"(next|future|upcoming)", re.I),
            ],
            QueryIntent.HELP: [
                re.compile(r"^(help|what can you do|how to|guide|tutorial)", re.I),
                re.compile(r"(explain|show me how|teach me)", re.I),
            ],
        }

    def _initialize_entity_extractors(self) -> Dict[str, Any]:
        """Initialize entity extraction patterns"""
        return {
            "staff": re.compile(
                r"(?:staff|employee|worker)\s*(?:id\s*)?#?(\d+|\w+)", re.I
            ),
            "product": re.compile(
                r"(?:product|item|menu)\s*(?:id\s*)?#?(\d+|[\w\s]+)", re.I
            ),
            "category": re.compile(
                r"(?:category|type)\s*(?:of\s*)?([a-zA-Z\s]+)", re.I
            ),
            "amount": re.compile(r"\$?(\d+(?:,\d{3})*(?:\.\d{2})?)", re.I),
            "percentage": re.compile(r"(\d+(?:\.\d+)?)\s*%", re.I),
            "count": re.compile(r"\b(\d+)\s*(?:orders?|sales?|transactions?)", re.I),
        }

    def _initialize_metric_keywords(self) -> Dict[str, List[str]]:
        """Initialize metric keyword mappings"""
        return {
            "revenue": ["revenue", "income", "earnings", "sales", "money", "dollars"],
            "orders": ["orders", "transactions", "sales count", "number of sales"],
            "customers": ["customers", "clients", "buyers", "patrons"],
            "average_order_value": [
                "average order",
                "aov",
                "average sale",
                "ticket size",
            ],
            "items_sold": ["items", "products sold", "units", "quantity"],
            "growth": ["growth", "increase", "change", "improvement"],
            "efficiency": ["efficiency", "productivity", "performance"],
        }

    def _initialize_time_patterns(self) -> List[Tuple[re.Pattern, callable]]:
        """Initialize time extraction patterns"""
        return [
            # Relative time patterns
            (re.compile(r"today", re.I), lambda: date.today()),
            (re.compile(r"yesterday", re.I), lambda: date.today() - timedelta(days=1)),
            (
                re.compile(r"(\d+)\s*days?\s*ago", re.I),
                lambda m: date.today() - timedelta(days=int(m.group(1))),
            ),
            (
                re.compile(r"last\s*(\d+)\s*days?", re.I),
                lambda m: (
                    date.today() - timedelta(days=int(m.group(1))),
                    date.today(),
                ),
            ),
            (
                re.compile(r"this\s*week", re.I),
                lambda: (
                    date.today() - timedelta(days=date.today().weekday()),
                    date.today(),
                ),
            ),
            (
                re.compile(r"last\s*week", re.I),
                lambda: (
                    date.today() - timedelta(days=date.today().weekday() + 7),
                    date.today() - timedelta(days=date.today().weekday() + 1),
                ),
            ),
            (
                re.compile(r"this\s*month", re.I),
                lambda: (date.today().replace(day=1), date.today()),
            ),
            (re.compile(r"last\s*month", re.I), lambda: self._get_last_month_range()),
            # Specific date patterns
            (
                re.compile(r"on\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", re.I),
                lambda m: date_parser.parse(m.group(1)).date(),
            ),
            (
                re.compile(r"between\s*(\S+)\s*and\s*(\S+)", re.I),
                lambda m: (
                    date_parser.parse(m.group(1)).date(),
                    date_parser.parse(m.group(2)).date(),
                ),
            ),
        ]

    def process_query(
        self, text: str, context: Optional[QueryContext] = None
    ) -> AnalyticsQuery:
        """
        Process natural language query and extract structured information.

        Args:
            text: User's natural language query
            context: Optional context from conversation history

        Returns:
            Structured AnalyticsQuery object
        """
        try:
            # Clean and normalize text
            cleaned_text = self._clean_query_text(text)

            # Detect intent
            intent, confidence = self._detect_intent(cleaned_text, context)

            # Extract entities
            entities = self._extract_entities(cleaned_text)

            # Extract time range
            time_range = self._extract_time_range(cleaned_text)

            # Extract metrics
            metrics = self._extract_metrics(cleaned_text)

            # Build filters
            filters = self._build_filters(entities, context)

            # Determine grouping and sorting
            group_by = self._determine_grouping(cleaned_text, intent)
            sort_by = self._determine_sorting(cleaned_text, intent)

            # Create query object
            query = AnalyticsQuery(
                original_text=text,
                intent=intent,
                entities=entities,
                time_range=time_range,
                filters=filters,
                metrics=metrics,
                group_by=group_by,
                sort_by=sort_by,
                confidence_score=confidence,
            )

            logger.info(
                f"Processed query: {query.intent} with confidence {query.confidence_score}"
            )
            return query

        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return AnalyticsQuery(
                original_text=text, intent=QueryIntent.UNKNOWN, confidence_score=0.0
            )

    def _clean_query_text(self, text: str) -> str:
        """Clean and normalize query text"""
        # Remove extra whitespace
        text = " ".join(text.split())
        # Remove special characters but keep useful ones
        text = re.sub(r"[^\w\s\$\%\#\-\/\.\,\?]", " ", text)
        return text.strip()

    def _detect_intent(
        self, text: str, context: Optional[QueryContext] = None
    ) -> Tuple[QueryIntent, float]:
        """
        Detect the intent of the query using pattern matching.

        Args:
            text: The user's query text
            context: Optional conversation context for better intent detection

        Returns:
            Tuple of (intent, confidence_score)
            - intent: The detected QueryIntent enum value
            - confidence_score: Float between 0.0 and 1.0 indicating confidence

        Note:
            Uses regex patterns and keyword matching to determine intent.
            Context can boost confidence for follow-up queries.
        """
        scores = {}

        # Check each intent pattern
        for intent, patterns in self.intent_patterns.items():
            score = 0.0
            for pattern in patterns:
                if pattern.search(text):
                    score += 1.0
            scores[intent] = score / len(patterns) if patterns else 0.0

        # Consider context if available
        if context and context.conversation_history:
            # Boost score based on recent conversation topics
            last_intents = [
                msg.metadata.get("intent")
                for msg in context.conversation_history[-3:]
                if msg.metadata and "intent" in msg.metadata
            ]
            for intent in last_intents:
                if intent in scores:
                    scores[intent] *= 1.2

        # Get the highest scoring intent
        if scores:
            best_intent = max(scores.items(), key=lambda x: x[1])
            if best_intent[1] > 0.3:  # Minimum confidence threshold
                return best_intent[0], min(best_intent[1], 1.0)

        # Default to general question if no clear intent
        return QueryIntent.GENERAL_QUESTION, 0.5

    def _extract_entities(self, text: str) -> Dict[str, Any]:
        """Extract entities from the query text"""
        entities = {}

        for entity_type, pattern in self.entity_extractors.items():
            matches = pattern.findall(text)
            if matches:
                entities[entity_type] = matches[0] if len(matches) == 1 else matches

        return entities

    def _extract_time_range(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract time range from query text"""
        for pattern, handler in self.time_patterns:
            match = pattern.search(text)
            if match:
                try:
                    result = handler(match) if match.groups() else handler()
                    if isinstance(result, tuple):
                        return {
                            "start_date": result[0].isoformat(),
                            "end_date": result[1].isoformat(),
                        }
                    else:
                        return {"date": result.isoformat()}
                except Exception as e:
                    logger.warning(f"Error parsing time range: {e}")

        # Default to last 7 days if no time specified
        return {
            "start_date": (date.today() - timedelta(days=7)).isoformat(),
            "end_date": date.today().isoformat(),
        }

    def _extract_metrics(self, text: str) -> List[str]:
        """Extract metrics mentioned in the query"""
        metrics = []
        text_lower = text.lower()

        for metric, keywords in self.metric_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                metrics.append(metric)

        # Default metrics based on intent
        if not metrics:
            return ["revenue", "orders"]

        return metrics

    def _build_filters(
        self, entities: Dict[str, Any], context: Optional[QueryContext] = None
    ) -> Dict[str, Any]:
        """Build filters from extracted entities and context"""
        filters = {}

        # Add entity-based filters
        if "staff" in entities:
            filters["staff_ids"] = (
                [entities["staff"]]
                if isinstance(entities["staff"], (str, int))
                else entities["staff"]
            )

        if "product" in entities:
            filters["product_ids"] = (
                [entities["product"]]
                if isinstance(entities["product"], (str, int))
                else entities["product"]
            )

        if "category" in entities:
            filters["category_names"] = (
                [entities["category"]]
                if isinstance(entities["category"], str)
                else entities["category"]
            )

        # Merge with context filters if available
        if context and context.current_filters:
            filters.update(context.current_filters)

        return filters

    def _determine_grouping(
        self, text: str, intent: QueryIntent
    ) -> Optional[List[str]]:
        """Determine grouping based on query text and intent"""
        grouping_keywords = {
            "by staff": ["staff_id"],
            "by employee": ["staff_id"],
            "by product": ["product_id"],
            "by category": ["category_id"],
            "by day": ["date"],
            "by week": ["week"],
            "by month": ["month"],
            "by hour": ["hour"],
        }

        text_lower = text.lower()
        for keyword, group_by in grouping_keywords.items():
            if keyword in text_lower:
                return group_by

        # Default grouping based on intent
        intent_defaults = {
            QueryIntent.STAFF_PERFORMANCE: ["staff_id"],
            QueryIntent.PRODUCT_ANALYSIS: ["product_id"],
            QueryIntent.TREND_ANALYSIS: ["date"],
        }

        return intent_defaults.get(intent)

    def _determine_sorting(self, text: str, intent: QueryIntent) -> Optional[str]:
        """Determine sorting based on query text and intent"""
        sorting_keywords = {
            "highest": "desc",
            "lowest": "asc",
            "most": "desc",
            "least": "asc",
            "best": "desc",
            "worst": "asc",
            "top": "desc",
            "bottom": "asc",
        }

        text_lower = text.lower()
        for keyword, order in sorting_keywords.items():
            if keyword in text_lower:
                # Determine what to sort by based on context
                if any(word in text_lower for word in ["revenue", "sales", "income"]):
                    return f"revenue:{order}"
                elif any(word in text_lower for word in ["orders", "transactions"]):
                    return f"orders:{order}"
                elif any(word in text_lower for word in ["performance", "efficiency"]):
                    return f"efficiency:{order}"

        # Default sorting
        return "revenue:desc"

    def _get_last_month_range(self) -> Tuple[date, date]:
        """Get the date range for last month"""
        today = date.today()
        first_day_this_month = today.replace(day=1)
        last_day_last_month = first_day_this_month - timedelta(days=1)
        first_day_last_month = last_day_last_month.replace(day=1)
        return first_day_last_month, last_day_last_month

    def enhance_with_context(
        self, query: AnalyticsQuery, context: QueryContext
    ) -> AnalyticsQuery:
        """Enhance query with conversation context"""
        # If query references previous results
        if any(
            word in query.original_text.lower()
            for word in ["that", "those", "same", "previous"]
        ):
            # Look for previous query parameters in context
            for msg in reversed(context.conversation_history):
                if msg.metadata and "query" in msg.metadata:
                    prev_query = msg.metadata["query"]
                    # Inherit filters if not specified
                    if not query.filters and prev_query.get("filters"):
                        query.filters = prev_query["filters"]
                    # Inherit time range if not specified
                    if not query.time_range and prev_query.get("time_range"):
                        query.time_range = prev_query["time_range"]
                    break

        return query

    def suggest_clarifications(self, query: AnalyticsQuery) -> List[str]:
        """Suggest clarifications for ambiguous queries"""
        clarifications = []

        # Check for missing time range
        if not query.time_range:
            clarifications.append("What time period would you like to analyze?")

        # Check for ambiguous entities
        if query.intent == QueryIntent.STAFF_PERFORMANCE and not query.filters.get(
            "staff_ids"
        ):
            clarifications.append(
                "Would you like to see all staff or specific team members?"
            )

        if query.intent == QueryIntent.PRODUCT_ANALYSIS and not query.filters.get(
            "product_ids"
        ):
            clarifications.append(
                "Are you interested in all products or specific categories?"
            )

        # Check for missing metrics
        if not query.metrics:
            clarifications.append(
                "What metrics would you like to see? (revenue, orders, growth, etc.)"
            )

        return clarifications

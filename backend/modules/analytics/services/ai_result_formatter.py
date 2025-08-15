# backend/modules/analytics/services/ai_result_formatter.py

"""
AI Result Formatter Service for Analytics Assistant.

This service formats query results into user-friendly visualizations
and provides natural language summaries of the data.
"""

import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, date
from decimal import Decimal

from ..schemas.ai_assistant_schemas import (
    QueryResult,
    ChartData,
    TableData,
    DataPoint,
    ChartType,
    AnalyticsQuery,
    QueryIntent,
)

logger = logging.getLogger(__name__)


class AIResultFormatter:
    """Format analytics results for AI assistant responses"""

    def __init__(self):
        self.chart_recommendations = self._initialize_chart_recommendations()
        self.formatting_rules = self._initialize_formatting_rules()

    def _initialize_chart_recommendations(self) -> Dict[str, ChartType]:
        """Initialize chart type recommendations based on data"""
        return {
            "time_series": ChartType.LINE,
            "comparison": ChartType.BAR,
            "distribution": ChartType.PIE,
            "trend": ChartType.AREA,
            "correlation": ChartType.SCATTER,
            "heatmap": ChartType.HEATMAP,
            "single_metric": ChartType.GAUGE,
            "mini_trend": ChartType.SPARKLINE,
        }

    def _initialize_formatting_rules(self) -> Dict[str, Dict[str, Any]]:
        """Initialize formatting rules for different data types"""
        return {
            "currency": {
                "prefix": "$",
                "decimal_places": 2,
                "thousands_separator": True,
            },
            "percentage": {"suffix": "%", "decimal_places": 1, "multiply_by": 100},
            "number": {"decimal_places": 0, "thousands_separator": True},
            "decimal": {"decimal_places": 2, "thousands_separator": True},
        }

    def format_value(self, value: Any, format_type: str = "number") -> str:
        """
        Format a value according to its type.

        Args:
            value: Value to format
            format_type: Type of formatting to apply

        Returns:
            Formatted string
        """
        if value is None:
            return "N/A"

        try:
            # Convert to float for numeric operations
            if isinstance(value, (int, float, Decimal)):
                num_value = float(value)
            else:
                return str(value)

            rules = self.formatting_rules.get(
                format_type, self.formatting_rules["number"]
            )

            # Apply multiplier if needed (e.g., for percentages)
            if "multiply_by" in rules:
                num_value *= rules["multiply_by"]

            # Format with decimal places
            decimal_places = rules.get("decimal_places", 0)
            formatted = f"{num_value:,.{decimal_places}f}"

            # Add prefix/suffix
            if "prefix" in rules:
                formatted = rules["prefix"] + formatted
            if "suffix" in rules:
                formatted = formatted + rules["suffix"]

            return formatted

        except Exception as e:
            logger.error(f"Error formatting value {value}: {e}")
            return str(value)

    def recommend_chart_type(
        self, data: List[DataPoint], query: AnalyticsQuery
    ) -> ChartType:
        """
        Recommend the best chart type based on data and query.

        Args:
            data: Data points to visualize
            query: Original analytics query

        Returns:
            Recommended chart type
        """
        # Check data characteristics
        if not data:
            return ChartType.TABLE

        # Time series data
        if any(self._is_date_label(point.label) for point in data):
            if len(data) > 20:
                return ChartType.LINE
            else:
                return ChartType.AREA

        # Distribution data (percentages that sum to 100)
        if len(data) <= 10 and self._is_distribution_data(data):
            return ChartType.PIE

        # Comparison data
        if len(data) <= 15:
            return ChartType.BAR

        # Large datasets
        if len(data) > 50:
            return ChartType.TABLE

        # Single metric
        if len(data) == 1:
            return ChartType.GAUGE

        # Default to bar chart
        return ChartType.BAR

    def _is_date_label(self, label: str) -> bool:
        """Check if label appears to be a date"""
        try:
            # Try common date formats
            for date_format in ["%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%m/%d/%Y"]:
                try:
                    datetime.strptime(label, date_format)
                    return True
                except ValueError:
                    continue

            # Check for time labels
            if ":" in label and any(
                label.endswith(suffix) for suffix in [":00", ":30", ":15", ":45"]
            ):
                return True

            return False
        except Exception as e:
            logger.debug(f"Date label check failed for '{label}': {e}")
            return False

    def _is_distribution_data(self, data: List[DataPoint]) -> bool:
        """Check if data represents a distribution (sums to ~100%)"""
        try:
            total = sum(
                float(point.value)
                for point in data
                if isinstance(point.value, (int, float))
            )
            return 95 <= total <= 105  # Allow some tolerance
        except Exception as e:
            logger.debug(f"Distribution data check failed: {e}")
            return False

    def create_summary_text(
        self, query_result: QueryResult, query: AnalyticsQuery
    ) -> str:
        """
        Create a natural language summary of the results.

        Args:
            query_result: Query execution result
            query: Original analytics query

        Returns:
            Natural language summary
        """
        parts = []

        # Add main summary
        parts.append(query_result.summary)

        # Add data summary if available
        if query_result.data:
            if isinstance(query_result.data, ChartData):
                data_summary = self._summarize_chart_data(query_result.data)
                if data_summary:
                    parts.append(data_summary)
            elif isinstance(query_result.data, TableData):
                data_summary = self._summarize_table_data(query_result.data)
                if data_summary:
                    parts.append(data_summary)

        # Add insights
        if query_result.insights:
            parts.append("\n**Key Insights:**")
            for i, insight in enumerate(query_result.insights[:3], 1):
                parts.append(f"{i}. {insight}")

        return "\n\n".join(parts)

    def _summarize_chart_data(self, chart_data: ChartData) -> Optional[str]:
        """Create summary for chart data"""
        if not chart_data.data:
            return None

        summaries = []

        # Get numeric values
        values = [
            float(point.value)
            for point in chart_data.data
            if isinstance(point.value, (int, float))
        ]

        if values:
            # Calculate statistics
            total = sum(values)
            average = total / len(values)
            maximum_value = max(values)
            minimum_value = min(values)

            # Find corresponding labels
            max_point = next(
                p for p in chart_data.data if float(p.value) == maximum_value
            )
            min_point = next(
                p for p in chart_data.data if float(p.value) == minimum_value
            )

            # Create summary based on chart type
            if chart_data.type == ChartType.PIE:
                summaries.append(
                    f"Total across all segments: {self.format_value(total, 'currency')}"
                )
                summaries.append(
                    f"Largest segment: {max_point.label} ({self.format_value(maximum_value, 'currency')})"
                )
            elif chart_data.type in [ChartType.LINE, ChartType.AREA]:
                if self._is_date_label(chart_data.data[0].label):
                    summaries.append(
                        f"Period range: {chart_data.data[0].label} to {chart_data.data[-1].label}"
                    )
                summaries.append(f"Average: {self.format_value(average, 'currency')}")
                summaries.append(
                    f"Peak: {self.format_value(maximum_value, 'currency')} on {max_point.label}"
                )
                summaries.append(
                    f"Low: {self.format_value(minimum_value, 'currency')} on {min_point.label}"
                )
            else:
                summaries.append(
                    f"Highest: {max_point.label} ({self.format_value(maximum_value, 'currency')})"
                )
                summaries.append(
                    f"Lowest: {min_point.label} ({self.format_value(minimum_value, 'currency')})"
                )
                summaries.append(f"Average: {self.format_value(average, 'currency')}")

        return " | ".join(summaries) if summaries else None

    def _summarize_table_data(self, table_data: TableData) -> Optional[str]:
        """Create summary for table data"""
        summaries = []

        if table_data.total_rows:
            summaries.append(
                f"Showing {len(table_data.rows)} of {table_data.total_rows} total records"
            )
        else:
            summaries.append(f"Showing {len(table_data.rows)} records")

        # Summarize numeric columns
        for column in table_data.columns:
            if column["type"] in ["number", "currency", "percentage"]:
                column_values = [
                    float(row[column["key"]])
                    for row in table_data.rows
                    if column["key"] in row
                    and isinstance(row[column["key"]], (int, float))
                ]

                if column_values:
                    total = sum(column_values)
                    average = total / len(column_values)

                    if column["type"] == "currency":
                        summaries.append(
                            f"Total {column['label']}: {self.format_value(total, 'currency')}"
                        )
                    else:
                        summaries.append(
                            f"Average {column['label']}: {self.format_value(average, column['type'])}"
                        )

        return " | ".join(summaries) if summaries else None

    def enhance_with_emojis(self, text: str, query_intent: QueryIntent) -> str:
        """
        Add appropriate emojis to enhance readability.

        Args:
            text: Text to enhance
            query_intent: Intent of the query

        Returns:
            Text with emojis
        """
        # Intent-based emojis
        intent_emojis = {
            QueryIntent.SALES_REPORT: "💰",
            QueryIntent.REVENUE_ANALYSIS: "📈",
            QueryIntent.STAFF_PERFORMANCE: "👥",
            QueryIntent.PRODUCT_ANALYSIS: "📦",
            QueryIntent.TREND_ANALYSIS: "📊",
            QueryIntent.COMPARISON: "🔄",
            QueryIntent.FORECAST: "🔮",
            QueryIntent.HELP: "❓",
        }

        # Keyword-based emojis
        keyword_emojis = {
            "increase": "⬆️",
            "decrease": "⬇️",
            "growth": "📈",
            "decline": "📉",
            "warning": "⚠️",
            "success": "✅",
            "error": "❌",
            "top": "🏆",
            "best": "⭐",
            "worst": "⚠️",
        }

        # Add intent emoji at the start
        emoji = intent_emojis.get(query_intent, "📊")
        enhanced_text = f"{emoji} {text}"

        # Replace keywords with emoji versions
        for keyword, emoji in keyword_emojis.items():
            enhanced_text = enhanced_text.replace(keyword, f"{keyword} {emoji}")

        return enhanced_text

    def format_error_response(
        self, error_message: str, suggestion: Optional[str] = None
    ) -> str:
        """
        Format an error response in a user-friendly way.

        Args:
            error_message: Error message
            suggestion: Optional suggestion for resolution

        Returns:
            Formatted error response
        """
        parts = ["❌ I encountered an issue while processing your request:"]
        parts.append(f"\n{error_message}")

        if suggestion:
            parts.append(f"\n\n💡 **Suggestion:** {suggestion}")
        else:
            # Add generic suggestions based on error type
            if "rate limit" in error_message.lower():
                parts.append(
                    "\n\n💡 **Tip:** Try spacing out your requests or simplifying your queries."
                )
            elif "permission" in error_message.lower():
                parts.append(
                    "\n\n💡 **Tip:** Contact your administrator if you need access to this data."
                )
            elif "timeout" in error_message.lower():
                parts.append(
                    "\n\n💡 **Tip:** Try narrowing your date range or filters to reduce processing time."
                )

        return "\n".join(parts)

    def create_comparison_summary(
        self,
        current_data: Dict[str, Any],
        previous_data: Dict[str, Any],
        metric_name: str,
    ) -> str:
        """
        Create a summary comparing two data sets.

        Args:
            current_data: Current period data
            previous_data: Previous period data
            metric_name: Name of the metric being compared

        Returns:
            Comparison summary text
        """
        current_value = current_data.get("value", 0)
        previous_value = previous_data.get("value", 0)

        if previous_value == 0:
            change = 100.0 if current_value > 0 else 0.0
        else:
            change = ((current_value - previous_value) / previous_value) * 100

        direction = (
            "increased"
            if change > 0
            else "decreased" if change < 0 else "remained flat"
        )
        emoji = "📈" if change > 5 else "📉" if change < -5 else "➡️"

        summary = (
            f"{emoji} {metric_name.capitalize()} {direction} by {abs(change):.1f}%\n"
        )
        summary += f"Current: {self.format_value(current_value, 'currency')} | "
        summary += f"Previous: {self.format_value(previous_value, 'currency')}"

        return summary

# backend/modules/analytics/services/pos_export_service.py

"""
Service for POS analytics exports.

Handles data export in various formats.
"""

from sqlalchemy.orm import Session
from typing import List, Optional, Any, Dict
from datetime import datetime
import logging
import csv
import json
import os
import tempfile
from pathlib import Path

from .pos.base_service import POSAnalyticsBaseService
from .pos_dashboard_service import POSDashboardService
from .pos_trends_service import POSTrendsService

logger = logging.getLogger(__name__)


class POSExportService(POSAnalyticsBaseService):
    """Service for exporting POS analytics data"""
    
    def __init__(self, db: Session):
        super().__init__(db)
        self.dashboard_service = POSDashboardService(db)
        self.trends_service = POSTrendsService(db)
    
    async def export_analytics(
        self,
        report_type: str,
        format: str,
        start_date: datetime,
        end_date: datetime,
        provider_ids: Optional[List[int]] = None,
        terminal_ids: Optional[List[str]] = None,
        include_charts: bool = False,
        user_id: int = None
    ) -> str:
        """Export analytics data to file"""
        
        # Validate inputs
        if report_type not in ["summary", "detailed", "transactions", "errors"]:
            raise ValueError(f"Invalid report type: {report_type}")
        
        if format not in ["csv", "xlsx", "pdf"]:
            raise ValueError(f"Invalid format: {format}")
        
        # Generate report data
        if report_type == "summary":
            data = await self._generate_summary_report(
                start_date, end_date, provider_ids, terminal_ids
            )
        elif report_type == "detailed":
            data = await self._generate_detailed_report(
                start_date, end_date, provider_ids, terminal_ids
            )
        elif report_type == "transactions":
            data = await self._generate_transactions_report(
                start_date, end_date, provider_ids, terminal_ids
            )
        elif report_type == "errors":
            data = await self._generate_errors_report(
                start_date, end_date, provider_ids, terminal_ids
            )
        else:
            raise ValueError(f"Unknown report type: {report_type}")
        
        # Export to file
        if format == "csv":
            file_path = await self._export_to_csv(data, report_type)
        elif format == "xlsx":
            file_path = await self._export_to_excel(data, report_type, include_charts)
        elif format == "pdf":
            file_path = await self._export_to_pdf(data, report_type, include_charts)
        else:
            raise ValueError(f"Unknown format: {format}")
        
        logger.info(
            f"Exported {report_type} report in {format} format for user {user_id}"
        )
        
        return file_path
    
    async def _generate_summary_report(
        self,
        start_date: datetime,
        end_date: datetime,
        provider_ids: Optional[List[int]],
        terminal_ids: Optional[List[str]]
    ) -> Dict[str, Any]:
        """Generate summary report data"""
        
        # Get dashboard data
        dashboard = await self.dashboard_service.get_dashboard_data(
            start_date, end_date, provider_ids, terminal_ids, True
        )
        
        return {
            "metadata": {
                "report_type": "summary",
                "generated_at": datetime.utcnow().isoformat(),
                "time_range": f"{start_date.isoformat()} to {end_date.isoformat()}"
            },
            "overview": {
                "total_providers": dashboard.total_providers,
                "active_providers": dashboard.active_providers,
                "total_terminals": dashboard.total_terminals,
                "online_terminals": dashboard.online_terminals,
                "total_transactions": dashboard.total_transactions,
                "transaction_success_rate": dashboard.transaction_success_rate,
                "total_transaction_value": str(dashboard.total_transaction_value)
            },
            "providers": [
                {
                    "name": p.provider_name,
                    "code": p.provider_code,
                    "terminals": p.total_terminals,
                    "transactions": p.total_transactions,
                    "success_rate": p.transaction_success_rate,
                    "value": str(p.total_transaction_value)
                }
                for p in dashboard.providers
            ],
            "trends": [
                {
                    "timestamp": t.timestamp.isoformat(),
                    "transactions": t.transaction_count,
                    "value": str(t.transaction_value),
                    "success_rate": t.success_rate
                }
                for t in dashboard.transaction_trends
            ]
        }
    
    async def _generate_detailed_report(
        self,
        start_date: datetime,
        end_date: datetime,
        provider_ids: Optional[List[int]],
        terminal_ids: Optional[List[str]]
    ) -> Dict[str, Any]:
        """Generate detailed report data"""
        
        # This would include more granular data
        # For now, return summary + additional metrics
        summary = await self._generate_summary_report(
            start_date, end_date, provider_ids, terminal_ids
        )
        
        # Add performance trends
        performance_trends = await self.trends_service.get_performance_trends(
            "response_time", start_date, end_date, None, "daily"
        )
        
        summary["performance_trends"] = performance_trends
        
        return summary
    
    async def _generate_transactions_report(
        self,
        start_date: datetime,
        end_date: datetime,
        provider_ids: Optional[List[int]],
        terminal_ids: Optional[List[str]]
    ) -> Dict[str, Any]:
        """Generate transactions report data"""
        
        # Get transaction trends with hourly granularity
        trends = await self.trends_service.get_transaction_trends(
            start_date, end_date, None, None, "hourly"
        )
        
        return {
            "metadata": {
                "report_type": "transactions",
                "generated_at": datetime.utcnow().isoformat(),
                "time_range": f"{start_date.isoformat()} to {end_date.isoformat()}"
            },
            "transactions": trends
        }
    
    async def _generate_errors_report(
        self,
        start_date: datetime,
        end_date: datetime,
        provider_ids: Optional[List[int]],
        terminal_ids: Optional[List[str]]
    ) -> Dict[str, Any]:
        """Generate errors report data"""
        
        # Get error trends
        error_trends = await self.trends_service.get_performance_trends(
            "error_rate", start_date, end_date, None, "daily"
        )
        
        return {
            "metadata": {
                "report_type": "errors",
                "generated_at": datetime.utcnow().isoformat(),
                "time_range": f"{start_date.isoformat()} to {end_date.isoformat()}"
            },
            "error_trends": error_trends
        }
    
    async def _export_to_csv(
        self,
        data: Dict[str, Any],
        report_type: str
    ) -> str:
        """Export data to CSV file"""
        
        # Create temporary file
        temp_dir = tempfile.gettempdir()
        filename = f"pos_analytics_{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        file_path = os.path.join(temp_dir, filename)
        
        with open(file_path, 'w', newline='') as csvfile:
            if report_type == "summary":
                # Write overview
                writer = csv.writer(csvfile)
                writer.writerow(["POS Analytics Summary Report"])
                writer.writerow([f"Generated: {data['metadata']['generated_at']}"])
                writer.writerow([f"Period: {data['metadata']['time_range']}"])
                writer.writerow([])
                
                # Write overview metrics
                writer.writerow(["Overview Metrics"])
                for key, value in data['overview'].items():
                    writer.writerow([key.replace('_', ' ').title(), value])
                writer.writerow([])
                
                # Write provider data
                writer.writerow(["Provider Performance"])
                if data['providers']:
                    headers = list(data['providers'][0].keys())
                    writer.writerow(headers)
                    for provider in data['providers']:
                        writer.writerow([provider[h] for h in headers])
            
            elif report_type == "transactions":
                # Write transaction data
                writer = csv.writer(csvfile)
                if data['transactions']:
                    headers = list(data['transactions'][0].keys())
                    writer.writerow(headers)
                    for tx in data['transactions']:
                        writer.writerow([tx[h] for h in headers])
        
        return file_path
    
    async def _export_to_excel(
        self,
        data: Dict[str, Any],
        report_type: str,
        include_charts: bool
    ) -> str:
        """Export data to Excel file"""
        
        # This would use openpyxl or similar library
        # For now, return CSV path as placeholder
        return await self._export_to_csv(data, report_type)
    
    async def _export_to_pdf(
        self,
        data: Dict[str, Any],
        report_type: str,
        include_charts: bool
    ) -> str:
        """Export data to PDF file"""
        
        # This would use reportlab or similar library
        # For now, return CSV path as placeholder
        return await self._export_to_csv(data, report_type)
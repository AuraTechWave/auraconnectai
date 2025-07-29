# backend/modules/analytics/services/async_processing.py

import asyncio
import logging
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from enum import Enum
import uuid
import json
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Status of async tasks"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    """Priority levels for async tasks"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class AsyncTask:
    """Async task definition"""
    id: str
    task_type: str
    status: TaskStatus
    priority: TaskPriority
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_by: Optional[int] = None


class AsyncTaskProcessor:
    """Processor for handling long-running analytics tasks asynchronously"""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.tasks: Dict[str, AsyncTask] = {}
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.task_handlers: Dict[str, Callable] = {}
        self.running = False
        
        # Register default task handlers
        self._register_default_handlers()
    
    async def start(self):
        """Start the async task processor"""
        self.running = True
        logger.info(f"Async task processor started with {self.max_workers} workers")
        
        # Start background task monitoring
        asyncio.create_task(self._monitor_tasks())
    
    async def stop(self):
        """Stop the async task processor"""
        self.running = False
        
        # Cancel all running tasks
        for task_id, task in self.running_tasks.items():
            if not task.done():
                task.cancel()
                self.tasks[task_id].status = TaskStatus.CANCELLED
        
        # Shutdown executor
        self.executor.shutdown(wait=True)
        logger.info("Async task processor stopped")
    
    def register_handler(self, task_type: str, handler: Callable):
        """Register a task handler function"""
        self.task_handlers[task_type] = handler
        logger.info(f"Registered handler for task type: {task_type}")
    
    async def submit_task(
        self,
        task_type: str,
        task_data: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
        created_by: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Submit a new async task"""
        
        if task_type not in self.task_handlers:
            raise ValueError(f"No handler registered for task type: {task_type}")
        
        task_id = str(uuid.uuid4())
        
        task = AsyncTask(
            id=task_id,
            task_type=task_type,
            status=TaskStatus.PENDING,
            priority=priority,
            created_at=datetime.now(),
            metadata={
                "task_data": task_data,
                **(metadata or {})
            },
            created_by=created_by
        )
        
        self.tasks[task_id] = task
        
        # Start task execution
        asyncio.create_task(self._execute_task(task_id))
        
        logger.info(f"Submitted async task: {task_id} ({task_type})")
        return task_id
    
    def get_task_status(self, task_id: str) -> Optional[AsyncTask]:
        """Get status of a specific task"""
        return self.tasks.get(task_id)
    
    def get_user_tasks(
        self, 
        user_id: int, 
        status_filter: Optional[TaskStatus] = None
    ) -> List[AsyncTask]:
        """Get all tasks for a specific user"""
        
        user_tasks = []
        for task in self.tasks.values():
            if task.created_by == user_id:
                if status_filter is None or task.status == status_filter:
                    user_tasks.append(task)
        
        return sorted(user_tasks, key=lambda t: t.created_at, reverse=True)
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or running task"""
        
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        
        if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            return False
        
        # Cancel the running task
        if task_id in self.running_tasks:
            running_task = self.running_tasks[task_id]
            if not running_task.done():
                running_task.cancel()
        
        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.now()
        
        logger.info(f"Cancelled task: {task_id}")
        return True
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get overall queue status"""
        
        status_counts = {}
        for task in self.tasks.values():
            status_counts[task.status.value] = status_counts.get(task.status.value, 0) + 1
        
        return {
            "total_tasks": len(self.tasks),
            "running_tasks": len(self.running_tasks),
            "status_breakdown": status_counts,
            "max_workers": self.max_workers,
            "processor_running": self.running
        }
    
    # Private methods
    
    async def _execute_task(self, task_id: str):
        """Execute a single task"""
        
        task = self.tasks[task_id]
        handler = self.task_handlers[task.task_type]
        
        try:
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            
            # Create async task for execution
            execution_task = asyncio.create_task(
                self._run_task_handler(handler, task)
            )
            self.running_tasks[task_id] = execution_task
            
            # Wait for completion
            result = await execution_task
            
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.progress = 100.0
            task.result = result
            
            logger.info(f"Task completed: {task_id}")
            
        except asyncio.CancelledError:
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now()
            logger.info(f"Task cancelled: {task_id}")
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now()
            task.error = str(e)
            logger.error(f"Task failed: {task_id} - {e}")
            
        finally:
            # Remove from running tasks
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
    
    async def _run_task_handler(self, handler: Callable, task: AsyncTask) -> Dict[str, Any]:
        """Run task handler in executor if it's not async"""
        
        task_data = task.metadata.get("task_data", {})
        
        # Check if handler is async
        if asyncio.iscoroutinefunction(handler):
            return await handler(task_data, task)
        else:
            # Run in executor for CPU-bound tasks
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self.executor,
                lambda: handler(task_data, task)
            )
    
    async def _monitor_tasks(self):
        """Monitor tasks and clean up old ones"""
        
        while self.running:
            try:
                # Clean up old completed tasks (older than 24 hours)
                cutoff_time = datetime.now().timestamp() - (24 * 3600)
                
                old_tasks = [
                    task_id for task_id, task in self.tasks.items()
                    if task.completed_at and task.completed_at.timestamp() < cutoff_time
                ]
                
                for task_id in old_tasks:
                    del self.tasks[task_id]
                
                if old_tasks:
                    logger.info(f"Cleaned up {len(old_tasks)} old tasks")
                
                # Log queue status every 5 minutes
                status = self.get_queue_status()
                logger.debug(f"Queue status: {status['running_tasks']}/{status['max_workers']} workers busy")
                
            except Exception as e:
                logger.error(f"Error in task monitoring: {e}")
            
            # Sleep for 5 minutes
            await asyncio.sleep(300)
    
    def _register_default_handlers(self):
        """Register default task handlers for analytics"""
        
        self.register_handler("generate_large_report", self._handle_large_report)
        self.register_handler("export_data", self._handle_export_data)
        self.register_handler("calculate_trends", self._handle_calculate_trends)
        self.register_handler("update_snapshots", self._handle_update_snapshots)
        self.register_handler("refresh_materialized_views", self._handle_refresh_views)
    
    async def _handle_large_report(self, task_data: Dict[str, Any], task: AsyncTask) -> Dict[str, Any]:
        """Handle large report generation"""
        
        from .sales_report_service import SalesReportService
        from ..schemas.analytics_schemas import SalesFilterRequest
        from backend.core.database import get_db
        
        db = next(get_db())
        try:
            service = SalesReportService(db)
            
            # Update progress
            task.progress = 10.0
            
            # Parse filters
            filters = SalesFilterRequest(**task_data.get("filters", {}))
            
            # Generate report
            task.progress = 50.0
            report = service.generate_detailed_sales_report(
                filters=filters,
                page=1,
                per_page=task_data.get("limit", 10000)
            )
            
            task.progress = 90.0
            
            return {
                "success": True,
                "report_type": "detailed_sales",
                "total_records": report.total,
                "data": [item.dict() for item in report.items]
            }
            
        finally:
            db.close()
    
    def _handle_export_data(self, task_data: Dict[str, Any], task: AsyncTask) -> Dict[str, Any]:
        """Handle data export tasks"""
        
        # This would implement large data exports
        import time
        
        # Simulate long-running export
        total_records = task_data.get("total_records", 10000)
        batch_size = 1000
        
        for i in range(0, total_records, batch_size):
            time.sleep(0.1)  # Simulate processing time
            task.progress = (i + batch_size) / total_records * 100
        
        return {
            "success": True,
            "export_format": task_data.get("format", "csv"),
            "records_exported": total_records,
            "file_path": f"/tmp/export_{task.id}.csv"
        }
    
    async def _handle_calculate_trends(self, task_data: Dict[str, Any], task: AsyncTask) -> Dict[str, Any]:
        """Handle trend calculation tasks"""
        
        from .trend_service import TrendService
        from backend.core.database import get_db
        
        db = next(get_db())
        try:
            service = TrendService(db)
            
            # Update progress
            task.progress = 20.0
            
            # Get trend data
            metrics = task_data.get("metrics", ["revenue", "orders"])
            start_date = datetime.fromisoformat(task_data["start_date"]).date()
            end_date = datetime.fromisoformat(task_data["end_date"]).date()
            
            task.progress = 50.0
            
            trend_data = service.get_multi_metric_trend(
                start_date=start_date,
                end_date=end_date,
                metrics=metrics,
                granularity=task_data.get("granularity", "daily")
            )
            
            task.progress = 90.0
            
            return {
                "success": True,
                "metrics": metrics,
                "trends": {
                    metric: [
                        {
                            "date": point.date.isoformat(),
                            "value": point.value,
                            "change_percentage": point.change_percentage
                        }
                        for point in points
                    ]
                    for metric, points in trend_data.items()
                }
            }
            
        finally:
            db.close()
    
    def _handle_update_snapshots(self, task_data: Dict[str, Any], task: AsyncTask) -> Dict[str, Any]:
        """Handle snapshot update tasks"""
        
        # This would implement snapshot updates
        import time
        
        date_range = task_data.get("date_range", 30)
        
        for day in range(date_range):
            time.sleep(0.05)  # Simulate processing
            task.progress = (day + 1) / date_range * 100
        
        return {
            "success": True,
            "snapshots_updated": date_range,
            "date_range": f"{date_range} days"
        }
    
    def _handle_refresh_views(self, task_data: Dict[str, Any], task: AsyncTask) -> Dict[str, Any]:
        """Handle materialized view refresh"""
        
        from backend.core.database import get_db
        from sqlalchemy import text
        
        db = next(get_db())
        try:
            views = task_data.get("views", ["mv_top_performers", "mv_daily_summary"])
            
            for i, view in enumerate(views):
                task.progress = (i / len(views)) * 100
                
                # Refresh the view
                db.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view};"))
                db.commit()
            
            task.progress = 100.0
            
            return {
                "success": True,
                "views_refreshed": views,
                "total_views": len(views)
            }
            
        finally:
            db.close()


# Global async processor instance
async_processor = AsyncTaskProcessor()


# Utility functions for common async operations
async def submit_large_report_task(
    filters: Dict[str, Any],
    user_id: int,
    limit: int = 50000
) -> str:
    """Submit a large report generation task"""
    
    return await async_processor.submit_task(
        task_type="generate_large_report",
        task_data={
            "filters": filters,
            "limit": limit
        },
        priority=TaskPriority.NORMAL,
        created_by=user_id
    )


async def submit_export_task(
    export_format: str,
    data_query: Dict[str, Any],
    user_id: int
) -> str:
    """Submit a data export task"""
    
    return await async_processor.submit_task(
        task_type="export_data",
        task_data={
            "format": export_format,
            "query": data_query,
            "total_records": data_query.get("estimated_records", 10000)
        },
        priority=TaskPriority.HIGH,
        created_by=user_id
    )


async def submit_trend_calculation_task(
    metrics: List[str],
    start_date: str,
    end_date: str,
    user_id: int
) -> str:
    """Submit a trend calculation task"""
    
    return await async_processor.submit_task(
        task_type="calculate_trends",
        task_data={
            "metrics": metrics,
            "start_date": start_date,
            "end_date": end_date,
            "granularity": "daily"
        },
        priority=TaskPriority.NORMAL,
        created_by=user_id
    )
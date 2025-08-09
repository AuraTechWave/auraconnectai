# backend/modules/menu/tasks/recipe_cost_tasks.py

"""
Background tasks for recipe cost calculations.
Uses Celery for async processing of bulk operations.
"""

from celery import Celery, Task
from celery.result import AsyncResult
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.config import settings
from ..services.recipe_service import RecipeService
from ..services.recipe_cache_service import get_recipe_cache_service
from ..models.recipe_models import Recipe, RecipeStatus

logger = logging.getLogger(__name__)

# Initialize Celery
celery_app = Celery(
    'recipe_tasks',
    broker=settings.redis_url or 'redis://localhost:6379/0',
    backend=settings.redis_url or 'redis://localhost:6379/0'
)

# Configure Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,
)


class RecipeCostTask(Task):
    """Base task class with database session management"""
    
    def __init__(self):
        self._db: Optional[Session] = None
        self._cache_service = None
    
    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db
    
    @property
    def cache_service(self):
        if self._cache_service is None:
            self._cache_service = get_recipe_cache_service()
        return self._cache_service
    
    def after_return(self, *args, **kwargs):
        if self._db is not None:
            self._db.close()
            self._db = None


@celery_app.task(base=RecipeCostTask, bind=True, name='recipe.calculate_cost')
def recalculate_recipe_cost_async(self, recipe_id: int, user_id: int) -> Dict[str, Any]:
    """
    Asynchronously recalculate cost for a single recipe.
    
    Args:
        recipe_id: ID of the recipe to recalculate
        user_id: ID of the user triggering the recalculation
        
    Returns:
        Dict with calculation results
    """
    try:
        recipe_service = RecipeService(self.db)
        
        # Update task progress
        self.update_state(state='PROGRESS', meta={'current': 0, 'total': 1})
        
        # Perform calculation
        cost_analysis = recipe_service.calculate_recipe_cost(recipe_id, use_cache=False)
        
        # Invalidate related caches
        self.cache_service.invalidate_recipe_cache(recipe_id)
        
        # Store result in cache
        self.cache_service.set('cost_analysis', cost_analysis.dict(), recipe_id)
        
        # Update task progress
        self.update_state(state='PROGRESS', meta={'current': 1, 'total': 1})
        
        return {
            'recipe_id': recipe_id,
            'status': 'success',
            'cost': cost_analysis.total_cost,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error calculating recipe cost {recipe_id}: {str(e)}")
        return {
            'recipe_id': recipe_id,
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }


@celery_app.task(base=RecipeCostTask, bind=True, name='recipe.bulk_calculate_costs')
def bulk_recalculate_costs_async(
    self, 
    recipe_ids: Optional[List[int]] = None,
    user_id: int = None,
    batch_size: int = 50
) -> Dict[str, Any]:
    """
    Asynchronously recalculate costs for multiple recipes.
    
    Args:
        recipe_ids: List of recipe IDs to recalculate (None for all)
        user_id: ID of the user triggering the recalculation
        batch_size: Number of recipes to process in each batch
        
    Returns:
        Dict with bulk calculation results
    """
    start_time = datetime.utcnow()
    results = {
        'total': 0,
        'success': 0,
        'failed': 0,
        'errors': [],
        'processing_time': 0
    }
    
    try:
        recipe_service = RecipeService(self.db)
        
        # Get recipes to process
        if recipe_ids:
            recipes = self.db.query(Recipe).filter(
                Recipe.id.in_(recipe_ids),
                Recipe.deleted_at.is_(None)
            ).all()
        else:
            recipes = self.db.query(Recipe).filter(
                Recipe.deleted_at.is_(None),
                Recipe.is_active == True
            ).all()
        
        results['total'] = len(recipes)
        
        # Process in batches
        for i in range(0, len(recipes), batch_size):
            batch = recipes[i:i + batch_size]
            
            # Update progress
            self.update_state(
                state='PROGRESS',
                meta={
                    'current': i,
                    'total': results['total'],
                    'success': results['success'],
                    'failed': results['failed']
                }
            )
            
            # Process batch
            for recipe in batch:
                try:
                    cost_analysis = recipe_service.calculate_recipe_cost(
                        recipe.id, 
                        use_cache=False
                    )
                    
                    # Cache the result
                    self.cache_service.set(
                        'cost_analysis', 
                        cost_analysis.dict(), 
                        recipe.id
                    )
                    
                    results['success'] += 1
                    
                except Exception as e:
                    logger.error(f"Error processing recipe {recipe.id}: {str(e)}")
                    results['failed'] += 1
                    results['errors'].append({
                        'recipe_id': recipe.id,
                        'error': str(e)
                    })
            
            # Commit batch
            self.db.commit()
        
        # Final progress update
        self.update_state(
            state='PROGRESS',
            meta={
                'current': results['total'],
                'total': results['total'],
                'success': results['success'],
                'failed': results['failed']
            }
        )
        
    except Exception as e:
        logger.error(f"Error in bulk cost calculation: {str(e)}")
        results['errors'].append({
            'error': f"Bulk processing error: {str(e)}"
        })
    
    # Calculate processing time
    results['processing_time'] = (datetime.utcnow() - start_time).total_seconds()
    results['timestamp'] = datetime.utcnow().isoformat()
    
    # Cache the bulk result
    if not recipe_ids:  # Only cache if processing all recipes
        self.cache_service.set(
            'bulk_cost_calculation',
            results,
            'all',
            ttl=1800  # 30 minutes
        )
    
    return results


@celery_app.task(name='recipe.schedule_recalculation')
def schedule_cost_recalculation(
    recipe_ids: Optional[List[int]] = None,
    delay_seconds: int = 0,
    priority: int = 5
) -> str:
    """
    Schedule a cost recalculation task.
    
    Args:
        recipe_ids: List of recipe IDs to recalculate
        delay_seconds: Delay before starting the task
        priority: Task priority (0-10, higher is more important)
        
    Returns:
        Task ID for tracking
    """
    task = bulk_recalculate_costs_async.apply_async(
        args=[recipe_ids],
        countdown=delay_seconds,
        priority=priority
    )
    
    return task.id


def get_task_status(task_id: str) -> Dict[str, Any]:
    """
    Get the status of a background task.
    
    Args:
        task_id: Celery task ID
        
    Returns:
        Dict with task status and result
    """
    result = AsyncResult(task_id, app=celery_app)
    
    response = {
        'task_id': task_id,
        'status': result.status,
        'current': 0,
        'total': 0,
        'result': None
    }
    
    if result.state == 'PENDING':
        response['status'] = 'pending'
    elif result.state == 'PROGRESS':
        response['status'] = 'processing'
        response.update(result.info)
    elif result.state == 'SUCCESS':
        response['status'] = 'completed'
        response['result'] = result.result
    elif result.state == 'FAILURE':
        response['status'] = 'failed'
        response['error'] = str(result.info)
    
    return response
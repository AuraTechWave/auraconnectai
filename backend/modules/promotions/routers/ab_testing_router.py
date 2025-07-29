# backend/modules/promotions/routers/ab_testing_router.py

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from datetime import datetime

from backend.core.database import get_db
from backend.modules.auth.dependencies import get_current_user, require_admin

from ..services.ab_testing_service import ABTestingService
from ..schemas.promotion_schemas import PromotionCreate

router = APIRouter(prefix="/ab-testing", tags=["A/B Testing"])


@router.post("/create")
def create_ab_test(
    test_name: str = Body(...),
    control_promotion: PromotionCreate = Body(...),
    variant_promotions: List[PromotionCreate] = Body(...),
    test_config: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """
    Create an A/B test with control and variant promotions
    
    Test Config Options:
    - control_traffic_percentage: Percentage of traffic for control (default 50)
    - variant_traffic_percentages: List of traffic percentages for each variant
    - duration_days: Duration of the test in days
    - minimum_sample_size: Minimum sample size before results are meaningful
    - success_metric: Primary metric to optimize (conversion_rate, revenue, etc.)
    - confidence_level: Required confidence level for significance (default 95)
    """
    try:
        if len(variant_promotions) == 0:
            raise HTTPException(status_code=400, detail="At least one variant promotion is required")
        
        if len(variant_promotions) > 5:
            raise HTTPException(status_code=400, detail="Maximum 5 variant promotions allowed")
        
        service = ABTestingService(db)
        result = service.create_ab_test(
            test_name=test_name,
            control_promotion=control_promotion,
            variant_promotions=variant_promotions,
            test_config=test_config
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create A/B test: {str(e)}")


@router.post("/{test_id}/start")
def start_ab_test(
    test_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Start an A/B test by activating all its promotions"""
    try:
        service = ABTestingService(db)
        result = service.start_ab_test(test_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start A/B test: {str(e)}")


@router.post("/{test_id}/stop")
def stop_ab_test(
    test_id: str,
    winning_variant: Optional[str] = Body(None),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Stop an A/B test and optionally declare a winner"""
    try:
        service = ABTestingService(db)
        result = service.stop_ab_test(test_id, winning_variant)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop A/B test: {str(e)}")


@router.post("/{test_id}/assign")
def assign_user_to_variant(
    test_id: str,
    customer_id: Optional[int] = Body(None),
    session_id: Optional[str] = Body(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Assign a user to a variant in an A/B test
    
    This endpoint is used by the frontend to determine which promotion
    variant to show to a user. The assignment is deterministic based on
    the user identifier, ensuring consistent experience.
    """
    try:
        if not customer_id and not session_id:
            raise HTTPException(status_code=400, detail="Either customer_id or session_id must be provided")
        
        service = ABTestingService(db)
        assignment = service.assign_user_to_variant(
            test_id=test_id,
            customer_id=customer_id,
            session_id=session_id
        )
        return assignment
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to assign user to variant: {str(e)}")


@router.get("/{test_id}/results")
def get_ab_test_results(
    test_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get comprehensive results for an A/B test"""
    try:
        service = ABTestingService(db)
        results = service.get_ab_test_results(test_id)
        return results
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get A/B test results: {str(e)}")


@router.get("/active")
def get_active_ab_tests(
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get all currently active A/B tests"""
    try:
        service = ABTestingService(db)
        active_tests = service.get_active_ab_tests()
        return {
            "total_active_tests": len(active_tests),
            "active_tests": active_tests
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get active A/B tests: {str(e)}")


@router.get("/all")
def get_all_ab_tests(
    status_filter: Optional[str] = Query(None, regex="^(draft|active|stopped|winner|loser)$"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get all A/B tests with optional filtering"""
    try:
        from ..models.promotion_models import Promotion
        
        query = db.query(Promotion).filter(
            Promotion.metadata['ab_test'].isnot(None)
        )
        
        if status_filter:
            query = query.filter(
                Promotion.metadata['ab_test']['test_status'].astext == status_filter
            )
        
        # Get unique tests (group by test_id)
        promotions = query.offset(offset).limit(limit * 10).all()  # Get more to account for duplicates
        
        tests_by_id = {}
        for promotion in promotions:
            ab_test_data = promotion.metadata['ab_test']
            test_id = ab_test_data['test_id']
            
            if test_id not in tests_by_id:
                tests_by_id[test_id] = {
                    'test_id': test_id,
                    'test_name': ab_test_data['test_name'],
                    'test_status': ab_test_data.get('test_status', 'unknown'),
                    'created_at': ab_test_data.get('created_at'),
                    'started_at': ab_test_data.get('started_at'),
                    'stopped_at': ab_test_data.get('stopped_at'),
                    'variant_count': 0,
                    'control_promotion_id': None,
                    'variant_promotion_ids': []
                }
            
            test_info = tests_by_id[test_id]
            test_info['variant_count'] += 1
            
            if ab_test_data['variant_type'] == 'control':
                test_info['control_promotion_id'] = promotion.id
            else:
                test_info['variant_promotion_ids'].append(promotion.id)
        
        # Apply limit after deduplication
        tests_list = list(tests_by_id.values())[offset:offset + limit]
        
        return {
            "total_tests": len(tests_by_id),
            "returned_tests": len(tests_list),
            "offset": offset,
            "limit": limit,
            "tests": tests_list
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get A/B tests: {str(e)}")


@router.get("/{test_id}/summary")
def get_ab_test_summary(
    test_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get a quick summary of an A/B test"""
    try:
        service = ABTestingService(db)
        results = service.get_ab_test_results(test_id)
        
        # Extract key metrics for summary
        total_conversions = sum(v['metrics']['conversions'] for v in results['variant_results'])
        total_revenue = sum(v['metrics']['total_revenue'] for v in results['variant_results'])
        
        control_variant = next((v for v in results['variant_results'] if v['variant_type'] == 'control'), None)
        best_variant = results.get('winner')
        
        summary = {
            'test_id': test_id,
            'test_name': results['test_name'],
            'status': results['test_status'],
            'duration_days': None,
            'total_variants': len(results['variant_results']),
            'total_conversions': total_conversions,
            'total_revenue': round(total_revenue, 2),
            'control_conversion_rate': control_variant['metrics']['conversion_rate'] if control_variant else 0,
            'winner': best_variant,
            'statistical_significance': results['statistical_analysis'].get('overall_significance', 'unknown'),
            'created_at': results.get('started_at') or results['variant_results'][0].get('created_at') if results['variant_results'] else None
        }
        
        # Calculate duration if test has started and stopped
        if results.get('started_at') and results.get('stopped_at'):
            started = datetime.fromisoformat(results['started_at'])
            stopped = datetime.fromisoformat(results['stopped_at'])
            summary['duration_days'] = (stopped - started).days
        
        return summary
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get A/B test summary: {str(e)}")


@router.post("/{test_id}/extend")
def extend_ab_test(
    test_id: str,
    additional_days: int = Body(..., ge=1, le=30),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Extend the duration of an active A/B test"""
    try:
        from ..models.promotion_models import Promotion
        
        test_promotions = db.query(Promotion).filter(
            Promotion.metadata['ab_test']['test_id'].astext == test_id
        ).all()
        
        if not test_promotions:
            raise HTTPException(status_code=404, detail="A/B test not found")
        
        # Check if test is active
        test_status = test_promotions[0].metadata['ab_test'].get('test_status')
        if test_status != 'active':
            raise HTTPException(status_code=400, detail=f"Cannot extend test with status: {test_status}")
        
        # Extend end date for all test promotions
        for promotion in test_promotions:
            if promotion.end_date:
                promotion.end_date = promotion.end_date + timedelta(days=additional_days)
            
            # Update test config
            test_config = promotion.metadata['ab_test']['test_config']
            current_duration = test_config.get('duration_days', 0)
            test_config['duration_days'] = current_duration + additional_days
            test_config['extended_at'] = datetime.utcnow().isoformat()
            test_config['extended_by_days'] = additional_days
            
            promotion.metadata['ab_test']['test_config'] = test_config
        
        db.commit()
        
        return {
            'test_id': test_id,
            'extended_by_days': additional_days,
            'new_end_date': test_promotions[0].end_date.isoformat() if test_promotions[0].end_date else None,
            'extended_at': datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to extend A/B test: {str(e)}")


@router.get("/{test_id}/config")
def get_ab_test_config(
    test_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get the configuration of an A/B test"""
    try:
        from ..models.promotion_models import Promotion
        
        promotion = db.query(Promotion).filter(
            Promotion.metadata['ab_test']['test_id'].astext == test_id,
            Promotion.metadata['ab_test']['variant_type'].astext == 'control'
        ).first()
        
        if not promotion:
            raise HTTPException(status_code=404, detail="A/B test not found")
        
        ab_test_data = promotion.metadata['ab_test']
        
        return {
            'test_id': test_id,
            'test_name': ab_test_data['test_name'],
            'test_config': ab_test_data['test_config'],
            'created_at': ab_test_data.get('created_at'),
            'status': ab_test_data.get('test_status', 'unknown')
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get A/B test config: {str(e)}")


@router.post("/validate-config")
def validate_ab_test_config(
    test_config: Dict[str, Any] = Body(...),
    variant_count: int = Body(..., ge=1, le=5),
    current_user = Depends(require_admin)
):
    """Validate A/B test configuration before creating the test"""
    try:
        from ..services.ab_testing_service import ABTestingService
        
        # Create a temporary service instance just for validation
        service = ABTestingService(None)  # We don't need DB for validation
        service._validate_ab_test_config(test_config, variant_count)
        
        return {
            'valid': True,
            'message': 'Configuration is valid',
            'validated_config': test_config
        }
        
    except ValueError as e:
        return {
            'valid': False,
            'message': str(e),
            'validated_config': test_config
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to validate config: {str(e)}")
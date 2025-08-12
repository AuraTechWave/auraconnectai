# Scheduling Conflict Bug Fix

## Problem Description

The `generate_demand_aware_schedule` function had a critical bug where it would assign the same staff member to overlapping shifts during the same generation run. This occurred because:

1. **Overlapping Shift Blocks**: The original implementation used overlapping shift blocks:
   - 6:00-14:00 (Morning)
   - 10:00-18:00 (Lunch/Dinner) 
   - 16:00-23:59 (Evening)

2. **Insufficient Conflict Detection**: The conflict detection only checked against persisted shifts in the database, not against shifts being generated in-memory during the same run.

3. **Staff Assignment Logic**: The function would assign staff to each shift block independently without considering that the same staff member could be assigned to multiple overlapping blocks.

## Root Cause

The core issue was in the shift block definition and the lack of proper in-memory conflict tracking during the generation process. The function would:

1. Create overlapping shift blocks
2. For each block, calculate required staff
3. Assign available staff to each block independently
4. Only check conflicts against existing database records

This resulted in scenarios where a staff member could be assigned to both a 6:00-14:00 shift and a 10:00-18:00 shift, creating a 4-hour overlap.

## Solution

### 1. Fixed Shift Blocks

Changed the shift blocks to be non-overlapping:

```python
# Before (overlapping)
shift_blocks = [
    (time(6, 0), time(14, 0)),
    (time(10, 0), time(18, 0)),  # Overlaps with morning
    (time(16, 0), time(23, 59)), # Overlaps with lunch
]

# After (non-overlapping)
shift_blocks = [
    (time(6, 0), time(14, 0)),   # Morning shift
    (time(14, 0), time(22, 0)),  # Afternoon/Evening shift
    (time(22, 0), time(6, 0)),   # Night shift (overnight)
]
```

### 2. Enhanced Conflict Tracking

The existing `_pick_best_staff_for_shift_with_tracking` method already had proper in-memory conflict tracking, but it wasn't being used effectively due to the overlapping shift blocks.

### 3. Improved Demand Analysis

Enhanced the demand estimation to work with hourly data instead of just peak orders:

```python
def _estimate_peak_orders(self, target_date: date, location_id: int, demand_lookback_days: int) -> Dict[int, int]:
    """Returns hourly demand for the entire day instead of just peak"""
    # Returns {hour: order_count} for hours 0-23
```

### 4. Flexible Scheduling Option

Added a new `generate_flexible_demand_schedule` method that creates shifts based on actual demand patterns rather than fixed blocks:

```python
def generate_flexible_demand_schedule(
    self,
    start_date: date,
    end_date: date,
    location_id: int,
    # ... other parameters
) -> List[EnhancedShift]:
    """Creates shifts that start and end based on actual demand peaks"""
```

## API Changes

### New Parameters

Added to `ScheduleGenerationRequest`:

```python
class ScheduleGenerationRequest(BaseModel):
    # ... existing fields ...
    use_flexible_shifts: bool = False
    min_shift_hours: int = 4
    max_shift_hours: int = 8
```

### New Response Strategy

The API now returns the strategy used:

```python
{
    "message": "Schedule generated",
    "strategy": "templates" | "demand_aware" | "flexible_demand",
    "shifts_created": 42,
    "start_date": "2024-01-01",
    "end_date": "2024-01-07"
}
```

## Testing

Created comprehensive tests in `test_scheduling_conflict_fix.py` that verify:

1. No overlapping shifts are created for the same staff member
2. Minimum rest periods are respected
3. Both fixed-block and flexible scheduling work correctly
4. Shift blocks are properly non-overlapping

## Migration Notes

### For Existing Users

- **No breaking changes**: Existing API calls will continue to work
- **Default behavior unchanged**: `use_historical_demand=False` still uses template-based scheduling
- **New features opt-in**: Flexible scheduling requires `use_flexible_shifts=True`

### For New Implementations

- **Recommended**: Use `use_historical_demand=True` with `use_flexible_shifts=True` for optimal staffing
- **Fallback**: Use `use_historical_demand=True` with `use_flexible_shifts=False` for fixed-block scheduling
- **Legacy**: Use `use_historical_demand=False` for template-based scheduling

## Performance Impact

- **Minimal**: The fix primarily changes shift block definitions and adds optional flexible scheduling
- **Improved**: Better conflict detection prevents invalid schedules from being created
- **Scalable**: The flexible scheduling option can handle complex demand patterns more efficiently

## Future Enhancements

1. **Machine Learning**: Integrate ML models for demand prediction
2. **Multi-location**: Support for coordinated scheduling across multiple locations
3. **Real-time Adjustments**: Dynamic schedule adjustments based on real-time demand
4. **Staff Preferences**: Consider staff preferences and availability patterns
5. **Cost Optimization**: Optimize for labor costs while maintaining service quality

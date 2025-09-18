"""
Cache preloading service based on usage patterns.

Analyzes cache access patterns and proactively loads
frequently accessed data during low-traffic periods.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Set
from datetime import datetime, timedelta, time
from collections import defaultdict, Counter
from dataclasses import dataclass
from enum import Enum

from .redis_cache import redis_cache
from .memory_cache import memory_cache

logger = logging.getLogger(__name__)


class AccessPattern(Enum):
    """Types of access patterns."""
    DAILY = "daily"  # Accessed at specific times each day
    PERIODIC = "periodic"  # Accessed at regular intervals
    BURST = "burst"  # Accessed in bursts
    CONSTANT = "constant"  # Accessed consistently


@dataclass
class CacheAccessRecord:
    """Record of a cache access."""
    key: str
    namespace: str
    timestamp: datetime
    hit: bool
    latency_ms: float
    size_bytes: Optional[int] = None


@dataclass
class PatternAnalysis:
    """Analysis results for a cache key."""
    key: str
    namespace: str
    pattern_type: AccessPattern
    access_count: int
    avg_latency_ms: float
    peak_hours: List[int]  # Hours of day with most accesses
    predictability_score: float  # 0-1, how predictable the access pattern is
    preload_priority: int  # 1-10, higher means more important to preload


class CachePatternAnalyzer:
    """Analyzes cache access patterns to identify preloading candidates."""
    
    def __init__(
        self,
        history_days: int = 7,
        min_access_count: int = 10
    ):
        self.history_days = history_days
        self.min_access_count = min_access_count
        self.access_history: List[CacheAccessRecord] = []
        self.pattern_cache: Dict[str, PatternAnalysis] = {}
        
    def record_access(
        self,
        key: str,
        namespace: str,
        hit: bool,
        latency_ms: float,
        size_bytes: Optional[int] = None
    ):
        """Record a cache access."""
        record = CacheAccessRecord(
            key=key,
            namespace=namespace,
            timestamp=datetime.utcnow(),
            hit=hit,
            latency_ms=latency_ms,
            size_bytes=size_bytes
        )
        self.access_history.append(record)
        
        # Clean old records periodically
        if len(self.access_history) % 1000 == 0:
            self._clean_old_records()
    
    def _clean_old_records(self):
        """Remove access records older than history_days."""
        cutoff = datetime.utcnow() - timedelta(days=self.history_days)
        self.access_history = [
            record for record in self.access_history
            if record.timestamp > cutoff
        ]
    
    def analyze_patterns(self) -> List[PatternAnalysis]:
        """Analyze access patterns and identify preloading candidates."""
        # Group accesses by key
        key_accesses = defaultdict(list)
        for record in self.access_history:
            key = f"{record.namespace}:{record.key}"
            key_accesses[key].append(record)
        
        analyses = []
        
        for key, accesses in key_accesses.items():
            if len(accesses) < self.min_access_count:
                continue
            
            namespace, cache_key = key.split(":", 1)
            
            # Analyze access pattern
            pattern_type = self._identify_pattern(accesses)
            peak_hours = self._find_peak_hours(accesses)
            predictability = self._calculate_predictability(accesses)
            
            # Calculate average latency
            avg_latency = sum(a.latency_ms for a in accesses) / len(accesses)
            
            # Determine preload priority
            priority = self._calculate_priority(
                len(accesses),
                avg_latency,
                predictability,
                pattern_type
            )
            
            analysis = PatternAnalysis(
                key=cache_key,
                namespace=namespace,
                pattern_type=pattern_type,
                access_count=len(accesses),
                avg_latency_ms=avg_latency,
                peak_hours=peak_hours,
                predictability_score=predictability,
                preload_priority=priority
            )
            
            analyses.append(analysis)
            self.pattern_cache[key] = analysis
        
        # Sort by priority
        analyses.sort(key=lambda x: x.preload_priority, reverse=True)
        
        return analyses
    
    def _identify_pattern(self, accesses: List[CacheAccessRecord]) -> AccessPattern:
        """Identify the type of access pattern."""
        # Calculate time between accesses
        intervals = []
        for i in range(1, len(accesses)):
            interval = (accesses[i].timestamp - accesses[i-1].timestamp).total_seconds()
            intervals.append(interval)
        
        if not intervals:
            return AccessPattern.CONSTANT
        
        avg_interval = sum(intervals) / len(intervals)
        std_dev = (sum((x - avg_interval) ** 2 for x in intervals) / len(intervals)) ** 0.5
        
        # Coefficient of variation
        cv = std_dev / avg_interval if avg_interval > 0 else 0
        
        # Analyze hourly distribution
        hourly_counts = Counter(a.timestamp.hour for a in accesses)
        max_hour_count = max(hourly_counts.values())
        total_hours = len(hourly_counts)
        
        # Decision logic
        if cv < 0.3:  # Low variation in intervals
            return AccessPattern.PERIODIC
        elif total_hours <= 6 and max_hour_count > len(accesses) * 0.3:
            return AccessPattern.DAILY
        elif cv > 1.5:  # High variation
            return AccessPattern.BURST
        else:
            return AccessPattern.CONSTANT
    
    def _find_peak_hours(self, accesses: List[CacheAccessRecord]) -> List[int]:
        """Find hours of day with most accesses."""
        hourly_counts = Counter(a.timestamp.hour for a in accesses)
        
        # Get top 3 hours
        peak_hours = [
            hour for hour, _ in hourly_counts.most_common(3)
        ]
        
        return sorted(peak_hours)
    
    def _calculate_predictability(self, accesses: List[CacheAccessRecord]) -> float:
        """Calculate how predictable the access pattern is (0-1)."""
        # Check hourly consistency
        hourly_counts = Counter(a.timestamp.hour for a in accesses)
        total_accesses = sum(hourly_counts.values())
        
        # Calculate entropy
        entropy = 0
        for count in hourly_counts.values():
            if count > 0:
                p = count / total_accesses
                entropy -= p * (p if p == 0 else p * (1 if p == 1 else -p))
        
        # Normalize entropy to 0-1 (lower entropy = more predictable)
        max_entropy = -(1/24) * (1/24) * 24  # Maximum when evenly distributed
        predictability = 1 - (entropy / max_entropy)
        
        return min(max(predictability, 0), 1)
    
    def _calculate_priority(
        self,
        access_count: int,
        avg_latency: float,
        predictability: float,
        pattern: AccessPattern
    ) -> int:
        """Calculate preload priority (1-10)."""
        # Base score on access frequency
        frequency_score = min(access_count / 100, 1.0) * 3
        
        # Latency impact (higher latency = higher priority)
        latency_score = min(avg_latency / 100, 1.0) * 3
        
        # Predictability bonus
        predictability_score = predictability * 2
        
        # Pattern bonus
        pattern_scores = {
            AccessPattern.DAILY: 2,
            AccessPattern.PERIODIC: 1.5,
            AccessPattern.CONSTANT: 1,
            AccessPattern.BURST: 0.5
        }
        pattern_score = pattern_scores.get(pattern, 1)
        
        total_score = frequency_score + latency_score + predictability_score + pattern_score
        
        # Convert to 1-10 scale
        return max(1, min(10, int(total_score)))


class CachePreloader:
    """Preloads cache based on usage patterns."""
    
    def __init__(
        self,
        analyzer: CachePatternAnalyzer,
        max_concurrent_preloads: int = 10,
        preload_threshold_priority: int = 5
    ):
        self.analyzer = analyzer
        self.max_concurrent_preloads = max_concurrent_preloads
        self.preload_threshold_priority = preload_threshold_priority
        self.preload_queue: List[PatternAnalysis] = []
        self.is_running = False
        
    asyncختار_preload_candidates(self) -> List[PatternAnalysis]:
        """Select candidates for preloading based on current time and patterns."""
        current_hour = datetime.utcnow().hour
        patterns = self.analyzer.analyze_patterns()
        
        candidates = []
        
        for pattern in patterns:
            if pattern.preload_priority < self.preload_threshold_priority:
                continue
            
            # Check if we should preload based on pattern
            should_preload = False
            
            if pattern.pattern_type == AccessPattern.DAILY:
                # Preload 30 minutes before peak hours
                for peak_hour in pattern.peak_hours:
                    preload_hour = (peak_hour - 1) % 24
                    if current_hour == preload_hour:
                        should_preload = True
                        break
            
            elif pattern.pattern_type == AccessPattern.PERIODIC:
                # Always preload periodic access patterns
                should_preload = True
            
            elif pattern.pattern_type == AccessPattern.CONSTANT:
                # Preload if not in cache
                should_preload = True
            
            if should_preload:
                candidates.append(pattern)
        
        return candidates
    
    async def preload_cache_entry(self, pattern: PatternAnalysis) -> bool:
        """Preload a single cache entry."""
        try:
            # This would need to be implemented based on your specific data loading logic
            # For now, we'll just log what would be preloaded
            logger.info(
                f"Preloading cache entry: {pattern.namespace}:{pattern.key} "
                f"(priority: {pattern.preload_priority}, pattern: {pattern.pattern_type.value})"
            )
            
            # In a real implementation, you would:
            # 1. Fetch the data from the database
            # 2. Store it in cache with appropriate TTL
            # 3. Optionally store in memory cache as well
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to preload {pattern.key}: {e}")
            return False
    
    async def run_preload_cycle(self):
        """Run a single preload cycle."""
        candidates = await self._get_preload_candidates()
        
        if not candidates:
            logger.debug("No cache entries to preload")
            return
        
        logger.info(f"Preloading {len(candidates)} cache entries")
        
        # Preload in batches
        semaphore = asyncio.Semaphore(self.max_concurrent_preloads)
        
        async def preload_with_limit(pattern):
            async with semaphore:
                return await self.preload_cache_entry(pattern)
        
        tasks = [preload_with_limit(pattern) for pattern in candidates]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful = sum(1 for r in results if r is True)
        logger.info(f"Successfully preloaded {successful}/{len(candidates)} entries")
    
    async def start_auto_preloader(self, interval_minutes: int = 30):
        """Start automatic preloading service."""
        self.is_running = True
        
        while self.is_running:
            try:
                await self.run_preload_cycle()
            except Exception as e:
                logger.error(f"Error in preload cycle: {e}")
            
            await asyncio.sleep(interval_minutes * 60)
    
    def stop(self):
        """Stop the preloader."""
        self.is_running = False
    
    async def get_preload_stats(self) -> Dict[str, Any]:
        """Get preloading statistics."""
        patterns = self.analyzer.pattern_cache
        
        pattern_counts = Counter(p.pattern_type.value for p in patterns.values())
        priority_distribution = Counter(p.preload_priority for p in patterns.values())
        
        return {
            "total_tracked_keys": len(patterns),
            "pattern_distribution": dict(pattern_counts),
            "priority_distribution": dict(priority_distribution),
            "high_priority_keys": [
                {
                    "key": p.key,
                    "namespace": p.namespace,
                    "priority": p.preload_priority,
                    "pattern": p.pattern_type.value,
                    "access_count": p.access_count
                }
                for p in patterns.values()
                if p.preload_priority >= 8
            ]
        }


# Global instances
pattern_analyzer = CachePatternAnalyzer()
cache_preloader = CachePreloader(pattern_analyzer)


# Export public interface
__all__ = [
    "pattern_analyzer",
    "cache_preloader",
    "CachePatternAnalyzer",
    "CachePreloader",
    "AccessPattern",
    "PatternAnalysis"
]
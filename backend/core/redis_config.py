# backend/core/redis_config.py

import redis.asyncio as redis
from redis.sentinel import Sentinel
from redis.asyncio.cluster import RedisCluster
from typing import Optional, List, Dict, Any
import logging
from urllib.parse import urlparse

from .config import settings


logger = logging.getLogger(__name__)


class RedisConnectionManager:
    """
    Manages Redis connections with support for:
    - Single instance
    - Redis Sentinel
    - Redis Cluster
    """
    
    def __init__(self):
        self.mode = settings.REDIS_MODE  # 'single', 'sentinel', 'cluster'
        self.client: Optional[redis.Redis] = None
        self._sentinel: Optional[Sentinel] = None
        self._cluster: Optional[RedisCluster] = None
    
    async def get_client(self) -> redis.Redis:
        """Get Redis client based on configured mode"""
        if self.client:
            return self.client
        
        if self.mode == 'sentinel':
            self.client = await self._create_sentinel_client()
        elif self.mode == 'cluster':
            self.client = await self._create_cluster_client()
        else:
            self.client = await self._create_single_client()
        
        # Test connection
        await self.client.ping()
        logger.info(f"Redis connected in {self.mode} mode")
        
        return self.client
    
    async def _create_single_client(self) -> redis.Redis:
        """Create single Redis instance client"""
        return await redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            retry_on_timeout=True,
            retry_on_error=[ConnectionError, TimeoutError],
            health_check_interval=30
        )
    
    async def _create_sentinel_client(self) -> redis.Redis:
        """Create Redis Sentinel client"""
        # Parse sentinel nodes from config
        sentinel_nodes = self._parse_sentinel_nodes(settings.REDIS_SENTINEL_NODES)
        
        # Create async sentinel
        from redis.asyncio.sentinel import Sentinel as AsyncSentinel
        
        self._sentinel = AsyncSentinel(
            sentinel_nodes,
            socket_timeout=0.1,
            decode_responses=True
        )
        
        # Get master client
        master_name = settings.REDIS_SENTINEL_MASTER or 'mymaster'
        client = self._sentinel.master_for(
            master_name,
            redis_class=redis.Redis,
            decode_responses=True,
            retry_on_timeout=True,
            health_check_interval=30
        )
        
        return client
    
    async def _create_cluster_client(self) -> redis.Redis:
        """Create Redis Cluster client"""
        # Parse cluster nodes
        startup_nodes = self._parse_cluster_nodes(settings.REDIS_CLUSTER_NODES)
        
        # Create cluster client
        self._cluster = await RedisCluster.from_startup_nodes(
            startup_nodes,
            decode_responses=True,
            skip_full_coverage_check=True,
            retry_on_timeout=True,
            retry_on_error=[ConnectionError, TimeoutError],
            health_check_interval=30,
            cluster_error_retry_attempts=3
        )
        
        return self._cluster
    
    def _parse_sentinel_nodes(self, nodes_str: str) -> List[tuple]:
        """Parse sentinel nodes from configuration string"""
        # Format: "host1:port1,host2:port2"
        nodes = []
        for node in nodes_str.split(','):
            host, port = node.strip().split(':')
            nodes.append((host, int(port)))
        return nodes
    
    def _parse_cluster_nodes(self, nodes_str: str) -> List[Dict[str, Any]]:
        """Parse cluster nodes from configuration string"""
        # Format: "host1:port1,host2:port2"
        nodes = []
        for node in nodes_str.split(','):
            host, port = node.strip().split(':')
            nodes.append({
                'host': host,
                'port': int(port)
            })
        return nodes
    
    async def close(self):
        """Close Redis connection"""
        if self.client:
            await self.client.close()
        if self._sentinel:
            await self._sentinel.close()
        if self._cluster:
            await self._cluster.close()
    
    async def get_connection_info(self) -> Dict[str, Any]:
        """Get current connection information"""
        info = {
            'mode': self.mode,
            'connected': False,
            'details': {}
        }
        
        try:
            if self.client:
                await self.client.ping()
                info['connected'] = True
                
                if self.mode == 'sentinel':
                    # Get sentinel info
                    if self._sentinel:
                        master_info = await self._sentinel.discover_master(
                            settings.REDIS_SENTINEL_MASTER or 'mymaster'
                        )
                        slaves_info = await self._sentinel.discover_slaves(
                            settings.REDIS_SENTINEL_MASTER or 'mymaster'
                        )
                        info['details'] = {
                            'master': master_info,
                            'slaves': slaves_info
                        }
                
                elif self.mode == 'cluster':
                    # Get cluster info
                    if self._cluster:
                        nodes = await self._cluster.cluster_nodes()
                        info['details'] = {
                            'nodes': len(nodes),
                            'slots_coverage': await self._cluster.cluster_slots()
                        }
                
        except Exception as e:
            logger.error(f"Error getting connection info: {e}")
            info['error'] = str(e)
        
        return info


# Global instance
redis_manager = RedisConnectionManager()


# Helper functions for different use cases
async def get_redis_client() -> redis.Redis:
    """Get Redis client for general use"""
    return await redis_manager.get_client()


async def get_redis_pubsub():
    """Get Redis pub/sub client"""
    client = await get_redis_client()
    return client.pubsub()


async def get_redis_lock(name: str, timeout: int = 10):
    """Get distributed lock"""
    client = await get_redis_client()
    return client.lock(name, timeout=timeout)


# WebSocket manager with cluster support
class ClusterAwareWebSocketManager:
    """WebSocket manager that works with Redis Cluster"""
    
    def __init__(self):
        self.channel_prefix = "order_tracking"
        self.node_id = None
    
    async def publish_to_order(self, order_id: int, message: Dict[str, Any]):
        """Publish message to order channel"""
        client = await get_redis_client()
        
        # Use hash tag to ensure all order messages go to same slot in cluster
        channel = f"{self.channel_prefix}:{{order:{order_id}}}"
        
        await client.publish(channel, json.dumps(message))
    
    async def subscribe_to_order(self, order_id: int, callback):
        """Subscribe to order channel"""
        pubsub = await get_redis_pubsub()
        
        # Use hash tag for consistent slot assignment
        channel = f"{self.channel_prefix}:{{order:{order_id}}}"
        
        await pubsub.subscribe(channel)
        
        async for message in pubsub.listen():
            if message['type'] == 'message':
                await callback(json.loads(message['data']))


# Configuration helper
class RedisConfig:
    """Redis configuration based on environment"""
    
    @staticmethod
    def from_env() -> Dict[str, Any]:
        """Create Redis configuration from environment variables"""
        config = {
            'mode': settings.REDIS_MODE or 'single'
        }
        
        if config['mode'] == 'single':
            config['url'] = settings.REDIS_URL
        
        elif config['mode'] == 'sentinel':
            config['sentinel_nodes'] = settings.REDIS_SENTINEL_NODES
            config['master_name'] = settings.REDIS_SENTINEL_MASTER
            config['sentinel_password'] = settings.REDIS_SENTINEL_PASSWORD
        
        elif config['mode'] == 'cluster':
            config['cluster_nodes'] = settings.REDIS_CLUSTER_NODES
            config['cluster_password'] = settings.REDIS_CLUSTER_PASSWORD
        
        return config
    
    @staticmethod
    def get_arq_settings():
        """Get Arq worker settings based on Redis config"""
        from arq.connections import RedisSettings as ArqRedisSettings
        
        mode = settings.REDIS_MODE or 'single'
        
        if mode == 'single':
            return ArqRedisSettings.from_dsn(settings.REDIS_URL)
        
        elif mode == 'sentinel':
            # Arq doesn't support sentinel directly, use discovered master
            # This would need custom implementation
            return ArqRedisSettings(
                host='localhost',  # Would be discovered from sentinel
                port=6379,
                password=settings.REDIS_PASSWORD
            )
        
        elif mode == 'cluster':
            # Arq doesn't support cluster, use single node
            # Would need to pick a specific node
            nodes = settings.REDIS_CLUSTER_NODES.split(',')[0]
            host, port = nodes.split(':')
            return ArqRedisSettings(
                host=host,
                port=int(port),
                password=settings.REDIS_CLUSTER_PASSWORD
            )


# Startup and shutdown functions
async def startup_redis():
    """Initialize Redis connection on startup"""
    await redis_manager.get_client()
    logger.info("Redis connection initialized")


async def shutdown_redis():
    """Close Redis connection on shutdown"""
    await redis_manager.close()
    logger.info("Redis connection closed")


# Example usage in settings
"""
# Single instance (default)
REDIS_MODE=single
REDIS_URL=redis://localhost:6379/0

# Redis Sentinel
REDIS_MODE=sentinel
REDIS_SENTINEL_NODES=localhost:26379,localhost:26380,localhost:26381
REDIS_SENTINEL_MASTER=mymaster
REDIS_SENTINEL_PASSWORD=sentinel_password

# Redis Cluster
REDIS_MODE=cluster
REDIS_CLUSTER_NODES=localhost:7000,localhost:7001,localhost:7002
REDIS_CLUSTER_PASSWORD=cluster_password
"""
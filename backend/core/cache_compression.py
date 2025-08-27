"""
Cache compression utilities for large objects.

Provides transparent compression/decompression for cached data
to reduce memory usage and network transfer.
"""

import zlib
import gzip
import logging
from typing import Any, Union, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class CompressionAlgorithm(Enum):
    """Supported compression algorithms."""
    NONE = "none"
    GZIP = "gzip"
    ZLIB = "zlib"


class CacheCompressor:
    """Handles compression and decompression of cache data."""
    
    # Minimum size in bytes before compression is applied
    MIN_SIZE_FOR_COMPRESSION = 1024  # 1KB
    
    # Compression level (1-9, 9 being highest compression)
    DEFAULT_COMPRESSION_LEVEL = 6
    
    @classmethod
    def should_compress(cls, data: bytes) -> bool:
        """Determine if data should be compressed based on size."""
        return len(data) >= cls.MIN_SIZE_FOR_COMPRESSION
    
    @classmethod
    def compress(
        cls,
        data: bytes,
        algorithm: CompressionAlgorithm = CompressionAlgorithm.GZIP,
        level: int = DEFAULT_COMPRESSION_LEVEL
    ) -> tuple[bytes, str]:
        """
        Compress data using specified algorithm.
        
        Returns:
            Tuple of (compressed_data, algorithm_used)
        """
        if not cls.should_compress(data):
            return data, CompressionAlgorithm.NONE.value
            
        try:
            if algorithm == CompressionAlgorithm.GZIP:
                compressed = gzip.compress(data, compresslevel=level)
            elif algorithm == CompressionAlgorithm.ZLIB:
                compressed = zlib.compress(data, level=level)
            else:
                return data, CompressionAlgorithm.NONE.value
                
            # Only use compressed version if it's actually smaller
            if len(compressed) < len(data):
                compression_ratio = (1 - len(compressed) / len(data)) * 100
                logger.debug(
                    f"Compressed {len(data)} bytes to {len(compressed)} bytes "
                    f"({compression_ratio:.1f}% reduction) using {algorithm.value}"
                )
                return compressed, algorithm.value
            else:
                logger.debug(
                    f"Compression not beneficial for data of size {len(data)}"
                )
                return data, CompressionAlgorithm.NONE.value
                
        except Exception as e:
            logger.error(f"Compression failed: {e}")
            return data, CompressionAlgorithm.NONE.value
    
    @classmethod
    def decompress(
        cls,
        data: bytes,
        algorithm: str
    ) -> bytes:
        """Decompress data using specified algorithm."""
        if algorithm == CompressionAlgorithm.NONE.value:
            return data
            
        try:
            if algorithm == CompressionAlgorithm.GZIP.value:
                return gzip.decompress(data)
            elif algorithm == CompressionAlgorithm.ZLIB.value:
                return zlib.decompress(data)
            else:
                logger.warning(f"Unknown compression algorithm: {algorithm}")
                return data
                
        except Exception as e:
            logger.error(f"Decompression failed for {algorithm}: {e}")
            # Return original data if decompression fails
            return data
    
    @classmethod
    def get_compression_stats(
        cls,
        original_size: int,
        compressed_size: int
    ) -> dict:
        """Calculate compression statistics."""
        if original_size == 0:
            return {
                "original_size": 0,
                "compressed_size": 0,
                "compression_ratio": 0,
                "space_saved": 0,
                "space_saved_percent": 0
            }
            
        compression_ratio = compressed_size / original_size
        space_saved = original_size - compressed_size
        space_saved_percent = (space_saved / original_size) * 100
        
        return {
            "original_size": original_size,
            "compressed_size": compressed_size,
            "compression_ratio": round(compression_ratio, 3),
            "space_saved": space_saved,
            "space_saved_percent": round(space_saved_percent, 1)
        }


class CompressedCacheValue:
    """Wrapper for compressed cache values with metadata."""
    
    def __init__(
        self,
        data: bytes,
        algorithm: str,
        original_size: int,
        compressed_size: int
    ):
        self.data = data
        self.algorithm = algorithm
        self.original_size = original_size
        self.compressed_size = compressed_size
        self.compression_stats = CacheCompressor.get_compression_stats(
            original_size,
            compressed_size
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "_compressed": True,
            "data": self.data.hex(),  # Store as hex string
            "algorithm": self.algorithm,
            "original_size": self.original_size,
            "compressed_size": self.compressed_size,
            "stats": self.compression_stats
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> Optional['CompressedCacheValue']:
        """Create from dictionary."""
        if not data.get("_compressed"):
            return None
            
        try:
            return cls(
                data=bytes.fromhex(data["data"]),
                algorithm=data["algorithm"],
                original_size=data["original_size"],
                compressed_size=data["compressed_size"]
            )
        except Exception as e:
            logger.error(f"Failed to deserialize compressed value: {e}")
            return None
    
    def decompress(self) -> bytes:
        """Decompress the data."""
        return CacheCompressor.decompress(self.data, self.algorithm)


# Export public interface
__all__ = [
    "CacheCompressor",
    "CompressedCacheValue",
    "CompressionAlgorithm"
]
"""
KV Cache management for cross-session persistence
"""

import os
import pickle
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import time

logger = logging.getLogger(__name__)

class KVCacheManager:
    """
    Manages KV cache persistence across sessions
    Uses disk-based storage with LRU eviction
    """
    
    def __init__(self, cache_dir="~/.Tangi/kv_cache", max_size_gb=4):
        self.cache_dir = Path(os.path.expanduser(cache_dir))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_size_bytes = max_size_gb * 1024**3
        self.cache_metadata = self._load_metadata()
        
    def _load_metadata(self) -> Dict:
        """Load cache metadata from disk"""
        meta_file = self.cache_dir / "metadata.pkl"
        if meta_file.exists():
            try:
                with open(meta_file, 'rb') as f:
                    return pickle.load(f)
            except:
                return {}
        return {}
    
    def _save_metadata(self):
        """Save cache metadata to disk"""
        meta_file = self.cache_dir / "metadata.pkl"
        with open(meta_file, 'wb') as f:
            pickle.dump(self.cache_metadata, f)
    
    def _get_cache_key(self, session_id: str, prefix_hash: str) -> str:
        """Generate unique cache key"""
        return f"{session_id}_{prefix_hash}"
    
    def _compute_prefix_hash(self, history: list) -> str:
        """Compute hash of conversation history prefix"""
        history_str = "|".join([str(msg) for msg in history[:10]])  # First 10 messages
        return hashlib.md5(history_str.encode()).hexdigest()[:16]
    
    def _enforce_size_limit(self):
        """LRU eviction when cache exceeds max size"""
        if self._get_total_size() <= self.max_size_bytes:
            return
        
        # Sort by last access time
        sorted_items = sorted(
            self.cache_metadata.items(),
            key=lambda x: x[1].get('last_access', 0)
        )
        
        # Remove oldest until under limit
        for key, _ in sorted_items:
            cache_file = self.cache_dir / f"{key}.pt"
            if cache_file.exists():
                cache_file.unlink()
            del self.cache_metadata[key]
            
            if self._get_total_size() <= self.max_size_bytes:
                break
        
        self._save_metadata()
    
    def _get_total_size(self) -> int:
        """Calculate total cache size"""
        total = 0
        for key in self.cache_metadata:
            cache_file = self.cache_dir / f"{key}.pt"
            if cache_file.exists():
                total += cache_file.stat().st_size
        return total
    
    def save_cache(self, session_id: str, history: list, kv_cache: Any):
        """Save KV cache for a session"""
        prefix_hash = self._compute_prefix_hash(history)
        cache_key = self._get_cache_key(session_id, prefix_hash)
        cache_file = self.cache_dir / f"{cache_key}.pt"
        
        # Save cache to disk
        try:
            # Assuming your LLM library has a save_cache method
            if hasattr(kv_cache, 'save'):
                kv_cache.save(cache_file)
            else:
                # Fallback: pickle the cache
                with open(cache_file, 'wb') as f:
                    pickle.dump(kv_cache, f)
            
            # Update metadata
            self.cache_metadata[cache_key] = {
                'session_id': session_id,
                'prefix_hash': prefix_hash,
                'created': time.time(),
                'last_access': time.time(),
                'size': cache_file.stat().st_size
            }
            
            self._save_metadata()
            self._enforce_size_limit()
            
            logger.info(f"Saved KV cache for session {session_id} ({cache_file.stat().st_size / 1024**2:.1f} MB)")
            
        except Exception as e:
            logger.error(f"Failed to save KV cache: {e}")
    
    def load_cache(self, session_id: str, history: list) -> Optional[Any]:
        """Load KV cache for a session if available"""
        prefix_hash = self._compute_prefix_hash(history)
        cache_key = self._get_cache_key(session_id, prefix_hash)
        cache_file = self.cache_dir / f"{cache_key}.pt"
        
        if not cache_file.exists():
            logger.debug(f"No KV cache found for session {session_id}")
            return None
        
        try:
            # Update last access time
            if cache_key in self.cache_metadata:
                self.cache_metadata[cache_key]['last_access'] = time.time()
                self._save_metadata()
            
            # Load cache
            if hasattr(self, 'llm') and hasattr(self.llm, 'load_cache'):
                return self.llm.load_cache(cache_file)
            else:
                with open(cache_file, 'rb') as f:
                    return pickle.load(f)
                    
        except Exception as e:
            logger.error(f"Failed to load KV cache: {e}")
            return None
    
    def clear_session_cache(self, session_id: str):
        """Clear all cache entries for a specific session"""
        to_delete = []
        for key, meta in self.cache_metadata.items():
            if meta.get('session_id') == session_id:
                to_delete.append(key)
        
        for key in to_delete:
            cache_file = self.cache_dir / f"{key}.pt"
            if cache_file.exists():
                cache_file.unlink()
            del self.cache_metadata[key]
        
        self._save_metadata()
        logger.info(f"Cleared {len(to_delete)} cache entries for session {session_id}")
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        return {
            'total_entries': len(self.cache_metadata),
            'total_size_gb': self._get_total_size() / 1024**3,
            'max_size_gb': self.max_size_bytes / 1024**3,
            'cache_files': list(self.cache_metadata.keys())
        }
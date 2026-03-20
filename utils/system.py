"""
System detection and optimization utilities
"""

import os
import logging
import multiprocessing
import time
import ctypes
import ctypes.util

logger = logging.getLogger(__name__)

# ==================== AUTO THREAD OPTIMIZATION ====================
class ThreadOptimizer:
    """Auto-detect and set optimal thread counts for any system"""
    
    @staticmethod
    def get_optimal_threads():
        """Returns optimal thread count based on system detection"""
        
        # Get logical cores
        logical = multiprocessing.cpu_count()
        
        # Try to detect physical cores
        physical = logical  # Default
        
        # Method 1: /proc/cpuinfo (Linux)
        try:
            if os.path.exists('/proc/cpuinfo'):
                cores = set()
                with open('/proc/cpuinfo', 'r') as f:
                    for line in f:
                        if 'core id' in line:
                            cores.add(line.split(':')[1].strip())
                if cores:
                    physical = len(cores)
                    logger.info(f"Detected {physical} physical cores via /proc/cpuinfo")
                    return physical
        except Exception as e:
            logger.debug(f"Core detection via cpuinfo failed: {e}")
        
        # Method 2: Check if hyperthreading is likely
        if logical > 4 and logical % 2 == 0:
            # Most consumer CPUs have 2 threads per core
            physical = logical // 2
            logger.info(f"Assuming {physical} physical cores (hyperthreading)")
        else:
            physical = logical
            logger.info(f"Using logical cores as physical count ({logical})")
        
        return physical
    
    @staticmethod
    def apply_optimizations():
        """Apply all thread optimizations"""
        threads = ThreadOptimizer.get_optimal_threads()
        
        # Set environment variables FIRST (most important)
        os.environ['OPENBLAS_NUM_THREADS'] = str(threads)
        os.environ['OMP_NUM_THREADS'] = str(threads)
        os.environ['GOTO_NUM_THREADS'] = str(threads)
        os.environ['MKL_NUM_THREADS'] = str(threads)
        os.environ['NUMEXPR_NUM_THREADS'] = str(threads)
        
        # Try multiple methods to force OpenBLAS thread count
        try:
            import ctypes
            import ctypes.util
            openblas_path = ctypes.util.find_library('openblas')
            if openblas_path:
                openblas = ctypes.CDLL(openblas_path)
                
                # Method 1: Set thread count
                if hasattr(openblas, 'openblas_set_num_threads'):
                    openblas.openblas_set_num_threads(threads)
                    logger.info(f"✅ Method 1: Set OpenBLAS threads to {threads}")
                
                # Method 2: Try the older function name
                if hasattr(openblas, 'goto_set_num_threads'):
                    openblas.goto_set_num_threads(threads)
                    logger.info(f"✅ Method 2: Set GOTO threads to {threads}")
                
                # Verify what actually took effect
                actual_threads = None
                if hasattr(openblas, 'openblas_get_num_threads'):
                    openblas.openblas_get_num_threads.restype = ctypes.c_int
                    actual_threads = openblas.openblas_get_num_threads()
                    logger.info(f"✅ OpenBLAS reports using {actual_threads} threads")
                
                # If verification failed or wrong, try one more time
                if actual_threads != threads:
                    # Method 3: Try the environment variable again via C
                    if hasattr(openblas, 'openblas_set_num_threads'):
                        openblas.openblas_set_num_threads(threads)
                        time.sleep(0.1)  # Give it time to apply
                        actual_threads = openblas.openblas_get_num_threads()
                        logger.info(f"✅ Method 3: Re-set threads, now using {actual_threads}")
        except Exception as e:
            logger.debug(f"OpenBLAS programmatic setting failed: {e}")
        
        logger.info(f"✅ Thread optimization complete: target={threads} threads")
        logger.info(f"   OPENBLAS_NUM_THREADS={os.environ.get('OPENBLAS_NUM_THREADS')}")
        logger.info(f"   OMP_NUM_THREADS={os.environ.get('OMP_NUM_THREADS')}")
        return threads


# ==================== OPENBLAS DETECTION MODULE ====================
class OpenBLASDetector:
    """Detect and verify OpenBLAS installation"""
    
    @staticmethod
    def find_openblas():
        """Find OpenBLAS library path"""
        import ctypes.util
        # Try standard library search
        openblas_path = ctypes.util.find_library('openblas')
        if openblas_path:
            return openblas_path
        
        # Common locations on Linux
        common_paths = [
            '/usr/lib64/libopenblas.so',
            '/usr/lib64/libopenblas.so.0',
            '/usr/lib/x86_64-linux-gnu/libopenblas.so',
            '/usr/lib/libopenblas.so',
            '/lib/x86_64-linux-gnu/libopenblas.so',
            '/lib64/libopenblas.so',
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                return path
        
        return None
    
    @staticmethod
    def get_openblas_info():
        """Get detailed OpenBLAS information"""
        info = {
            'present': False,
            'path': None,
            'threads': None,
            'core': None,
            'parallel': None,
        }
        
        path = OpenBLASDetector.find_openblas()
        if not path:
            return info
        
        info['present'] = True
        info['path'] = path
        
        try:
            import ctypes
            openblas = ctypes.CDLL(path)
            
            # Get thread count
            if hasattr(openblas, 'openblas_get_num_threads'):
                openblas.openblas_get_num_threads.restype = ctypes.c_int
                info['threads'] = openblas.openblas_get_num_threads()
            
            # Get core name
            if hasattr(openblas, 'openblas_get_corename'):
                openblas.openblas_get_corename.restype = ctypes.c_char_p
                core_name = openblas.openblas_get_corename()
                if core_name:
                    info['core'] = core_name.decode('utf-8')
            
            # Get parallel mode
            if hasattr(openblas, 'openblas_get_parallel'):
                openblas.openblas_get_parallel.restype = ctypes.c_int
                info['parallel'] = openblas.openblas_get_parallel()
                    
        except Exception as e:
            logger.debug(f"Error reading OpenBLAS info: {e}")
        
        return info
    
    @staticmethod
    def check_environment():
        """Check OpenBLAS-related environment variables"""
        return {
            'OPENBLAS_NUM_THREADS': os.environ.get('OPENBLAS_NUM_THREADS', 'not set'),
            'OMP_NUM_THREADS': os.environ.get('OMP_NUM_THREADS', 'not set'),
        }
    
    @staticmethod
    def verify_in_use():
        """Quick verification that OpenBLAS is likely being used"""
        info = OpenBLASDetector.get_openblas_info()
        env = OpenBLASDetector.check_environment()
        
        if not info['present']:
            return False, "OpenBLAS library not found"
        
        # Check if we have core info (indicates it's loaded)
        if info['core']:
            return True, f"OpenBLAS active ({info['core']})"
        
        return True, "OpenBLAS present"
    
    @staticmethod
    def log_status():
        """Log OpenBLAS status to logger"""
        info = OpenBLASDetector.get_openblas_info()
        env = OpenBLASDetector.check_environment()
        
        if info['present']:
            logger.info(f"✅ OpenBLAS detected at: {info['path']}")
            if info['core']:
                logger.info(f"✅ OpenBLAS core: {info['core']}")
            if info['threads']:
                logger.info(f"✅ OpenBLAS threads: {info['threads']}")
        else:
            logger.warning("❌ OpenBLAS not found - performance may be suboptimal")
            logger.warning("   Install with: sudo emerge -av sci-libs/openblas")
        
        # Log environment variables
        for key, value in env.items():
            logger.info(f"⚙️  {key}: {value}")


# ==================== RAM DETECTION ====================
def detect_system_ram():
    """Detect system RAM with fallback"""
    try:
        import psutil
        mem = psutil.virtual_memory()
        
        total_ram_bytes = mem.total
        available_ram_bytes = mem.available
        total_ram_gb = total_ram_bytes / (1024**3)
        available_ram_gb = available_ram_bytes / (1024**3)
        
        system_ram_mb = int(total_ram_gb * 1024)
        available_ram_mb = int(available_ram_gb * 1024)
        
        logger.info(f"Total RAM: {total_ram_gb:.1f}GB, Available: {available_ram_gb:.1f}GB ({available_ram_gb/total_ram_gb*100:.1f}%)")
        
        return system_ram_mb, available_ram_mb
        
    except ImportError:
        # psutil not installed - use manual setting
        logger.warning("psutil not installed, using default RAM values")
        return 11161, 8000  # Default fallback values


# Run auto-detection on import
optimal_threads = ThreadOptimizer.apply_optimizations()
SYSTEM_RAM_MB, AVAILABLE_RAM_MB = detect_system_ram()

# Export for other modules
__all__ = [
    'ThreadOptimizer',
    'OpenBLASDetector',
    'detect_system_ram',
    'optimal_threads',
    'SYSTEM_RAM_MB',
    'AVAILABLE_RAM_MB'
]
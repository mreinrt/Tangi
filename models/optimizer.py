"""
Model-specific CPU optimization
"""

import os
import logging
import multiprocessing

logger = logging.getLogger(__name__)


class AdaptiveCPUOptimizer:
    """Dynamically optimize CPU usage based on model capabilities - MODEL AGNOSTIC"""
    
    @staticmethod
    def calculate_optimal_resources(model_type, model_size_category, available_cores, context_size=2048):
        """Calculate optimal CPU resources for any model - OPTIMIZED FOR LOW-CORE CPUS with NUMA awareness"""
        total_cores = available_cores
        
        # === ADD NUMA DETECTION ===
        import platform
        import os
        import logging
        logger = logging.getLogger(__name__)
        
        # Detect NUMA nodes (for multi-socket systems)
        numa_nodes = 1
        numa_node_ids = []
        try:
            if os.path.exists('/sys/devices/system/node'):
                # Get list of node directories
                nodes = [d for d in os.listdir('/sys/devices/system/node') if d.startswith('node')]
                node_nums = [int(d.replace('node', '')) for d in nodes if d.replace('node', '').isdigit()]
                if node_nums:
                    numa_nodes = len(node_nums)
                    numa_node_ids = node_nums
                    logger.info(f"NUMA detected: {numa_nodes} nodes: {numa_node_ids}")
        except Exception as e:
            logger.debug(f"NUMA detection skipped: {e}")
            numa_nodes = 1
        
        # UNIVERSAL PHYSICAL CORE DETECTION - Works on any Linux
        physical_cores = total_cores  # Default fallback
        detection_method = "logical_only"
        suggested_threads = total_cores  # Default

        try:
            # Method 1: Parse /proc/cpuinfo (most reliable on Linux)
            if os.path.exists('/proc/cpuinfo'):
                core_ids = set()
                with open('/proc/cpuinfo', 'r') as f:
                    for line in f:
                        if 'core id' in line:
                            core_id = line.split(':')[1].strip()
                            core_ids.add(core_id)
                
                if core_ids:
                    physical_cores = len(core_ids)
                    detection_method = "cpuinfo"
                    logger.info(f"Detected {physical_cores} physical cores via /proc/cpuinfo")
            
            # Method 2: Check sysfs if cpuinfo didn't work
            if detection_method == "logical_only" and os.path.exists('/sys/devices/system/cpu'):
                import glob
                core_ids = set()
                cpu_dirs = glob.glob('/sys/devices/system/cpu/cpu[0-9]*')
                for cpu_dir in cpu_dirs:
                    core_id_path = os.path.join(cpu_dir, 'topology', 'core_id')
                    if os.path.exists(core_id_path):
                        with open(core_id_path, 'r') as f:
                            core_id = f.read().strip()
                            core_ids.add(core_id)
                
                if core_ids:
                    physical_cores = len(core_ids)
                    detection_method = "sysfs"
                    logger.info(f"Detected {physical_cores} physical cores via sysfs")
                    
        except Exception as e:
            logger.debug(f"Physical core detection failed: {e}")

        # If detection failed, use conservative heuristic
        if detection_method == "logical_only":
            # Conservative fallback for hyperthreading
            if total_cores > 4 and total_cores % 2 == 0:
                physical_cores = total_cores // 2
                detection_method = "fallback_halving"
                logger.info(f"Using heuristic: {physical_cores} physical cores (assuming hyperthreading)")
            else:
                physical_cores = max(1, total_cores // 2)
                detection_method = "fallback_conservative"
                logger.info(f"Using conservative fallback: {physical_cores} physical cores")

        # Use physical cores as baseline for threading
        suggested_threads = physical_cores
        is_low_core_cpu = physical_cores <= 4

        logger.info(f"Core detection: {detection_method} - Logical: {total_cores}, Physical: {physical_cores}, Using: {suggested_threads} threads")
        
        # NUMA-AWARE THREAD ADJUSTMENT
        # For multi-NUMA systems, distribute threads across nodes
        if numa_nodes > 1:
            # Calculate threads per node
            threads_per_node = max(1, suggested_threads // numa_nodes)
            # Adjust total threads to be node-aligned
            suggested_threads = threads_per_node * numa_nodes
            logger.info(f"NUMA-aware adjustment: {threads_per_node} threads per node, total {suggested_threads}")
        
        # === BENCHMARK-OPTIMIZED BATCH SIZES ===
        # Based on benchmark results showing 512 was optimal for most systems
        # and batch size 32-64 worked well for low-core systems
        if is_low_core_cpu:
            if physical_cores <= 2:
                # Very low-core systems (like i7-6600U)
                base_batch = 64
            else:
                # Low-core systems (3-4 cores)
                base_batch = 128
        else:
            if context_size <= 4096:
                base_batch = 512
            elif context_size <= 8192:
                base_batch = 384
            elif context_size <= 16384:
                base_batch = 256
            else:
                base_batch = 128
        
        base_config = {
            'n_threads': suggested_threads,
            'n_threads_batch': suggested_threads,
            'n_batch': base_batch,
            'use_mlock': is_low_core_cpu or numa_nodes > 1,  # Enable mlock for NUMA too
            'use_mmap': True,
            'flash_attn': False,
            'rope_freq_base': 10000,
            'rope_freq_scale': 1.0,
            'n_gpu_layers': 0,
            # Add NUMA hint if supported (may help llama.cpp)
            'numa': True if numa_nodes > 1 else False,
        }
        
        # Size-based optimization - REFINED BASED ON BENCHMARK
        if model_size_category == 'tiny':  # < 3B params
            base_config.update({
                'n_threads': suggested_threads,
                'n_threads_batch': suggested_threads,
                'n_batch': min(base_batch, 512),
                'use_mlock': is_low_core_cpu or numa_nodes > 1,
            })
        elif model_size_category == 'small':  # 3B-8B params
            base_config.update({
                'n_threads': suggested_threads,
                'n_threads_batch': suggested_threads,
                'n_batch': min(base_batch, 384),
                'use_mlock': is_low_core_cpu or numa_nodes > 1,
            })
        elif model_size_category == 'medium':  # 8B-20B params
            thread_count = min(suggested_threads, 4) if is_low_core_cpu else max(4, int(total_cores * 0.85))
            base_config.update({
                'n_threads': thread_count,
                'n_threads_batch': thread_count,
                'n_batch': min(base_batch, 256),
                'use_mlock': True,  # Always lock for medium models
            })
        elif model_size_category in ['large', 'huge']:  # 20B+ params
            thread_count = min(suggested_threads, 4) if is_low_core_cpu else total_cores
            base_config.update({
                'n_threads': thread_count,
                'n_threads_batch': thread_count,
                'n_batch': min(base_batch, 128),
                'use_mlock': True,
            })
        
        # Architecture-specific tweaks
        if model_type == 'mpt':
            base_config.update({
                'flash_attn': True,
                'use_mlock': True,
            })
        elif model_type == 'mistral':
            base_config.update({
                'rope_freq_base': 1000000,
                'rope_freq_scale': 1.0,
            })
        elif model_type == 'qwen':
            base_config.update({
                'rope_freq_base': 1000000,
            })
        
        # Safety limits - ENSURING WE NEVER USE MORE THAN PHYSICAL CORES ON LOW-CORE CPUs
        if is_low_core_cpu:
            base_config['n_threads'] = min(base_config['n_threads'], physical_cores)
            base_config['n_threads_batch'] = min(base_config['n_threads_batch'], physical_cores)
        else:
            base_config['n_threads'] = min(base_config['n_threads'], total_cores)
            base_config['n_threads_batch'] = min(base_config['n_threads_batch'], total_cores)
        
        # Ensure batch size doesn't exceed reasonable limits
        base_config['n_batch'] = min(base_config['n_batch'], 2048)
        
        # Special case: many cores
        if total_cores > 16 and not is_low_core_cpu:
            base_config['n_threads'] = max(12, int(total_cores * 0.8))
            base_config['n_threads_batch'] = max(12, int(total_cores * 0.8))
        
        # NUMA-aware final adjustment for multi-node systems
        if numa_nodes > 1 and base_config['n_threads'] > 0:
            # Ensure thread count is divisible by nodes for even distribution
            threads_per_node = base_config['n_threads'] // numa_nodes
            if threads_per_node < 1:
                threads_per_node = 1
            base_config['n_threads'] = threads_per_node * numa_nodes
            base_config['n_threads_batch'] = threads_per_node * numa_nodes
        
        logger.info(f"OPTIMIZED CONFIG: {model_type}/{model_size_category} -> {base_config['n_threads']} threads, batch: {base_config['n_batch']}, mlock: {base_config['use_mlock']}, NUMA: {numa_nodes > 1}")
        
        return base_config
    
    @staticmethod
    def get_generation_optimizations(model_type="", prompt_text="", context_size=2048):
        """Get optimal generation parameters - AGNOSTIC VERSION"""
        optimizations = {
            'temperature': 0.8,           # Increased base temperature
            'top_p': 0.95,                 # Increased - wider token selection
            'repeat_penalty': 1.05,        # Reduced - was too aggressive
            'frequency_penalty': 0.0,      # Removed - causes repetition loops
            'presence_penalty': 0.0,       # Removed - causes repetition loops
            'top_k': 60,                    # Increased - more token candidates
            'mirostat_mode': 0,             # Keep off for now
            'mirostat_tau': 5.0,
            'mirostat_eta': 0.1,
            'tfs_z': 1.0,
        }
        
        # Adjust based on context size - more nuanced adjustments
        if context_size <= 2048:
            optimizations['temperature'] = 0.75    # Slightly lower for small context
            optimizations['repeat_penalty'] = 1.08  # Slightly higher for small context
            optimizations['top_k'] = 50
        elif context_size <= 4096:
            optimizations['temperature'] = 0.8
            optimizations['repeat_penalty'] = 1.05
            optimizations['top_k'] = 60
        elif context_size <= 8192:
            optimizations['temperature'] = 0.85
            optimizations['repeat_penalty'] = 1.02
            optimizations['top_k'] = 70
        else:  # >= 16384
            optimizations['temperature'] = 0.9
            optimizations['repeat_penalty'] = 1.0   # No repetition penalty for huge context
            optimizations['top_k'] = 80
        
        # Model-specific adjustments - refined for better responses
        if model_type == 'codellama':
            optimizations.update({
                'temperature': 0.4,         # Keep lower for code precision
                'repeat_penalty': 1.15,      # Reduced from 1.3
                'top_k': 40,                  # More conservative for code
            })
        elif model_type == 'mpt':
            optimizations.update({
                'temperature': 0.85,
                'repeat_penalty': 1.02,
                'top_k': 70,
            })
        elif model_type == 'phi':
            optimizations.update({
                'temperature': 0.75,
                'repeat_penalty': 1.1,       # Reduced from 1.2
                'top_k': 50,
            })
        elif model_type == 'mistral':
            optimizations.update({
                'temperature': 0.82,
                'repeat_penalty': 1.03,
                'top_k': 65,
            })
        elif model_type == 'llama':
            optimizations.update({
                'temperature': 0.8,
                'repeat_penalty': 1.05,
                'top_k': 60,
            })
        
        # Prompt-based adjustments - more balanced
        if prompt_text:
            prompt_lower = prompt_text.lower()
            
            code_keywords = ['code', 'function', 'def ', 'class ', 'import ', 'algorithm', 'python', 'javascript']
            if any(kw in prompt_lower for kw in code_keywords):
                optimizations['temperature'] = min(optimizations['temperature'], 0.5)
                optimizations['repeat_penalty'] = max(optimizations['repeat_penalty'], 1.1)
                optimizations['top_k'] = min(optimizations.get('top_k', 60), 50)
            
            creative_keywords = ['story', 'creative', 'write a', 'imagine', 'narrative', 'fiction']
            if any(kw in prompt_lower for kw in creative_keywords):
                optimizations['temperature'] = max(optimizations['temperature'], 0.85)
                optimizations['repeat_penalty'] = min(optimizations['repeat_penalty'], 1.02)
                optimizations['top_k'] = max(optimizations.get('top_k', 60), 75)
            
            factual_keywords = ['explain', 'what is', 'how does', 'define', 'fact', 'science']
            if any(kw in prompt_lower for kw in factual_keywords):
                optimizations['temperature'] = min(optimizations['temperature'], 0.7)
                optimizations['repeat_penalty'] = max(optimizations['repeat_penalty'], 1.08)
            
            # Technical/how-to questions need balanced settings
            technical_keywords = ['how to', 'gentoo', 'install', 'configure', 'setup', 'widget', 'btop']
            if any(kw in prompt_lower for kw in technical_keywords):
                optimizations['temperature'] = 0.82  # Sweet spot for technical
                optimizations['repeat_penalty'] = 1.04
                optimizations['top_k'] = 65
        
        # Ensure reasonable bounds - relaxed upper bound on temperature
        optimizations['temperature'] = max(0.2, min(1.2, optimizations['temperature']))
        optimizations['repeat_penalty'] = max(1.0, min(1.5, optimizations['repeat_penalty']))
        
        return optimizations


__all__ = ['AdaptiveCPUOptimizer']
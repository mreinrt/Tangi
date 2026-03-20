"""
Model loading thread with automatic optimization
"""

import os
import time
import logging
from PyQt6.QtCore import QThread, pyqtSignal

from llama_cpp import Llama

from Tangi.models.detector import ModelCapabilityDetector
from Tangi.models.optimizer import AdaptiveCPUOptimizer
from Tangi.utils.constants import DEFAULT_RAM_PERCENTAGE
from Tangi.utils.system import SYSTEM_RAM_MB, AVAILABLE_RAM_MB

logger = logging.getLogger(__name__)


class ModelLoaderThread(QThread):
    """Background thread for loading models with progress reporting"""
    
    model_loaded = pyqtSignal(object)
    load_failed = pyqtSignal(str)
    progress = pyqtSignal(str)
    
    def __init__(self, model_path, ram_percentage=None):
        super().__init__()
        self.model_path = model_path
        self._is_running = True
        self.ram_percentage = ram_percentage or DEFAULT_RAM_PERCENTAGE
        self.model_type = "unknown"
        self.model_size_category = "unknown"
        self.estimated_params = 0
        self.high_swap_pressure = False
        
        # Calculate ACTUAL available RAM for this load
        try:
            import psutil
            mem = psutil.virtual_memory()
            self.available_ram_mb = mem.available / (1024 * 1024)
            self.available_percent = (mem.available / mem.total) * 100
            self.total_ram_mb = mem.total / (1024 * 1024)
            
            # Add swap detection
            swap = psutil.swap_memory()
            self.swap_used_mb = swap.used / (1024 * 1024)
            self.swap_percent = swap.percent
            self.swap_total_mb = swap.total / (1024 * 1024)
            
            # Flag high swap pressure
            if swap.percent > 20:
                self.high_swap_pressure = True
                logger.warning(f"High swap usage detected: {swap.percent:.1f}% ({self.swap_used_mb:.0f}MB / {self.swap_total_mb:.0f}MB)")
            else:
                logger.info(f"Swap usage: {swap.percent:.1f}% ({self.swap_used_mb:.0f}MB / {self.swap_total_mb:.0f}MB)")
            
            logger.info(f"Loader RAM: Available={self.available_ram_mb:.0f}MB ({self.available_percent:.1f}%) of {self.total_ram_mb:.0f}MB total")
            
        except Exception as e:
            # Fallback: use percentage of total
            self.available_ram_mb = (SYSTEM_RAM_MB * self.ram_percentage) / 100
            self.available_percent = self.ram_percentage
            self.total_ram_mb = SYSTEM_RAM_MB
            self.swap_used_mb = 0
            self.swap_percent = 0
            self.swap_total_mb = 0
            logger.warning(f"Could not detect system memory: {e}")
            logger.warning(f"Using fallback values: {self.available_ram_mb:.0f}MB available")
            
    def detect_model_capabilities(self):
        """Detect model type and size for optimization"""
        try:
            self.model_type = ModelCapabilityDetector.detect_model_type(self.model_path)
            self.model_size_category, self.estimated_params = ModelCapabilityDetector.detect_model_size(self.model_path)
            
            logger.info(f"Detected: {self.model_type}, {self.model_size_category}, ~{self.estimated_params}M params")
            return True
        except Exception as e:
            logger.warning(f"Model detection failed: {e}")
            filename = os.path.basename(self.model_path).lower()
            if 'mpt' in filename or 'story' in filename:
                self.model_type = 'mpt'
            elif 'llama' in filename:
                if 'code' in filename:
                    self.model_type = 'codellama'
                else:
                    self.model_type = 'llama'
            elif 'mistral' in filename:
                self.model_type = 'mistral'
            elif 'qwen' in filename:
                self.model_type = 'qwen'
            
            try:
                file_size_mb = os.path.getsize(self.model_path) / (1024 * 1024)
                self.estimated_params = int(file_size_mb / 500)
                if self.estimated_params < 3000:
                    self.model_size_category = 'tiny'
                elif self.estimated_params < 8000:
                    self.model_size_category = 'small'
                elif self.estimated_params < 20000:
                    self.model_size_category = 'medium'
                else:
                    self.model_size_category = 'large'
            except:
                pass
                
            return False
    
    def get_optimal_settings(self, ctx_size):
        """Get optimal settings for this specific model"""
        available_cores = os.cpu_count()
        
        optimal_config = AdaptiveCPUOptimizer.calculate_optimal_resources(
            self.model_type, 
            self.model_size_category, 
            available_cores,
            ctx_size
        )
        
        logger.info(f"Optimal settings: {optimal_config['n_threads']} threads, batch: {optimal_config['n_batch']}")
        return optimal_config
    
    def detect_reasonable_context_sizes(self, model_size_mb):
        """Intelligently guess context sizes based on AVAILABLE RAM"""
        
        import psutil
        
        # Check current swap usage
        swap = psutil.swap_memory()
        swap_used_gb = swap.used / (1024**3)
        swap_total_gb = swap.total / (1024**3)
        
        logger.info(f"Swap usage: {swap_used_gb:.1f}GB / {swap_total_gb:.1f}GB ({swap.percent:.1f}%)")
        
        # If swap is already in use, REDUCE context aggressively
        high_swap_pressure = swap.percent > 20
        
        filename = os.path.basename(self.model_path).lower()
        
        # Quantization multiplier
        if "q4_k_m" in filename or "q4-k-m" in filename:
            model_multiplier = 1.5
        elif "q3" in filename:
            model_multiplier = 1.4
        elif "q5" in filename:
            model_multiplier = 1.6
        else:
            model_multiplier = 1.5
        
        available_ram_mb = (SYSTEM_RAM_MB * self.ram_percentage) / 100
        model_ram_needed = model_size_mb * model_multiplier
        
        # Ensure minimum 1GB for context
        context_ram_available = max(1024, available_ram_mb - model_ram_needed)
        
        if high_swap_pressure:
            context_ram_available = context_ram_available * 0.5
            logger.info(f"High swap detected! Reducing effective context RAM to {context_ram_available:.0f}MB")
        
        logger.info(f"Available RAM: {available_ram_mb:.0f}MB")
        logger.info(f"Model needs (x{model_multiplier}): {model_ram_needed:.0f}MB")
        logger.info(f"Context RAM: {context_ram_available:.0f}MB")
        
        # Context calculation - BENCHMARK SHOWS CONTEXT DOESN'T AFFECT SPEED
        # So we can be aggressive with context sizing
        max_context_by_ram = int((context_ram_available / 0.8) * 1024)  # Less conservative
        
        # Apply model limits
        if "codellama" in filename:
            model_max_context = 16384
        elif "llama-3" in filename or "llama3" in filename:
            model_max_context = 8192
        else:
            model_max_context = 32768
        
        absolute_max_context = min(model_max_context, max_context_by_ram)
        absolute_max_context = max(2048, absolute_max_context)
        
        if high_swap_pressure:
            absolute_max_context = min(absolute_max_context, 8192)
            logger.info(f"Swap pressure detected: Capping context to {absolute_max_context}")
        
        logger.info(f"Final max context: {absolute_max_context} tokens")
        
        # Generate options - try larger contexts first since speed is constant
        if absolute_max_context >= 16384:
            options = [16384, 8192, 4096, 2048]
        elif absolute_max_context >= 8192:
            options = [8192, 4096, 2048, 1024]
        elif absolute_max_context >= 4096:
            options = [4096, 2048, 1024, 512]
        else:
            options = [2048, 1024, 512, 256]
        
        options = [opt for opt in options if opt <= absolute_max_context]
        return options
        
    def run(self):
        try:
            if not self._is_running:
                return
                
            self.progress.emit("Checking file...")
            
            # Verify file exists and get file size
            if not os.path.exists(self.model_path):
                self.load_failed.emit(f"File does not exist: {self.model_path}")
                return
                
            if not os.access(self.model_path, os.R_OK):
                self.load_failed.emit(f"Cannot read file (permission denied): {self.model_path}")
                return
            
            # Get model file size
            model_size_bytes = os.path.getsize(self.model_path)
            model_size_mb = model_size_bytes / (1024 * 1024)
            
            # Calculate ACTUAL available RAM - use the MINIMUM of:
            # 1. What's actually available right now
            # 2. What the user requested as percentage of total
            user_requested_mb = (SYSTEM_RAM_MB * self.ram_percentage) / 100
            actual_available_mb = min(self.available_ram_mb, user_requested_mb)
            
            # Warn if RAM is limited
            if self.available_percent < 30:
                self.progress.emit(f"⚠️ Low available RAM: {self.available_percent:.0f}% ({self.available_ram_mb/1024:.1f}GB)")
            
            self.progress.emit(
                f"Model: {model_size_mb:.1f}MB | "
                f"Available RAM: {self.available_ram_mb:.0f}MB ({self.available_percent:.0f}%) | "
                f"Using: {actual_available_mb:.0f}MB of requested {user_requested_mb:.0f}MB"
            )
            
            # DETECT MODEL CAPABILITIES
            self.progress.emit("Analyzing model architecture...")
            self.detect_model_capabilities()
            self.progress.emit(f"Detected: {self.model_type} ({self.model_size_category}, ~{self.estimated_params}M params)")
            
            # UNIVERSAL context size detection
            target_context_sizes = self.detect_reasonable_context_sizes(model_size_mb)
            
            # Format context sizes for display
            context_display = []
            for c in target_context_sizes:
                if c >= 1000:
                    context_display.append(f"{c//1000}K")
                else:
                    context_display.append(str(c))
            self.progress.emit(f"Trying contexts: {context_display}")
            
            last_error = None
            for ctx_size in target_context_sizes:
                if not self._is_running:
                    return
                    
                try:
                    # Format context display for message
                    if ctx_size >= 1000:
                        ctx_display = f"{ctx_size//1000}K"
                    else:
                        ctx_display = str(ctx_size)
                    self.progress.emit(f"Trying {ctx_display} context...")
                    
                    # GET MODEL-SPECIFIC OPTIMAL SETTINGS
                    optimal_settings = self.get_optimal_settings(ctx_size)
                    
                    self.progress.emit(f"Using {optimal_settings['n_threads']} threads, batch: {optimal_settings['n_batch']}")
                    
                    # Adjust settings based on AVAILABLE RAM
                    if actual_available_mb < self.total_ram_mb * 0.5:  # Less than 50% available
                        # Reduce batch size to save RAM
                        optimal_settings['n_batch'] = max(256, optimal_settings['n_batch'] // 2)
                        optimal_settings['use_mlock'] = False  # Don't lock memory
                        self.progress.emit(f"Reduced batch to {optimal_settings['n_batch']} due to low RAM")
                    
                    # Try loading with optimized settings
                    llm = Llama(
                        model_path=self.model_path, 
                        n_ctx=ctx_size,
                        n_threads=optimal_settings['n_threads'],
                        n_threads_batch=optimal_settings['n_threads_batch'],
                        verbose=False,
                        n_batch=optimal_settings['n_batch'],
                        n_gpu_layers=optimal_settings.get('n_gpu_layers', 0),
                        seed=-1,
                        use_mlock=optimal_settings['use_mlock'],
                        use_mmap=optimal_settings['use_mmap'],
                        vocab_only=False,
                        rope_freq_base=optimal_settings['rope_freq_base'],
                        rope_freq_scale=optimal_settings['rope_freq_scale'],
                        flash_attn=optimal_settings['flash_attn'],
                        logits_all=False,
                        embedding=False,
                        low_vram=False,
                        tensor_split=None,
                        last_n_tokens_size=64,
                        f16_kv=True
                    )
                    
                    if self._is_running:
                        # Store the actual context size
                        llm.actual_ctx = ctx_size
                        llm.model_path = self.model_path
                        llm.model_type = self.model_type
                        llm.model_size_category = self.model_size_category
                        llm.estimated_params = self.estimated_params
                        
                        max_ctx_display = f"{ctx_size//1000}K" if ctx_size >= 1000 else str(ctx_size)
                        
                        try:
                            if hasattr(llm, 'metadata'):
                                metadata = llm.metadata()
                                if 'general.architecture' in metadata:
                                    arch = metadata['general.architecture']
                                    self.progress.emit(f"Architecture: {arch}")
                        except:
                            pass
                        
                        success_msg = f"Success! Context: {max_ctx_display} tokens"
                        self.progress.emit(success_msg)
                        self.model_loaded.emit(llm)
                    return
                    
                except Exception as e:
                    error_msg = str(e)
                    last_error = error_msg
                    short_msg = error_msg[:80] + "..." if len(error_msg) > 80 else error_msg
                    
                    if ctx_size >= 1000:
                        ctx_display_err = f"{ctx_size//1000}K"
                    else:
                        ctx_display_err = str(ctx_size)
                    self.progress.emit(f"Failed with {ctx_display_err}: {short_msg}")
                    
                    if "memory" in error_msg.lower() or "ram" in error_msg.lower() or "oom" in error_msg.lower():
                        # Try even more aggressive RAM reduction
                        self.progress.emit("Memory error - trying smaller context with RAM optimization...")
                        continue
                    elif "cuda" in error_msg.lower() or "gpu" in error_msg.lower():
                        self.progress.emit("GPU error - trying CPU-only...")
                        continue
                    elif "file" in error_msg.lower() or "load" in error_msg.lower():
                        self.progress.emit("File format issue...")
                        continue
                    
                    time.sleep(0.1)
            
            # If all attempts failed, try ultra-minimal settings with RAM optimization
            if self._is_running:
                self.progress.emit("All attempts failed, trying minimal settings with RAM optimization...")
                try:
                    # Ultra-conservative settings for low RAM
                    llm = Llama(
                        model_path=self.model_path,
                        n_ctx=512,
                        n_threads=1,  # Single thread to save RAM
                        n_gpu_layers=0,
                        verbose=False,
                        seed=-1,
                        use_mlock=False,  # Don't lock memory
                        use_mmap=True,
                        n_batch=128,  # Very small batch
                        low_vram=True  # Enable low VRAM mode if available
                    )
                    
                    if self._is_running:
                        llm.actual_ctx = 512
                        llm.model_path = self.model_path
                        llm.model_type = self.model_type
                        self.progress.emit("Success with minimal RAM settings (512 context, 1 thread)")
                        self.model_loaded.emit(llm)
                    return
                    
                except Exception as e:
                    if self._is_running:
                        error_detail = str(e)
                        if "invalid file" in error_detail.lower():
                            self.load_failed.emit("Invalid or corrupted GGUF file")
                        elif "version" in error_detail.lower():
                            self.load_failed.emit("GGUF version mismatch")
                        elif "memory" in error_detail.lower():
                            # Give specific RAM advice
                            ram_advice = f"Insufficient RAM. Available: {self.available_ram_mb/1024:.1f}GB, Model needs more."
                            ram_advice += f"\nTry: 1. Close other applications"
                            ram_advice += f"\n2. Reduce RAM allocation in Preferences"
                            ram_advice += f"\n3. Try a smaller model"
                            self.load_failed.emit(ram_advice)
                        else:
                            self.load_failed.emit(f"Failed: {error_detail[:120]}")
            
        except Exception as e:
            if self._is_running:
                self.load_failed.emit(f"Unexpected error: {str(e)[:150]}")
                logger.error(f"Model loader error: {e}")
    
    def stop(self):
        """Safely stop the thread"""
        self._is_running = False
        self.quit()
        self.wait(1000)


__all__ = ['ModelLoaderThread']
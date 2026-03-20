"""
Background worker for LLM inference
"""

import time
import sys
import logging
from PyQt6.QtCore import QThread, pyqtSignal

from Tangi.models.detector import ModelCapabilityDetector
from Tangi.models.optimizer import AdaptiveCPUOptimizer
from Tangi.utils.helpers import is_code_request, estimate_token_count

logger = logging.getLogger(__name__)


class LLMWorker(QThread):
    """Background thread for generating LLM responses"""
    
    response_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, llm, context, model_path=None, prompt=None, max_tokens_setting=512, code_context=None):
        super().__init__()
        self.llm = llm
        self.context = context
        self.model_path = model_path
        self.prompt = prompt
        self._is_running = True
        self.max_tokens_setting = max_tokens_setting
        self.code_context = code_context  # Store code context for RAG
    
    def get_generation_params(self):
        """Get generation parameters combining aggressive settings with model optimizations"""
        
        # Start with our aggressive base settings
        params = {
            'temperature': 0.1,           # Near-deterministic
            'top_p': 0.7,                  # Tight sampling
            'repeat_penalty': 1.3,         # Prevent loops
            'top_k': 20,                    # Very focused
            'mirostat_mode': 2,
            'mirostat_tau': 1.5,
            'mirostat_eta': 0.1,
            'frequency_penalty': 0.3,
            'presence_penalty': 0.2,
            'tfs_z': 0.9,
        }
        
        # For code requests - even more aggressive
        if self.prompt and is_code_request(self.prompt):
            params.update({
                'temperature': 0.05,        # Almost greedy
                'repeat_penalty': 1.5,
                'top_k': 10,
                'mirostat_tau': 1.0,
            })
            logger.info("Using aggressive code-optimized generation parameters")
        
        # Get model-specific optimizations if available
        if self.model_path:
            try:
                model_type = ModelCapabilityDetector.detect_model_type(self.model_path)
                model_ctx = getattr(self.llm, 'actual_ctx', 2048)
                
                # Get the base optimizations
                base_optimizations = AdaptiveCPUOptimizer.get_generation_optimizations(
                    model_type, self.prompt, model_ctx
                )
                
                # Only use non-critical params from base_optimizations
                # Keep our aggressive settings for critical params
                for k, v in base_optimizations.items():
                    if k not in ['temperature', 'repeat_penalty', 'top_k', 'mirostat_mode', 'mirostat_tau']:
                        params[k] = v
                        
            except Exception as e:
                logger.warning(f"Could not apply model-specific optimizations: {e}")
        
        return params
    
    def run(self):
        try:
            if not self._is_running:
                return
            
            start_time = time.time()
            
            # Get the actual context size from the model
            model_ctx = 2048
            if hasattr(self.llm, 'actual_ctx'):
                model_ctx = self.llm.actual_ctx
            elif hasattr(self.llm, 'n_ctx'):
                model_ctx = self.llm.n_ctx
            
            # === KV CACHE LOADING ===
            kv_cache = None
            if hasattr(self, 'kv_cache_manager') and self.kv_cache_manager:
                kv_cache = self.kv_cache_manager.load_cache(
                    self.session_id, 
                    self.history
                )
            
            # === INJECT CODE CONTEXT IF AVAILABLE ===
            if self.code_context:
                # Build code context string
                context_str = "\n\n=== RELEVANT CODE FROM YOUR PROJECT ===\n"
                
                for i, chunk in enumerate(self.code_context):
                    # Handle if chunk is a string instead of dict
                    if isinstance(chunk, str):
                        context_str += f"\n--- Chunk {i+1} ---\n"
                        context_str += f"{chunk}\n"
                    else:
                        # Handle as dictionary
                        try:
                            file_name = chunk.get('file', 'Unknown file')
                            start_line = chunk.get('start_line', '?')
                            end_line = chunk.get('end_line', '?')
                            text = chunk.get('text', '')
                            
                            context_str += f"\n--- {file_name} (lines {start_line}-{end_line}) ---\n"
                            context_str += f"{text}\n"
                        except Exception as e:
                            context_str += f"\n--- Chunk {i+1} (error parsing) ---\n"
                            context_str += f"{str(chunk)[:500]}\n"
                
                # Insert before the user's question
                user_marker = f"User: {self.prompt}"
                if user_marker in self.context:
                    self.context = self.context.replace(
                        user_marker,
                        f"{context_str}\n\n{user_marker}"
                    )
            
            # === SMART MAX TOKENS CALCULATION ===
            # Estimate prompt tokens (rough approximation)
            estimated_prompt_tokens = estimate_token_count(self.context)
            
            # Get user's token setting
            user_max_tokens = self.max_tokens_setting

            # Check if this is a code request
            code_request = False
            if self.prompt and is_code_request(self.prompt):
                code_request = True
                # For code, use user setting with reasonable caps based on complexity
                if estimated_prompt_tokens < 50:
                    max_tokens = min(1024, user_max_tokens)  # Simple code request
                elif estimated_prompt_tokens < 150:
                    max_tokens = min(2048, user_max_tokens)  # Medium code request
                else:
                    max_tokens = min(4096, user_max_tokens)  # Complex code request
                logger.info(f"Code request detected, max_tokens={max_tokens}")
            else:
                # For conversation, use the user's setting directly
                max_tokens = min(user_max_tokens, 4096)  # Cap at model's max context
                logger.info(f"Conversation prompt: ~{estimated_prompt_tokens} tokens, max_tokens={max_tokens}")
            
            # === GENERATION PARAMETERS ===
            params = self.get_generation_params()
            inference_params = {k: v for k, v in params.items() if k != 'n_batch'}
            
            # Add cache to inference params if available
            if kv_cache:
                inference_params['cache'] = kv_cache
            
            # === IMPROVED STOP SEQUENCES ===
            if code_request:
                stop_sequences = None  # No stops for code
                logger.info("Using NO stop sequences for code generation")
            else:
                stop_sequences = [
                    "\nUser:", "\nuser:", "\nHuman:", "\nhuman:",
                    "<|end|>", "<|endoftext|>", "<|im_end|>",
                    "\n\n\n",
                ]
                logger.info("Using minimal stop sequences for general questions")
            
            # Run the LLM inference with cache
            out = self.llm(
                self.context, 
                max_tokens=max_tokens,
                stop=stop_sequences,
                echo=False,
                **inference_params
            )
            
            elapsed = time.time() - start_time
            
            # === SAVE UPDATED KV CACHE ===
            if hasattr(self, 'kv_cache_manager') and hasattr(out, 'cache'):
                self.kv_cache_manager.save_cache(
                    self.session_id,
                    self.history,
                    out.cache
                )
            
            # Get the actual response
            reply = out["choices"][0]["text"].strip()
            actual_tokens = len(reply.split())
            
            # Log completion
            logger.info(f"Generation completed in {elapsed:.2f} seconds, {actual_tokens} tokens, {actual_tokens/elapsed:.2f} tokens/sec")
            
            # Clean up prefixes
            import re
            cleaned_reply = re.sub(r'^(Assistant:|assistant:|AI:|ai:)\s*', '', reply)
            
            # === WARNINGS (logged, not printed) ===
            if elapsed > 30:
                logger.warning(f"Generation took over 30 seconds ({elapsed:.2f}s)")
            if not reply:
                logger.warning("Empty response received")
            elif code_request and '```' not in reply and len(reply) < 200:
                logger.warning("Code request but no code blocks found")
            if actual_tokens < 10 and estimated_prompt_tokens > 20:
                logger.warning("Very short response for prompt length")
            
            if self._is_running:
                self.response_ready.emit(cleaned_reply)
                
        except Exception as e:
            logger.error(f"LLM worker error: {e}")
            if self._is_running:
                self.error_occurred.emit(str(e))
        
    def stop(self):
        """Safely stop the thread"""
        self._is_running = False
        self.quit()
        self.wait(1000)


__all__ = ['LLMWorker']
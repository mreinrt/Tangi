"""
Model capability detection from GGUF files
"""

import os
import struct
import logging

logger = logging.getLogger(__name__)


class ModelCapabilityDetector:
    """Auto-detect model capabilities for optimal CPU/GPU usage"""
    
    @staticmethod
    def detect_model_type(model_path):
        """Detect model architecture from GGUF file metadata"""
        try:
            with open(model_path, 'rb') as f:
                # Read GGUF header
                magic = f.read(4)
                if magic != b'GGUF':
                    logger.warning(f"Not a valid GGUF file: {model_path}")
                    return 'unknown'
                
                # Read version (skip for now)
                version = struct.unpack('<I', f.read(4))[0]
                
                # Read tensor count (skip for now)  
                tensor_count = struct.unpack('<Q', f.read(8))[0]
                
                # Read metadata key-value count
                metadata_kv_count = struct.unpack('<Q', f.read(8))[0]
                
                metadata = {}
                
                # Read all metadata key-value pairs
                for _ in range(metadata_kv_count):
                    try:
                        # Read key
                        key_len = struct.unpack('<Q', f.read(8))[0]
                        key = f.read(key_len).decode('utf-8', errors='ignore')
                        
                        # Read value type
                        value_type = struct.unpack('<I', f.read(4))[0]
                        
                        # Read value based on type
                        if value_type == 0:  # UINT8
                            value = struct.unpack('<B', f.read(1))[0]
                        elif value_type == 1:  # INT8
                            value = struct.unpack('<b', f.read(1))[0]
                        elif value_type == 2:  # UINT16
                            value = struct.unpack('<H', f.read(2))[0]
                        elif value_type == 3:  # INT16
                            value = struct.unpack('<h', f.read(2))[0]
                        elif value_type == 4:  # UINT32
                            value = struct.unpack('<I', f.read(4))[0]
                        elif value_type == 5:  # INT32
                            value = struct.unpack('<i', f.read(4))[0]
                        elif value_type == 6:  # FLOAT32
                            value = struct.unpack('<f', f.read(4))[0]
                        elif value_type == 7:  # BOOL
                            value = bool(struct.unpack('<B', f.read(1))[0])
                        elif value_type == 8:  # STRING
                            str_len = struct.unpack('<Q', f.read(8))[0]
                            value = f.read(str_len).decode('utf-8', errors='ignore')
                        elif value_type == 9:  # ARRAY
                            # Skip array data for now
                            array_type = struct.unpack('<I', f.read(4))[0]
                            array_len = struct.unpack('<Q', f.read(8))[0]
                            # Skip array elements
                            for _ in range(array_len):
                                if array_type == 8:  # String array
                                    elem_len = struct.unpack('<Q', f.read(8))[0]
                                    f.read(elem_len)
                                else:
                                    # Skip based on type (simplified)
                                    f.read(4)
                            continue
                        else:
                            # Unknown type, skip
                            continue
                        
                        metadata[key] = value
                        
                    except Exception as e:
                        logger.debug(f"Error reading metadata key: {e}")
                        continue
                
                # Log all metadata for debugging
                logger.info(f"GGUF metadata keys: {list(metadata.keys())[:10]}...")  # First 10 only
                
                # Try different metadata fields that might contain architecture info
                arch = None
                for key in ['general.architecture', 'general.name', 'tokenizer.ggml.model']:
                    if key in metadata:
                        arch = metadata[key].lower() if isinstance(metadata[key], str) else str(metadata[key]).lower()
                        logger.info(f"Found architecture from {key}: {arch}")
                        break
                
                if not arch:
                    # Try to infer from filename as fallback
                    filename = os.path.basename(model_path).lower()
                    if 'llama' in filename:
                        arch = 'llama'
                    elif 'mistral' in filename:
                        arch = 'mistral'
                    elif 'qwen' in filename:
                        arch = 'qwen'
                    elif 'phi' in filename:
                        arch = 'phi'
                
                # Determine model type from architecture
                if arch:
                    if 'llama' in arch:
                        if 'code' in arch or 'coder' in arch:
                            return 'codellama'
                        return 'llama'
                    elif 'mpt' in arch:
                        return 'mpt'
                    elif 'mistral' in arch:
                        return 'mistral'
                    elif 'qwen' in arch:
                        return 'qwen'
                    elif 'yi' in arch:
                        return 'yi'
                    elif 'phi' in arch:
                        return 'phi'
                    elif 'gemma' in arch:
                        return 'gemma'
                    elif 'falcon' in arch:
                        return 'falcon'
                    elif 'starcoder' in arch or 'starchat' in arch:
                        return 'codellama'  # Treat as code model
                
                return 'unknown'
                        
        except Exception as e:
            logger.warning(f"Could not read model metadata: {e}")
        
        # Ultimate fallback: detect from filename
        filename = os.path.basename(model_path).lower()
        if any(x in filename for x in ['llama', 'llama-2', 'llama2']):
            if 'code' in filename or 'coder' in filename:
                return 'codellama'
            return 'llama'
        elif any(x in filename for x in ['mpt', 'story']):
            return 'mpt'
        elif any(x in filename for x in ['mistral', 'mixtral']):
            return 'mistral'
        elif any(x in filename for x in ['qwen']):
            return 'qwen'
        elif any(x in filename for x in ['phi']):
            return 'phi'
        elif any(x in filename for x in ['gemma']):
            return 'gemma'
        elif any(x in filename for x in ['falcon']):
            return 'falcon'
        elif any(x in filename for x in ['starcoder', 'starchat']):
            return 'codellama'
        else:
            return 'unknown'
    
    @staticmethod
    def detect_model_size(model_path):
        """Estimate model size in parameters from file size"""
        try:
            file_size_gb = os.path.getsize(model_path) / (1024 ** 3)
            filename = os.path.basename(model_path).lower()
            
            # Better estimation based on quantization
            if 'q2' in filename:
                params_per_gb = 1.8  # Q2: ~1.8B per GB
            elif 'q3' in filename:
                params_per_gb = 1.5  # Q3: ~1.5B per GB
            elif 'q4' in filename:
                params_per_gb = 1.2  # Q4: ~1.2B per GB
            elif 'q5' in filename:
                params_per_gb = 1.0  # Q5: ~1.0B per GB
            elif 'q6' in filename:
                params_per_gb = 0.9  # Q6: ~0.9B per GB
            elif 'q8' in filename:
                params_per_gb = 0.7  # Q8: ~0.7B per GB
            else:
                params_per_gb = 1.0  # Default
            
            params_billions = file_size_gb * params_per_gb
            params_millions = int(params_billions * 1000)
            
            logger.info(f"Model size: {file_size_gb:.2f}GB, estimated {params_billions:.1f}B params")
            
            if params_billions < 3:
                return 'tiny', params_millions
            elif params_billions < 8:
                return 'small', params_millions
            elif params_billions < 20:
                return 'medium', params_millions
            elif params_billions < 50:
                return 'large', params_millions
            else:
                return 'huge', params_millions
                
        except Exception as e:
            logger.error(f"Model size detection failed: {e}")
            return 'unknown', 0


__all__ = ['ModelCapabilityDetector']
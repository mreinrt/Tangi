"""
Helper functions for response cleaning, validation, and formatting
"""

import re
import html
import logging
from datetime import datetime
import zoneinfo
from collections import Counter

logger = logging.getLogger(__name__)


def clean_response(text):
    """Universal response cleaner for ANY model - prevents repetition loops"""
    if not text:
        return text
    
    original_text = text
    
    # Remove common prefixes
    prefixes_to_remove = [
        r'^assistant[:\s]*', r'^Assistant[:\s]*', r'^ASSISTANT[:\s]*',
        r'^AI[:\s]*', r'^ai[:\s]*',
        r'^model[:\s]*', r'^Model[:\s]*',
        r'^bot[:\s]*', r'^Bot[:\s]*',
    ]
    
    for pattern in prefixes_to_remove:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    text = text.strip()
    
    # Length truncation if too long
    if len(text) > 8000:
        text = text[:8000] + "\n\n[Response truncated due to length]"
    
    # Check for paragraph-level repetition
    if len(text) > 300:
        paragraphs = re.split(r'\n\s*\n', text)
        if len(paragraphs) > 4:
            seen_paragraphs = {}
            clean_paragraphs = []
            
            for i, para in enumerate(paragraphs):
                if len(para.strip()) > 40:
                    sig = para[:60].strip().lower()
                    
                    if sig in seen_paragraphs:
                        last_pos = seen_paragraphs[sig]
                        if i - last_pos < 3:
                            continue
                    
                    seen_paragraphs[sig] = i
                    clean_paragraphs.append(para)
                else:
                    clean_paragraphs.append(para)
            
            if len(clean_paragraphs) < len(paragraphs):
                text = '\n\n'.join(clean_paragraphs)
    
    # Check for sentence/trigram repetition
    words = text.split()
    if len(words) > 100:
        trigrams = [' '.join(words[i:i+3]) for i in range(len(words)-2)]
        trigram_counts = Counter(trigrams)
        
        repeated_sequences = [seq for seq, count in trigram_counts.items() 
                            if count >= 4 and len(seq.split()) == 3]
        
        if repeated_sequences:
            for seq in repeated_sequences:
                first_idx = text.find(seq)
                second_idx = text.find(seq, first_idx + len(seq))
                if second_idx != -1:
                    text = text[:second_idx].strip()
                    text += "\n\n[Response truncated - repetition detected]"
                    break
    
    # If cleaning removed too much, return original
    if len(text) < len(original_text) * 0.3 and len(original_text) > 100:
        return original_text.strip()
    
    return text


def validate_response(response, prompt):
    """Universal response validation for ANY model"""
    if not response or len(response.strip()) < 2:
        return False, "Response too short"
    
    # Increased limit for code responses
    if len(response) > 50000:
        return False, "Response too long"
    
    # Log assistant prefixes but don't reject
    if response.count("Assistant:") > 5 or response.count("assistant:") > 5:
        logger.warning(f"Response contains multiple assistant prefixes ({response.count('Assistant:')})")
    
    # Check for extreme repetition
    sentences = re.split(r'[.!?]+', response)
    if len(sentences) > 8:
        clean_sentences = [s.strip().lower() for s in sentences if len(s.strip()) > 15]
        if clean_sentences:
            sentence_counts = Counter(clean_sentences)
            most_common = sentence_counts.most_common(1)
            if most_common and most_common[0][1] > 3:
                logger.warning(f"Excessive repetition detected")
                return False, "Excessive repetition detected"
    
    # Check for truncated code blocks (warning only)
    if '```' in response and response.count('```') % 2 != 0:
        logger.warning("Response has unclosed code block - may be truncated")
    
    # For short responses, check if they're meaningful
    if len(response) < 500 and len(prompt) > 20:
        prompt_words = set(prompt.lower().split()[:15])
        response_words = set(response.lower().split()[:20])
        
        if len(prompt_words) > 5 and len(response_words) > 3:
            overlap = prompt_words.intersection(response_words)
            overlap_ratio = len(overlap) / len(prompt_words) if prompt_words else 0
            
            if overlap_ratio > 0.8 and len(response) < 100:
                return False, "Response too similar to prompt"
    
    return True, "Valid"


def get_appropriate_system_prompt(model_path=None):
    """Get appropriate system prompt based on model type"""
    base_prompt = "You are an expert programming assistant skilled in multiple languages and development practices."
    
    if not model_path:
        return base_prompt
    
    model_lower = str(model_path).lower()
    
    if any(x in model_lower for x in ['code', 'coder', 'python', 'program']):
        return base_prompt
    
    return base_prompt


def format_timestamp(timestamp_str):
    """Convert UTC timestamp to local time string"""
    try:
        # Parse the UTC timestamp
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        
        # Assume it's UTC and convert to local system time
        dt_utc = dt.replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
        local_dt = dt_utc.astimezone()
        
        return local_dt.strftime("%Y-%m-%d %H:%M:%S")
        
    except Exception as e:
        logger.error(f"Error formatting timestamp: {e}")
        return str(timestamp_str)


def is_code_request(prompt):
    """Detect if a prompt is requesting code"""
    code_keywords = [
        'code', 'program', 'function', 'calculator', 'python', 'javascript',
        'script', 'write', 'create', 'make', 'build', 'class', 'def',
        'algorithm', 'implementation', 'c++', 'java', 'rust', 'go', 'html',
        'css', 'api', 'endpoint', 'route', 'database', 'sql', 'query'
    ]
    return any(word in prompt.lower() for word in code_keywords)


def estimate_token_count(text):
    """Rough estimation of token count"""
    if not text:
        return 0
    words = len(text.split())
    # Rough approximation: 1 token ≈ 1.3 words for English
    return int(words * 1.3)


def truncate_text(text, max_length, suffix="..."):
    """Safely truncate text at word boundary"""
    if len(text) <= max_length:
        return text
    
    truncated = text[:max_length]
    # Cut at last space
    last_space = truncated.rfind(' ')
    if last_space > 0:
        truncated = truncated[:last_space]
    
    return truncated + suffix


__all__ = [
    'clean_response',
    'validate_response',
    'get_appropriate_system_prompt',
    'format_timestamp',
    'is_code_request',
    'estimate_token_count',
    'truncate_text'
]
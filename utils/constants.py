"""
Universal constants for Tangi
"""

# Universal stop sequences for ALL models
UNIVERSAL_STOP_SEQUENCES = [
    "\nUser:", "\nuser:", "\nHuman:", "\nhuman:",
    "\n\nUser:", "\n\nuser:", "\n\nHuman:", "\n\nhuman:",
    "\nUser ", "\nuser ", "\nHuman ", "\nhuman ",
    "<|end|>", "<|endoftext|>", "<|im_end|>", "<|endofmessage|>",
    "</s>", "<EOS>", "<eos>", "[END]", "[end]",
    "###", "\n###", "\n\n###", "---", "\n---", "\n\n---",
    "\n```", "\n\n```",
    "\n\n\n", "\n\nAssistant:", "\n\nASSISTANT:",
    "\nThank you.", "\nThanks.", "\nHope that helps.",
]

# Conversation limits
MAX_TURNS = 6
MAX_QUEUE_SIZE = 10

# RAM defaults
DEFAULT_RAM_PERCENTAGE = 85

# Export for other modules
__all__ = [
    'UNIVERSAL_STOP_SEQUENCES',
    'MAX_TURNS',
    'MAX_QUEUE_SIZE',
    'DEFAULT_RAM_PERCENTAGE'
]
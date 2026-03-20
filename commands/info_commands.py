"""
Information commands for developer, about, hardware, etc.
"""

import os
import logging
from Tangi.commands.base import Command

logger = logging.getLogger(__name__)

class AboutCommand(Command):
    """/about - Show complete application information"""
    
    def __init__(self, parent):
        super().__init__("about", "Complete application information", parent)
    
    def execute(self, args):
        self.parent.append_message("assistant",
            "**Tangi Information:**\n\n"
            "• **Developer:** Michael Reinert\n"
            "• **Development OS:** Gentoo Linux\n"
            "• **Version:** Universal Model Interface\n"
            "• **Purpose:** Local AI inference on consumer hardware\n"
            "• **Compatibility:** Supports most GGUF format models\n"
            "• **Optimization:** Adaptive CPU/GPU usage based on model type\n\n"
            
            "**Technical Features:**\n\n"
            "• Multi-model agnostic architecture\n"
            "• Automatic RAM optimization\n"
            "• Context size auto-detection\n"
            "• Markdown and conversation response formats\n"
            "• SQLite chat history storage\n"
            "• Gentoo-optimized binaries\n\n"
            
            "**Development Hardware:**\n\n"
            "• **Laptop:** HP with i7-6600U processor\n"
            "• **Operating System:** Gentoo Linux\n"
            "• **Cores:** 2 cores, 4 threads\n"
            "• **RAM:** System-optimized allocation\n"
            "• **Storage:** Standard SSD\n"
            "• **GPU:** Integrated Intel HD Graphics\n\n"
            
            "**Performance Note:**\n\n"
            "Tangi is optimized to run efficiently on modest hardware while\n"
            "supporting models up to 70B parameters through quantization.\n"
            "Gentoo compilation provides maximum performance per hardware capability.\n\n"
            
            "**Developer Expertise:**\n\n"
            "**Primary Domains:**\n"
            "• Robotics - Hardware integration and control systems\n"
            "• Machine Learning - Model development and deployment\n"
            "• Software Development - Full-stack and system programming\n\n"
            
            "**Technical Focus Areas:**\n"
            "• Automation Engineering - Process optimization\n"
            "• Reverse Engineering - System analysis and modification\n"
            "• Embedded Systems - Low-level hardware programming\n\n"
            
            "**Development Environment:**\n\n"
            "• **Operating System:** Gentoo Linux\n"
            "• **Kernel:** Custom compiled\n"
            "• **Package Management:** Portage\n"
            "• **Compiler:** GCC with architecture-specific optimizations\n"
            "• **USE Flags:** Customized for AI/ML workloads\n\n"
            
            "**Why Gentoo:**\n\n"
            "Gentoo provides complete control over system optimization, allowing\n"
            "for maximum performance on specific hardware. All dependencies are\n"
            "compiled with flags optimized for the i7-6600U processor architecture.\n\n"
            
            "**Development Location:**\n\n"
            "• **City:** Antipolo\n"
            "• **Country:** Philippines\n"
            "• **Time Zone:** Philippine Standard Time (UTC+8)\n"
            "• **Environment:** Home lab setup with Gentoo workstation\n\n"
            
            "**Remote Development:**\n"
            "All development conducted locally with emphasis on offline capability\n"
            "and hardware-optimized performance."
        )

class CommandsCommand(Command):
    """/commands - Show all available commands"""
    
    def __init__(self, parent):
        super().__init__("commands", "Show all available commands", parent)
    
    def execute(self, args):
        # Build main command list
        main_commands = []
        rag_commands = []
        
        # Define all RAG commands - use EXACT names from registry
        rag_command_names = [
            "index", "search", "remove-index", "get-rag",
            "ds", "clear", "cache-info", "rag-status" 
        ]
        
        for name, cmd in self.parent.command_registry.commands.items():
            if name in ["commands", "help"]:
                continue
            elif name in rag_command_names:
                rag_commands.append(f"/{name:<12} - {cmd.description}")
            elif name == "hf":
                continue
            else:
                main_commands.append(f"/{name:<12} - {cmd.description}")
        
        # Build HF subcommands in the same format as other commands
        hf_subcommands = [
            "Hugging Face Commands:",
            "/hf login                 - Log in to Hugging Face Hub",
            "/hf whoami                - Show current user",
            "/hf logout                - Log out",
            "/hf download MODEL_ID [file] - Download a model or specific file",
            "/hf list [models|datasets|spaces] - List popular items",
            "/hf info MODEL_ID         - Show model information",
            "/hf search QUERY          - Search for models",
            "/hf cache                 - Show cache information",
            "/hf env                   - Show environment info",
            "",
            "Examples:",
            "  /hf download gpt2",
            "  /hf download meta-llama/Llama-2-7b config.json",
            "  /hf search text generation",
            "  /hf info mistralai/Mistral-7B-v0.1",
            "",
            "Note: Downloaded models are stored in ~/.cache/huggingface/",
            ""
        ]
        
        # Build output in correct order
        output = []
        output.append("Available Commands:")
        output.append("")
        
        output.append("General Commands:")
        if main_commands:
            output.extend(sorted(main_commands))
        else:
            output.append("  (No general commands found)")
        output.append("")
        
        # Add HF commands
        output.extend(hf_subcommands)
        
        output.append("Retrieval Augmented Generation (RAG) Code Indexing Commands:")
        if rag_commands:
            output.extend(sorted(rag_commands))
        else:
            output.append("  (No RAG commands registered)")
        
        # Send everything as one message
        self.parent.append_command_output("\n".join(output))

class HelpCommand(Command):
    """/help - Alias for /commands"""
    
    def __init__(self, parent):
        super().__init__("help", "Show all available commands", parent)
    
    def execute(self, args):
        # Just delegate to commands command
        self.parent.command_registry.execute("commands")

def register_all_info_commands(registry):
    """Register all info commands with the registry"""
    registry.register(AboutCommand(registry.parent))
    registry.register(CommandsCommand(registry.parent))
    registry.register(HelpCommand(registry.parent))

__all__ = ['register_all_info_commands']
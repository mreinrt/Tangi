"""
Base classes for command handling
"""

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class Command(ABC):
    """Base class for all commands"""
    
    def __init__(self, name, description, parent):
        self.name = name
        self.description = description
        self.parent = parent  # Reference to main window
    
    @abstractmethod
    def execute(self, args):
        """Execute the command with given arguments"""
        pass
    
    def can_execute(self):
        """Check if command can be executed"""
        return True
    
    def get_help(self):
        """Get help text for this command"""
        return f"{self.name} - {self.description}"


class CommandRegistry:
    """Registry for all commands"""
    
    def __init__(self, parent):
        self.parent = parent
        self.commands = {}
        self.logger = logging.getLogger(__name__)
    
    def register(self, command):
        """Register a command"""
        self.commands[command.name] = command
        self.logger.debug(f"Registered command: {command.name}")
    
    def unregister(self, name):
        """Unregister a command"""
        if name in self.commands:
            del self.commands[name]
            self.logger.debug(f"Unregistered command: {name}")
    
    def get_command(self, name):
        """Get a command by name"""
        return self.commands.get(name)
    
    def execute(self, command_line):
        """Execute a command from a string"""
        if not command_line:
            return
        
        parts = command_line.strip().split()
        cmd_name = parts[0].lower()
        args = ' '.join(parts[1:]) if len(parts) > 1 else ''
        
        cmd = self.get_command(cmd_name)
        if cmd:
            if cmd.can_execute():
                cmd.execute(args)
            else:
                self.parent.append_message("system", f"Command '{cmd_name}' cannot be executed right now.")
        else:
            self.parent.append_message("system", f"Unknown command: {cmd_name}")
    
    def get_all_commands(self):
        """Get all registered commands"""
        return self.commands.values()
    
    def get_help_text(self):
        """Get help text for all commands"""
        help_lines = ["Available Commands:"]
        for cmd in sorted(self.commands.values(), key=lambda c: c.name):
            help_lines.append(f"  /{cmd.name:<12} - {cmd.description}")
        return "\n".join(help_lines)


__all__ = ['Command', 'CommandRegistry']
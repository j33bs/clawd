#!/usr/bin/env python3
"""
Tool-Use Governance System with Failure-Mode Awareness
Implements explicit governance for when not to act, detecting mis-specification
"""

import json
import time
import traceback
from typing import Dict, List, Any, Callable, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class FailureType(Enum):
    """Types of failures to track"""
    TRANSIENT_ERROR = "transient_error"
    SPECIFICATION_ERROR = "specification_error" 
    PERMISSION_DENIED = "permission_denied"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    INVALID_INPUT = "invalid_input"
    SYSTEM_UNAVAILABLE = "system_unavailable"


@dataclass
class ToolCallRecord:
    """Record of a tool call attempt"""
    tool_name: str
    parameters: Dict[str, Any]
    timestamp: float
    success: bool
    error: Optional[str] = None
    retry_count: int = 0
    failure_type: Optional[FailureType] = None
    execution_time: Optional[float] = None


@dataclass
class ToolGovernanceRules:
    """Rules governing tool usage"""
    max_retries: int = 3
    retry_backoff_base: float = 1.0  # seconds
    timeout_seconds: float = 30
    max_concurrent_calls: int = 5
    fail_fast_on_spec_errors: bool = True
    max_calls_per_minute: int = 60
    require_confirmation_for_destructive: bool = True


class ToolGovernanceSystem:
    """
    Governs tool usage with failure-mode awareness
    Prevents compulsive automation by detecting when retries indicate mis-specification
    """
    
    def __init__(self, rules: Optional[ToolGovernanceRules] = None):
        self.rules = rules or ToolGovernanceRules()
        self.call_history: List[ToolCallRecord] = []
        self.active_calls: Dict[str, float] = {}  # tool_id -> start_time
        self.call_counts: Dict[str, List[float]] = {}  # tool_name -> list of timestamps
        self.failure_patterns: Dict[str, List[ToolCallRecord]] = {}
    
    def should_retry(self, tool_record: ToolCallRecord) -> bool:
        """
        Determine if a tool call should be retried based on failure analysis
        """
        # Don't retry if we've exceeded max retries
        if tool_record.retry_count >= self.rules.max_retries:
            return False
        
        # Don't retry if it's a specification error (mis-specification)
        if (tool_record.failure_type == FailureType.SPECIFICATION_ERROR and 
            self.rules.fail_fast_on_spec_errors):
            return False
        
        # Don't retry if it's a permission error
        if tool_record.failure_type == FailureType.PERMISSION_DENIED:
            return False
        
        # Don't retry if it's an invalid input error
        if tool_record.failure_type == FailureType.INVALID_INPUT:
            return False
        
        # Check if this looks like a recurring pattern indicating mis-specification
        recent_failures = self._get_recent_failures(tool_record.tool_name, hours=1)
        if len(recent_failures) >= 3:
            # If we have 3+ failures in the last hour for the same tool,
            # with similar error patterns, it may indicate mis-specification
            error_pattern = self._analyze_error_pattern(recent_failures)
            if error_pattern['similarity_score'] > 0.7:
                # High similarity suggests the same underlying issue - don't retry
                return False
        
        return True
    
    def _get_recent_failures(self, tool_name: str, hours: float) -> List[ToolCallRecord]:
        """Get recent failures for a specific tool"""
        cutoff_time = time.time() - (hours * 3600)
        return [
            record for record in self.call_history
            if (record.tool_name == tool_name and 
                not record.success and 
                record.timestamp > cutoff_time)
        ]
    
    def _analyze_error_pattern(self, failures: List[ToolCallRecord]) -> Dict[str, Any]:
        """Analyze patterns in failures to detect recurring issues"""
        if not failures:
            return {'similarity_score': 0.0, 'pattern': 'none'}
        
        # Simple similarity analysis based on error messages
        error_messages = [f.error or "" for f in failures if f.error]
        
        if len(error_messages) < 2:
            return {'similarity_score': 0.0, 'pattern': 'insufficient_data'}
        
        # Calculate similarity between error messages
        similarities = []
        for i in range(len(error_messages)):
            for j in range(i + 1, len(error_messages)):
                sim = self._string_similarity(error_messages[i], error_messages[j])
                similarities.append(sim)
        
        avg_similarity = sum(similarities) / len(similarities) if similarities else 0.0
        
        return {
            'similarity_score': avg_similarity,
            'pattern': 'recurring' if avg_similarity > 0.5 else 'diverse',
            'count': len(error_messages)
        }
    
    def _string_similarity(self, s1: str, s2: str) -> float:
        """Simple string similarity calculation"""
        if not s1 and not s2:
            return 1.0
        if not s1 or not s2:
            return 0.0
        
        # Use a simple character-based similarity
        common_chars = set(s1.lower()) & set(s2.lower())
        total_chars = set(s1.lower()) | set(s2.lower())
        
        return len(common_chars) / len(total_chars) if total_chars else 0.0
    
    def can_execute_tool(self, tool_name: str) -> bool:
        """Check if a tool can be executed given governance rules"""
        # Check rate limiting
        current_time = time.time()
        minute_ago = current_time - 60
        
        recent_calls = [
            ts for ts in self.call_counts.get(tool_name, [])
            if ts > minute_ago
        ]
        
        if len(recent_calls) >= self.rules.max_calls_per_minute:
            return False
        
        # Check concurrent calls
        if len(self.active_calls) >= self.rules.max_concurrent_calls:
            return False
        
        return True
    
    def execute_with_governance(self, tool_func: Callable, tool_name: str, 
                               params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool with governance and failure awareness
        """
        # Check if we can execute the tool
        if not self.can_execute_tool(tool_name):
            return {
                'success': False,
                'error': f'Tool execution blocked by governance rules: {tool_name}',
                'governance_reason': 'rate_limit_exceeded_or_concurrency_limit'
            }
        
        # Track the call
        start_time = time.time()
        call_id = f"{tool_name}_{int(start_time)}"
        
        try:
            # Record the call
            self.active_calls[call_id] = start_time
            
            # Add to call counts
            if tool_name not in self.call_counts:
                self.call_counts[tool_name] = []
            self.call_counts[tool_name].append(start_time)
            
            # Execute the tool
            result = tool_func(**params)
            
            # Record successful execution
            execution_time = time.time() - start_time
            record = ToolCallRecord(
                tool_name=tool_name,
                parameters=params,
                timestamp=start_time,
                success=True,
                execution_time=execution_time
            )
            
            self.call_history.append(record)
            del self.active_calls[call_id]
            
            return {
                'success': True,
                'result': result,
                'execution_time': execution_time
            }
            
        except Exception as e:
            # Record failed execution
            execution_time = time.time() - start_time
            error_msg = str(e)
            
            # Classify the failure type
            failure_type = self._classify_failure(error_msg, params)
            
            record = ToolCallRecord(
                tool_name=tool_name,
                parameters=params,
                timestamp=start_time,
                success=False,
                error=error_msg,
                execution_time=execution_time,
                failure_type=failure_type
            )
            
            self.call_history.append(record)
            del self.active_calls[call_id]
            
            # Store in failure patterns
            if tool_name not in self.failure_patterns:
                self.failure_patterns[tool_name] = []
            self.failure_patterns[tool_name].append(record)
            
            return {
                'success': False,
                'error': error_msg,
                'failure_type': failure_type.value if failure_type else None,
                'should_retry': self.should_retry(record),
                'execution_time': execution_time
            }
    
    def _classify_failure(self, error_message: str, params: Dict[str, Any]) -> Optional[FailureType]:
        """Classify the type of failure based on error message and parameters"""
        error_lower = error_message.lower()
        
        # Check for common patterns
        if any(pattern in error_lower for pattern in [
            'permission denied', 'access denied', 'unauthorized', 'forbidden'
        ]):
            return FailureType.PERMISSION_DENIED
        
        if any(pattern in error_lower for pattern in [
            'timeout', 'timed out', 'connection refused', 'network error'
        ]):
            return FailureType.TRANSIENT_ERROR
        
        if any(pattern in error_lower for pattern in [
            'not found', 'does not exist', 'file not found', 'no such file'
        ]):
            # This could be specification error if the path was wrong
            if 'path' in params or 'file' in str(params).lower():
                return FailureType.SPECIFICATION_ERROR
            else:
                return FailureType.TRANSIENT_ERROR
        
        if any(pattern in error_lower for pattern in [
            'quota', 'limit', 'exceeded', 'resource exhausted', 'out of memory'
        ]):
            return FailureType.RESOURCE_EXHAUSTED
        
        if any(pattern in error_lower for pattern in [
            'invalid', 'malformed', 'bad request', 'validation failed'
        ]):
            return FailureType.INVALID_INPUT
        
        # Default to transient error if no specific pattern matched
        return FailureType.TRANSIENT_ERROR
    
    def get_governance_report(self) -> Dict[str, Any]:
        """Generate a report on tool usage and governance"""
        total_calls = len(self.call_history)
        successful_calls = len([c for c in self.call_history if c.success])
        failed_calls = total_calls - successful_calls
        
        # Analyze failure patterns
        concerning_patterns = {}
        for tool_name, failures in self.failure_patterns.items():
            recent_failures = self._get_recent_failures(tool_name, hours=1)
            if len(recent_failures) >= 3:
                pattern_analysis = self._analyze_error_pattern(recent_failures)
                if pattern_analysis['similarity_score'] > 0.5:
                    concerning_patterns[tool_name] = pattern_analysis
        
        return {
            'total_calls': total_calls,
            'successful_calls': successful_calls,
            'failed_calls': failed_calls,
            'success_rate': successful_calls / total_calls if total_calls > 0 else 0,
            'concerning_patterns': concerning_patterns,
            'active_governance_rules': {
                'max_retries': self.rules.max_retries,
                'fail_fast_on_spec_errors': self.rules.fail_fast_on_spec_errors,
                'max_calls_per_minute': self.rules.max_calls_per_minute
            }
        }


def example_tool_function(file_path: str, content: str = ""):
    """Example tool function that might fail in various ways"""
    import os
    
    # Simulate some validation
    if not file_path:
        raise ValueError("file_path cannot be empty")
    
    if not isinstance(file_path, str):
        raise TypeError("file_path must be a string")
    
    # Simulate file operation
    if not os.path.exists(os.path.dirname(file_path)) and '/nonexistent/' in file_path:
        raise FileNotFoundError(f"Directory does not exist: {os.path.dirname(file_path)}")
    
    # Actually write the file
    with open(file_path, 'w') as f:
        f.write(content)
    
    return f"Successfully wrote {len(content)} characters to {file_path}"


def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python tool_governance.py <command>")
        print("Commands: test, report")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'test':
        # Test the governance system
        gov_system = ToolGovernanceSystem()
        
        # Test successful call
        result = gov_system.execute_with_governance(
            example_tool_function,
            'write_file',
            {'file_path': '/tmp/test.txt', 'content': 'Hello World'}
        )
        print(f"Successful call: {result}")
        
        # Test failing call
        result = gov_system.execute_with_governance(
            example_tool_function,
            'write_file',
            {'file_path': '', 'content': 'Empty path'}
        )
        print(f"Failing call: {result}")
        
        # Test specification error
        result = gov_system.execute_with_governance(
            example_tool_function,
            'write_file',
            {'file_path': '/nonexistent/path/file.txt', 'content': 'Test'}
        )
        print(f"Spec error call: {result}")
        
    elif command == 'report':
        gov_system = ToolGovernanceSystem()
        report = gov_system.get_governance_report()
        print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    # Example usage
    gov_system = ToolGovernanceSystem(ToolGovernanceRules(
        max_retries=2,
        fail_fast_on_spec_errors=True,
        max_calls_per_minute=10
    ))
    
    print("Testing tool governance system...")
    
    # Test various scenarios
    scenarios = [
        # Valid call
        ('write_file', {'file_path': '/tmp/governance_test.txt', 'content': 'Valid content'}),
        
        # Invalid path (specification error)
        ('write_file', {'file_path': '', 'content': 'Empty path'}),
        
        # Non-existent directory (specification error)
        ('write_file', {'file_path': '/nonexistent/dir/file.txt', 'content': 'Test content'})
    ]
    
    for tool_name, params in scenarios:
        print(f"\nExecuting: {tool_name} with {params}")
        result = gov_system.execute_with_governance(example_tool_function, tool_name, params)
        print(f"Result: {result}")
        
        if not result['success'] and result.get('should_retry') is False:
            print("  -> Governance system prevented retry (likely spec error)")
    
    # Generate report
    print("\n" + "="*50)
    print("GOVERNANCE REPORT")
    print("="*50)
    report = gov_system.get_governance_report()
    print(f"Total calls: {report['total_calls']}")
    print(f"Success rate: {report['success_rate']:.2%}")
    print(f"Concerning patterns: {len(report['concerning_patterns'])}")
    
    for tool, pattern in report['concerning_patterns'].items():
        print(f"  {tool}: {pattern}")
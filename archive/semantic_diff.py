#!/usr/bin/env python3
"""
Semantic Diffing System
Computes meaning-level diffs (intent, invariants, side-effects) rather than line diffs
"""

import json
import ast
import difflib
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import hashlib


class ChangeType(Enum):
    """Types of semantic changes"""
    FUNCTIONAL_CHANGE = "functional_change"
    BEHAVIORAL_CHANGE = "behavioral_change"
    PERFORMANCE_CHANGE = "performance_change"
    SECURITY_CHANGE = "security_change"
    INTERFACE_CHANGE = "interface_change"
    INVARIANT_CHANGE = "invariant_change"
    SIDE_EFFECT_CHANGE = "side_effect_change"
    REFACTORING = "refactoring"
    DOCUMENTATION = "documentation"


@dataclass
class SemanticDiff:
    """Represents a semantic difference between two versions"""
    type: ChangeType
    description: str
    severity: str  # 'low', 'medium', 'high', 'critical'
    affected_components: List[str]
    impact_assessment: str
    confidence: float  # 0.0 to 1.0


@dataclass
class CodeAnalysis:
    """Analysis of a code version"""
    functions: List[Dict[str, Any]]
    classes: List[Dict[str, Any]]
    imports: List[str]
    constants: List[Dict[str, Any]]
    side_effects: List[str]
    invariants: List[str]
    interfaces: List[Dict[str, Any]]
    performance_characteristics: Dict[str, Any]


class SemanticDiffer:
    """
    Computes semantic diffs that capture meaning-level changes
    rather than just syntactic differences
    """
    
    def __init__(self):
        self.known_patterns = {
            'security': ['password', 'secret', 'token', 'auth', 'credential', 'encrypt', 'decrypt'],
            'performance': ['time', 'memory', 'speed', 'efficiency', 'optimize', 'cache', 'parallel'],
            'interface': ['api', 'endpoint', 'protocol', 'request', 'response', 'param', 'argument'],
            'behavior': ['if', 'else', 'while', 'for', 'return', 'raise', 'exception']
        }
    
    def analyze_code(self, code: str) -> CodeAnalysis:
        """Analyze code to extract semantic elements"""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            # If parsing fails, return basic analysis
            return self._basic_analysis(code)
        
        analysis = CodeAnalysis(
            functions=[],
            classes=[],
            imports=[],
            constants=[],
            side_effects=[],
            invariants=[],
            interfaces=[],
            performance_characteristics={}
        )
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_info = {
                    'name': node.name,
                    'args': [arg.arg for arg in node.args.args],
                    'returns': self._get_return_annotation(node),
                    'docstring': ast.get_docstring(node),
                    'line_start': node.lineno,
                    'line_end': self._get_end_lineno(node)
                }
                analysis.functions.append(func_info)
                
                # Analyze function body for side effects
                side_effects = self._analyze_function_side_effects(node)
                analysis.side_effects.extend(side_effects)
                
            elif isinstance(node, ast.ClassDef):
                class_info = {
                    'name': node.name,
                    'bases': [base.id for base in node.bases if isinstance(base, ast.Name)],
                    'methods': [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                }
                analysis.classes.append(class_info)
                
            elif isinstance(node, ast.Import):
                analysis.imports.extend([alias.name for alias in node.names])
                
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                analysis.imports.extend([f"{module}.{alias.name}" for alias in node.names])
                
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                # Extract constants
                if isinstance(node, ast.Assign) and len(node.targets) == 1:
                    target = node.targets[0]
                    if isinstance(target, ast.Name) and target.id.isupper():
                        const_info = {
                            'name': target.id,
                            'value_type': self._get_value_type(node.value),
                            'line': node.lineno
                        }
                        analysis.constants.append(const_info)
        
        # Analyze for invariants and interfaces
        analysis.invariants = self._extract_invariants(code)
        analysis.interfaces = self._extract_interfaces(code)
        
        return analysis
    
    def _basic_analysis(self, code: str) -> CodeAnalysis:
        """Basic analysis when AST parsing fails"""
        lines = code.split('\n')
        analysis = CodeAnalysis(
            functions=[],
            classes=[],
            imports=[],
            constants=[],
            side_effects=[],
            invariants=[],
            interfaces=[],
            performance_characteristics={}
        )
        
        # Simple pattern matching for basic analysis
        for i, line in enumerate(lines):
            if 'def ' in line and '(' in line and ')' in line:
                # Extract function definition
                parts = line.split('def ')
                if len(parts) > 1:
                    func_name = parts[1].split('(')[0].strip()
                    analysis.functions.append({
                        'name': func_name,
                        'line_start': i + 1,
                        'args': []
                    })
            elif 'class ' in line and ':' in line:
                # Extract class definition
                parts = line.split('class ')
                if len(parts) > 1:
                    class_name = parts[1].split(':')[0].split('(')[0].strip()
                    analysis.classes.append({
                        'name': class_name
                    })
            elif 'import ' in line:
                # Extract imports
                analysis.imports.append(line.strip())
        
        return analysis
    
    def _get_return_annotation(self, node: ast.FunctionDef) -> Optional[str]:
        """Extract return annotation from function"""
        if hasattr(node, 'returns') and node.returns:
            return ast.unparse(node.returns)
        return None
    
    def _get_end_lineno(self, node: ast.AST) -> int:
        """Get end line number of a node"""
        if hasattr(node, 'end_lineno') and node.end_lineno:
            return node.end_lineno
        return node.lineno
    
    def _get_value_type(self, value_node: ast.AST) -> str:
        """Get the type of a value node"""
        if isinstance(value_node, ast.Constant):
            return type(value_node.value).__name__
        elif isinstance(value_node, ast.List):
            return 'list'
        elif isinstance(value_node, ast.Dict):
            return 'dict'
        elif isinstance(value_node, ast.Call):
            return 'call'
        else:
            return 'unknown'
    
    def _analyze_function_side_effects(self, func_node: ast.FunctionDef) -> List[str]:
        """Analyze function for potential side effects"""
        side_effects = []
        
        for node in ast.walk(func_node):
            if isinstance(node, ast.Call):
                # Check for function calls that might have side effects
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                    if func_name in ['print', 'input', 'open', 'write', 'append']:
                        side_effects.append(f"Potential side effect: {func_name} call")
                    elif 'file' in func_name.lower() or 'io' in func_name.lower():
                        side_effects.append(f"IO operation: {func_name}")
            elif isinstance(node, ast.Attribute):
                # Check for attribute modifications
                if isinstance(node.ctx, ast.Store):
                    side_effects.append(f"Attribute modification: {ast.unparse(node)}")
        
        return side_effects
    
    def _extract_invariants(self, code: str) -> List[str]:
        """Extract potential invariants from code"""
        invariants = []
        lines = code.split('\n')
        
        for line in lines:
            # Look for assertions and conditions that might represent invariants
            if 'assert' in line:
                assertion = line.strip()
                invariants.append(assertion)
            elif '==' in line and 'if' in line:
                # Potential invariant condition
                invariants.append(line.strip())
        
        return invariants
    
    def _extract_interfaces(self, code: str) -> List[Dict[str, Any]]:
        """Extract interface-like elements from code"""
        interfaces = []
        lines = code.split('\n')
        
        for i, line in enumerate(lines):
            if 'def ' in line and '(' in line and ')' in line:
                # Extract function signature
                func_def = line.strip()
                interfaces.append({
                    'signature': func_def,
                    'line_number': i + 1
                })
        
        return interfaces
    
    def compute_semantic_diff(self, old_code: str, new_code: str) -> List[SemanticDiff]:
        """Compute semantic differences between two code versions"""
        old_analysis = self.analyze_code(old_code)
        new_analysis = self.analyze_code(new_code)
        
        diffs = []
        
        # Compare functions
        diffs.extend(self._compare_functions(old_analysis.functions, new_analysis.functions))
        
        # Compare classes
        diffs.extend(self._compare_classes(old_analysis.classes, new_analysis.classes))
        
        # Compare imports
        diffs.extend(self._compare_imports(old_analysis.imports, new_analysis.imports))
        
        # Compare side effects
        diffs.extend(self._compare_side_effects(old_analysis.side_effects, new_analysis.side_effects))
        
        # Compare invariants
        diffs.extend(self._compare_invariants(old_analysis.invariants, new_analysis.invariants))
        
        # Compare interfaces
        diffs.extend(self._compare_interfaces(old_analysis.interfaces, new_analysis.interfaces))
        
        # Compare overall code structure
        diffs.extend(self._compare_code_structure(old_code, new_code))
        
        return diffs
    
    def _compare_functions(self, old_funcs: List[Dict], new_funcs: List[Dict]) -> List[SemanticDiff]:
        """Compare function definitions between versions"""
        diffs = []
        
        old_names = {f['name'] for f in old_funcs}
        new_names = {f['name'] for f in new_funcs}
        
        # Added functions
        added = new_names - old_names
        if added:
            diffs.append(SemanticDiff(
                type=ChangeType.INTERFACE_CHANGE,
                description=f"Added functions: {', '.join(added)}",
                severity='medium',
                affected_components=list(added),
                impact_assessment='New functionality added to the system',
                confidence=0.9
            ))
        
        # Removed functions
        removed = old_names - new_names
        if removed:
            diffs.append(SemanticDiff(
                type=ChangeType.INTERFACE_CHANGE,
                description=f"Removed functions: {', '.join(removed)}",
                severity='high',
                affected_components=list(removed),
                impact_assessment='Functionality removed from the system',
                confidence=0.9
            ))
        
        # Modified functions
        for func_name in old_names & new_names:
            old_func = next(f for f in old_funcs if f['name'] == func_name)
            new_func = next(f for f in new_funcs if f['name'] == func_name)
            
            if old_func != new_func:
                # Check what specifically changed
                if old_func.get('args') != new_func.get('args'):
                    diffs.append(SemanticDiff(
                        type=ChangeType.INTERFACE_CHANGE,
                        description=f"Changed parameters for function '{func_name}'",
                        severity='high',
                        affected_components=[func_name],
                        impact_assessment='Function signature changed, may break calling code',
                        confidence=0.8
                    ))
                
                if old_func.get('returns') != new_func.get('returns'):
                    diffs.append(SemanticDiff(
                        type=ChangeType.BEHAVIORAL_CHANGE,
                        description=f"Changed return type for function '{func_name}'",
                        severity='medium',
                        affected_components=[func_name],
                        impact_assessment='Return behavior changed',
                        confidence=0.7
                    ))
        
        return diffs
    
    def _compare_classes(self, old_classes: List[Dict], new_classes: List[Dict]) -> List[SemanticDiff]:
        """Compare class definitions between versions"""
        diffs = []
        
        old_names = {c['name'] for c in old_classes}
        new_names = {c['name'] for c in new_classes}
        
        # Added classes
        added = new_names - old_names
        if added:
            diffs.append(SemanticDiff(
                type=ChangeType.INTERFACE_CHANGE,
                description=f"Added classes: {', '.join(added)}",
                severity='medium',
                affected_components=list(added),
                impact_assessment='New abstractions added to the system',
                confidence=0.8
            ))
        
        # Removed classes
        removed = old_names - new_names
        if removed:
            diffs.append(SemanticDiff(
                type=ChangeType.INTERFACE_CHANGE,
                description=f"Removed classes: {', '.join(removed)}",
                severity='high',
                affected_components=list(removed),
                impact_assessment='Abstractions removed from the system',
                confidence=0.9
            ))
        
        return diffs
    
    def _compare_imports(self, old_imports: List[str], new_imports: List[str]) -> List[SemanticDiff]:
        """Compare imports between versions"""
        diffs = []
        
        old_set = set(old_imports)
        new_set = set(new_imports)
        
        added = new_set - old_set
        removed = old_set - new_set
        
        if added:
            diffs.append(SemanticDiff(
                type=ChangeType.FUNCTIONAL_CHANGE,
                description=f"Added imports: {', '.join(added)}",
                severity='low',
                affected_components=list(added),
                impact_assessment='New dependencies introduced',
                confidence=0.7
            ))
        
        if removed:
            diffs.append(SemanticDiff(
                type=ChangeType.FUNCTIONAL_CHANGE,
                description=f"Removed imports: {', '.join(removed)}",
                severity='medium',
                affected_components=list(removed),
                impact_assessment='Dependencies removed',
                confidence=0.7
            ))
        
        return diffs
    
    def _compare_side_effects(self, old_effects: List[str], new_effects: List[str]) -> List[SemanticDiff]:
        """Compare side effects between versions"""
        diffs = []
        
        old_set = set(old_effects)
        new_set = set(new_effects)
        
        added = new_set - old_set
        removed = old_set - new_set
        
        if added:
            diffs.append(SemanticDiff(
                type=ChangeType.SIDE_EFFECT_CHANGE,
                description=f"New side effects introduced: {', '.join(added)}",
                severity='high',
                affected_components=['side_effects'],
                impact_assessment='New side effects may affect system behavior',
                confidence=0.8
            ))
        
        if removed:
            diffs.append(SemanticDiff(
                type=ChangeType.SIDE_EFFECT_CHANGE,
                description=f"Side effects removed: {', '.join(removed)}",
                severity='medium',
                affected_components=['side_effects'],
                impact_assessment='Side effects eliminated',
                confidence=0.7
            ))
        
        return diffs
    
    def _compare_invariants(self, old_invs: List[str], new_invs: List[str]) -> List[SemanticDiff]:
        """Compare invariants between versions"""
        diffs = []
        
        old_set = set(old_invs)
        new_set = set(new_invs)
        
        added = new_set - old_set
        removed = old_set - new_set
        
        if added:
            diffs.append(SemanticDiff(
                type=ChangeType.INVARIANT_CHANGE,
                description=f"New invariants added: {len(added)} assertions",
                severity='medium',
                affected_components=['invariants'],
                impact_assessment='Additional correctness constraints added',
                confidence=0.7
            ))
        
        if removed:
            diffs.append(SemanticDiff(
                type=ChangeType.INVARIANT_CHANGE,
                description=f"Invariants removed: {len(removed)} assertions",
                severity='high',
                affected_components=['invariants'],
                impact_assessment='Correctness constraints removed',
                confidence=0.8
            ))
        
        return diffs
    
    def _compare_interfaces(self, old_ifaces: List[Dict], new_ifaces: List[Dict]) -> List[SemanticDiff]:
        """Compare interfaces between versions"""
        diffs = []
        
        old_signatures = {iface['signature'] for iface in old_ifaces}
        new_signatures = {iface['signature'] for iface in new_ifaces}
        
        added = new_signatures - old_signatures
        removed = old_signatures - new_signatures
        
        if added:
            diffs.append(SemanticDiff(
                type=ChangeType.INTERFACE_CHANGE,
                description=f"New interface signatures added: {len(added)}",
                severity='medium',
                affected_components=['interfaces'],
                impact_assessment='New interface contracts defined',
                confidence=0.8
            ))
        
        if removed:
            diffs.append(SemanticDiff(
                type=ChangeType.INTERFACE_CHANGE,
                description=f"Interface signatures removed: {len(removed)}",
                severity='high',
                affected_components=['interfaces'],
                impact_assessment='Interface contracts removed',
                confidence=0.9
            ))
        
        return diffs
    
    def _compare_code_structure(self, old_code: str, new_code: str) -> List[SemanticDiff]:
        """Compare overall code structure and complexity"""
        diffs = []
        
        # Compare line counts
        old_lines = len(old_code.split('\n'))
        new_lines = len(new_code.split('\n'))
        
        if abs(new_lines - old_lines) > max(old_lines, new_lines) * 0.3:  # More than 30% change
            change_direction = "increased" if new_lines > old_lines else "decreased"
            diffs.append(SemanticDiff(
                type=ChangeType.REFACTORING,
                description=f"Code size {change_direction} significantly ({old_lines} → {new_lines} lines)",
                severity='medium',
                affected_components=['overall_structure'],
                impact_assessment=f'Significant structural change: {change_direction}',
                confidence=0.6
            ))
        
        # Compute traditional diff for additional context
        old_lines_list = old_code.split('\n')
        new_lines_list = new_code.split('\n')
        
        # Look for security-related changes
        security_changes = self._find_security_related_changes(old_lines_list, new_lines_list)
        if security_changes:
            diffs.append(SemanticDiff(
                type=ChangeType.SECURITY_CHANGE,
                description=f"Security-related changes: {', '.join(security_changes)}",
                severity='high',
                affected_components=security_changes,
                impact_assessment='Changes affecting security properties',
                confidence=0.8
            ))
        
        return diffs
    
    def _find_security_related_changes(self, old_lines: List[str], new_lines: List[str]) -> List[str]:
        """Find security-related changes in the diff"""
        changes = set()
        
        # Create a unified diff
        diff = list(difflib.unified_diff(old_lines, new_lines, lineterm=''))
        
        for line in diff:
            if line.startswith('+') or line.startswith('-'):
                lower_line = line[1:].lower()  # Remove + or - prefix
                for category, patterns in self.known_patterns.items():
                    if category == 'security':
                        for pattern in patterns:
                            if pattern in lower_line:
                                changes.add(pattern)
        
        return list(changes)
    
    def generate_diff_report(self, old_code: str, new_code: str) -> Dict[str, Any]:
        """Generate a comprehensive semantic diff report"""
        diffs = self.compute_semantic_diff(old_code, new_code)
        
        # Categorize by severity
        high_severity = [d for d in diffs if d.severity == 'high' or d.severity == 'critical']
        medium_severity = [d for d in diffs if d.severity == 'medium']
        low_severity = [d for d in diffs if d.severity == 'low']
        
        # Calculate overall risk
        risk_score = sum({
            'critical': 10,
            'high': 7,
            'medium': 4,
            'low': 1
        }.get(d.severity, 0) for d in diffs)
        
        return {
            'total_changes': len(diffs),
            'high_severity_changes': len(high_severity),
            'medium_severity_changes': len(medium_severity),
            'low_severity_changes': len(low_severity),
            'risk_score': risk_score,
            'risk_level': self._calculate_risk_level(risk_score),
            'changes_by_type': self._group_changes_by_type(diffs),
            'detailed_changes': [
                {
                    'type': diff.type.value,
                    'description': diff.description,
                    'severity': diff.severity,
                    'affected_components': diff.affected_components,
                    'impact': diff.impact_assessment,
                    'confidence': diff.confidence
                } for diff in diffs
            ]
        }
    
    def _calculate_risk_level(self, risk_score: int) -> str:
        """Calculate risk level based on risk score"""
        if risk_score >= 20:
            return 'critical'
        elif risk_score >= 10:
            return 'high'
        elif risk_score >= 5:
            return 'medium'
        else:
            return 'low'
    
    def _group_changes_by_type(self, diffs: List[SemanticDiff]) -> Dict[str, int]:
        """Group changes by type"""
        groups = {}
        for diff in diffs:
            type_name = diff.type.value
            groups[type_name] = groups.get(type_name, 0) + 1
        return groups


def main():
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python semantic_diff.py <old_file> <new_file>")
        sys.exit(1)
    
    old_file = sys.argv[1]
    new_file = sys.argv[2]
    
    with open(old_file, 'r') as f:
        old_code = f.read()
    
    with open(new_file, 'r') as f:
        new_code = f.read()
    
    differ = SemanticDiffer()
    report = differ.generate_diff_report(old_code, new_code)
    
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    # Example usage with sample code
    print("Semantic Diffing System")
    print("=" * 40)
    
    # Sample code versions to compare
    old_code = '''
def authenticate_user(username, password):
    """Authenticate user with username and password"""
    if username == "admin" and password == "secret":
        return True
    return False

def process_data(data):
    """Process input data"""
    result = []
    for item in data:
        if item > 0:
            result.append(item * 2)
    return result
'''
    
    new_code = '''
import hashlib
import logging

def authenticate_user(username, password):
    """Authenticate user with hashed password comparison"""
    stored_hash = get_password_hash(username)  # Retrieve from secure storage
    input_hash = hashlib.sha256(password.encode()).hexdigest()
    return stored_hash == input_hash

def process_data(data, multiplier=2):
    """Process input data with configurable multiplier"""
    if not data:
        logging.warning("Empty data provided to process_data")
        return []
    
    result = []
    for item in data:
        if item > 0:
            result.append(item * multiplier)
    return result

def get_password_hash(username):
    """Retrieve password hash for user from secure storage"""
    # Implementation would retrieve from secure database
    pass
'''
    
    differ = SemanticDiffer()
    report = differ.generate_diff_report(old_code, new_code)
    
    print(f"Total changes detected: {report['total_changes']}")
    print(f"Risk level: {report['risk_level']} (score: {report['risk_score']})")
    print(f"High severity: {report['high_severity_changes']}")
    print(f"Medium severity: {report['medium_severity_changes']}")
    print(f"Low severity: {report['low_severity_changes']}")
    
    print(f"\nChanges by type:")
    for change_type, count in report['changes_by_type'].items():
        print(f"  {change_type}: {count}")
    
    print(f"\nDetailed changes:")
    for change in report['detailed_changes'][:5]:  # Show first 5
        print(f"  [{change['severity'].upper()}] {change['type']}: {change['description']}")
        print(f"    Impact: {change['impact']}")
        print(f"    Confidence: {change['confidence']:.2f}")
        print()
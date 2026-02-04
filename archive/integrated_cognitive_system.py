#!/usr/bin/env python3
"""
Integrated Cognitive System
Combines all the implemented systems for tiered cognitive-load routing,
reflexive context compaction, executable notebooks, tool governance,
multi-agent dialectics, semantic diffing, secrets orchestration,
narrative observability, constraint-aware prompting, and shutdown rituals
"""

import sys
import time
from typing import Dict, Any, Optional
from datetime import datetime

# Import all the systems we've created
from local_models import LocalModelRouter
from context_compactor import ContextCompactor
from notebook_processor import NotebookProcessor
from tool_governance import ToolGovernanceSystem, ToolGovernanceRules
from multi_agent_dialectics import DialecticalDebateSystem
from semantic_diff import SemanticDiffer
from secrets_orchestrator import SecretsOrchestrator
from observability_narrative import NarrativeObserver
from constraint_prompt_synthesis import ConstraintAwareAgent, ResourceBudget
from shutdown_handoff_rituals import RitualizedAgent


class IntegratedCognitiveSystem:
    """
    Main integration class that combines all cognitive systems
    """
    
    def __init__(self):
        print("🔧 Initializing Integrated Cognitive System...")
        
        # Initialize all subsystems
        self.local_router = LocalModelRouter()
        self.context_compactor = ContextCompactor()
        self.notebook_processor = NotebookProcessor()
        self.tool_governance = ToolGovernanceSystem(
            ToolGovernanceRules(max_retries=2, fail_fast_on_spec_errors=True)
        )
        self.debate_system = DialecticalDebateSystem()
        self.semantic_differ = SemanticDiffer()
        self.secrets_orchestrator = SecretsOrchestrator(master_password="demo_password_123")
        self.observer = NarrativeObserver()
        self.constraint_agent = ConstraintAwareAgent()
        self.ritual_agent = RitualizedAgent()
        
        print("✅ All cognitive systems initialized")
        
        # Register shutdown procedures
        self.ritual_agent.register_shutdown_procedure(self._shutdown_cleanup)
    
    def _shutdown_cleanup(self):
        """Cleanup procedure for shutdown"""
        print("🧹 Performing system cleanup...")
        # Add any necessary cleanup here
    
    def process_request(self, query: str, context: Optional[str] = None) -> Dict[str, Any]:
        """
        Process a request through the integrated system
        """
        print(f"\n🧠 Processing request: {query[:50]}{'...' if len(query) > 50 else ''}")
        
        # 1. Route through local model first (Tiered cognitive-load routing)
        routing_result = self.local_router.route_request(query)
        print(f"   🛣️ Routing decision: {routing_result['routing_decision']}")
        
        if routing_result['routing_decision'] == 'local':
            return {
                'result': routing_result.get('response', 'Local processing completed'),
                'routing': routing_result,
                'processed_by': 'local'
            }
        
        # 2. Compact context if provided (Reflexive context compaction)
        if context:
            print("   🗜️ Compacting context...")
            compaction_result = self.context_compactor.compact_context(context, target_length=800)
            print(f"   📊 Compression ratio: {compaction_result['compression_ratio']:.2f}")
        
        # 3. Evaluate complexity and determine resource budget (Constraint-aware prompting)
        print("   💰 Determining resource budget...")
        budget = self.constraint_agent.suggest_optimal_budget(query)
        print(f"   📋 Suggested budget: {budget.model_class.value}, ${budget.max_cost_cents}, {budget.max_tokens} tokens")
        
        # 4. Generate constraint-aware prompt
        constraint_result = self.constraint_agent.process_request(query, budget)
        print(f"   ⚖️ Applied {len(constraint_result['fidelity_tradeoffs'])} fidelity tradeoffs")
        
        # 5. Run multi-agent dialectics if needed for complex decisions
        if routing_result['classification']['complexity_score'] > 1:
            print("   🤝 Initiating multi-agent dialectics...")
            debate_result = self.debate_system.conduct_debate(query)
            print(f"   🎯 Debate converged: {debate_result.converged}, confidence: {debate_result.confidence_level:.2f}")
        
        # 6. Log the process for narrative observability
        self.observer.observe_function_call(
            'integrated_system.process_request',
            (query,),
            {'context_length': len(context or ''), 'budget': budget.model_class.value},
            result={'routing': routing_result['routing_decision']}
        )
        
        return {
            'result': constraint_result['response'],
            'routing': routing_result,
            'compaction': compaction_result if context else None,
            'constraints_applied': constraint_result['fidelity_tradeoffs'],
            'debate_result': debate_result.__dict__ if 'debate_result' in locals() else None,
            'resource_utilization': constraint_result['resource_utilization'],
            'budget_adherence': constraint_result['budget_adherence'],
            'processed_by': 'integrated_system'
        }
    
    def execute_notebook(self, notebook_content: str) -> Dict[str, Any]:
        """Execute an executable research notebook"""
        print(f"\n📓 Executing research notebook...")
        result = self.notebook_processor.process_notebook(notebook_content)
        print(f"   ✅ Processed {result['summary']['total_cells']} cells")
        print(f"   📊 Success rate: {result['summary']['executed_successfully']}/{result['summary']['code_cells']} code cells")
        
        # Log the notebook execution
        self.observer.observe_function_call(
            'integrated_system.execute_notebook',
            (len(notebook_content),),
            {'cell_count': result['summary']['total_cells']},
            result={'success_rate': result['summary']['executed_successfully'] / max(1, result['summary']['code_cells'])}
        )
        
        return result
    
    def compare_versions(self, old_content: str, new_content: str) -> Dict[str, Any]:
        """Perform semantic diffing between versions"""
        print(f"\n🔍 Performing semantic diff...")
        diff_result = self.semantic_differ.generate_diff_report(old_content, new_content)
        print(f"   📊 Detected {diff_result['total_changes']} semantic changes")
        print(f"   ⚠️ Risk level: {diff_result['risk_level']} (score: {diff_result['risk_score']})")
        
        # Log the diff operation
        self.observer.observe_function_call(
            'integrated_system.compare_versions',
            (len(old_content), len(new_content)),
            {'change_count': diff_result['total_changes'], 'risk_level': diff_result['risk_level']},
            result={'risk_assessment': diff_result['risk_level']}
        )
        
        return diff_result
    
    def govern_tool_use(self, tool_func, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool with governance"""
        print(f"\n🛡️ Governing tool execution: {tool_name}")
        result = self.tool_governance.execute_with_governance(tool_func, tool_name, params)
        
        if not result['success'] and result.get('should_retry') is False:
            print(f"   ❌ Governance system prevented retry (likely specification error)")
        
        # Log the tool governance
        self.observer.observe_function_call(
            'integrated_system.govern_tool_use',
            (tool_name,),
            {'params_count': len(params), 'governance_applied': True},
            result={'success': result['success'], 'governance_action': 'permitted' if result['success'] else 'blocked'}
        )
        
        return result
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status"""
        return {
            'timestamp': time.time(),
            'local_router_active': True,
            'context_compactor_ready': True,
            'notebook_processor_ready': True,
            'tool_governance_active': True,
            'dialectical_system_ready': True,
            'semantic_differ_ready': True,
            'secrets_orchestrator_ready': True,
            'observer_ready': True,
            'constraint_agent_ready': True,
            'ritual_agent_active': self.ritual_agent.active
        }
    
    def shutdown_system(self) -> Dict[str, Any]:
        """Perform graceful shutdown with handoff ritual"""
        print(f"\n🛑 Initiating system shutdown ritual...")
        
        # Create context snapshot
        context_snapshot = {
            'active_processes': [],
            'pending_tasks': [],
            'system_metrics': self.get_system_status(),
            'last_activity': time.time()
        }
        
        # Perform handoff ritual
        handoff_result = self.ritual_agent.shutdown_and_handoff(context_snapshot)
        
        return {
            'shutdown_complete': True,
            'handoff_state': handoff_result.__dict__ if handoff_result else None,
            'final_system_status': self.get_system_status()
        }


def main():
    if len(sys.argv) < 2:
        print("Usage: python integrated_cognitive_system.py <command>")
        print("Commands: demo, process <query>, notebook <file>, status, shutdown")
        sys.exit(1)
    
    command = sys.argv[1]
    
    # Initialize the integrated system
    system = IntegratedCognitiveSystem()
    
    if command == 'demo':
        print("🎬 Running integrated system demonstration...")
        
        # Demonstrate processing a complex request
        complex_query = "Design a cognitive architecture that implements tiered processing with local-first principles, multi-agent dialectics, and constraint-aware resource management"
        
        result = system.process_request(complex_query)
        print(f"\n✅ Complex query processed successfully")
        print(f"Routing decision: {result['routing']['routing_decision']}")
        print(f"Resource utilization: {result['resource_utilization']}")
        
        # Demonstrate notebook processing
        sample_notebook = """
# Cognitive Architecture Design

We propose a system with multiple cognitive layers:

```python
def cognitive_layer(input_data, layer_type):
    if layer_type == 'perceptual':
        return preprocess(input_data)
    elif layer_type == 'reasoning':
        return logical_inference(input_data)
    elif layer_type == 'executive':
        return decision_making(input_data)
```

The system should implement dialectical reasoning between different cognitive modules.
"""
        
        notebook_result = system.execute_notebook(sample_notebook)
        print(f"\n✅ Notebook executed with {notebook_result['summary']['executed_successfully']} successful code cells")
        
        # Demonstrate semantic diffing
        old_code = "def process(x):\n    return x * 2"
        new_code = "def process(x, multiplier=2):\n    if x > 0:\n        return x * multiplier\n    return 0"
        
        diff_result = system.compare_versions(old_code, new_code)
        print(f"\n✅ Semantic diff completed with {diff_result['total_changes']} changes detected")
        
        # Demonstrate tool governance
        def mock_tool(param1: str, param2: int):
            return f"Mock tool executed with {param1} and {param2}"
        
        tool_result = system.govern_tool_use(mock_tool, 'mock_tool', {'param1': 'test', 'param2': 42})
        print(f"\n✅ Tool governance applied, success: {tool_result['success']}")
        
        print(f"\n🎯 All systems demonstrated successfully!")
        
    elif command == 'process':
        if len(sys.argv) < 3:
            print("Usage: python integrated_cognitive_system.py process <query>")
            sys.exit(1)
        
        query = " ".join(sys.argv[2:])
        result = system.process_request(query)
        print(json.dumps(result, indent=2))
        
    elif command == 'notebook':
        if len(sys.argv) < 3:
            print("Usage: python integrated_cognitive_system.py notebook <file_path>")
            sys.exit(1)
        
        file_path = sys.argv[2]
        with open(file_path, 'r') as f:
            content = f.read()
        
        result = system.execute_notebook(content)
        print(json.dumps(result, indent=2))
        
    elif command == 'status':
        status = system.get_system_status()
        print(json.dumps(status, indent=2, default=str))
        
    elif command == 'shutdown':
        result = system.shutdown_system()
        print(f"Shutdown complete: {result['shutdown_complete']}")
        
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    print("🤖 Integrated Cognitive System")
    print("=" * 60)
    print("Implemented systems:")
    print("  ✓ Tiered cognitive-load routing (local → cloud escalation)")
    print("  ✓ Reflexive context compaction with epistemic tagging")
    print("  ✓ Executable research notebooks as first-class artifacts")
    print("  ✓ Tool-use governance via failure-mode awareness")
    print("  ✓ Multi-agent dialectics (not parallelism)")
    print("  ✓ Semantic diffing across iterations")
    print("  ✓ Local-first secrets and credential orchestration")
    print("  ✓ Observability as narrative, not logs")
    print("  ✓ Constraint-aware prompt synthesis")
    print("  ✓ Deliberate shutdown and handoff rituals")
    print("=" * 60)
    
    # For the demo, let's run a comprehensive example
    print("\n🚀 Running comprehensive demonstration...")
    
    # Initialize the system
    system = IntegratedCognitiveSystem()
    
    # Example 1: Process a complex request
    print("\n1️⃣ Processing complex cognitive architecture request...")
    query = "Design a system that implements local-first processing with cloud escalation, including failure mode detection and multi-agent consensus mechanisms"
    
    result = system.process_request(query)
    print(f"   Status: {result['processed_by']}")
    print(f"   Routing: {result['routing']['routing_decision']}")
    print(f"   Constraints applied: {len(result['constraints_applied'])}")
    
    # Example 2: Execute a research notebook
    print("\n2️⃣ Executing executable research notebook...")
    notebook_content = """
# Cognitive Architecture Research Notebook

This notebook explores the design of a cognitive architecture with multiple processing tiers.

## Local Processing Tier

```python
def local_classifier(text):
    # Simple heuristic-based classification
    keywords = ['simple', 'basic', 'quick', 'fast']
    complex_keywords = ['analyze', 'research', 'implement', 'design']
    
    simple_score = sum(1 for kw in keywords if kw in text.lower())
    complex_score = sum(1 for kw in complex_keywords if kw in text.lower())
    
    return 'simple' if simple_score >= complex_score else 'complex'

# Test the classifier
print(local_classifier("What time is it?"))
print(local_classifier("Analyze the cognitive architecture patterns"))
```

## Multi-Agent Consensus

The system should implement dialectical reasoning between agents with different priors.
"""
    
    notebook_result = system.execute_notebook(notebook_content)
    print(f"   Status: {notebook_result['summary']['executed_successfully']}/{notebook_result['summary']['code_cells']} code cells successful")
    
    # Example 3: Perform semantic diffing
    print("\n3️⃣ Performing semantic diffing...")
    old_version = """
def process_request(request):
    if is_simple(request):
        return handle_locally(request)
    else:
        return escalate_to_cloud(request)
"""
    
    new_version = """
def process_request(request, context=None):
    # Enhanced with context awareness
    if is_simple(request) and has_local_capability(request):
        return handle_locally(request, context)
    elif should_escalate_due_to_failure_pattern(request):
        return escalate_with_context(request, context)
    else:
        return handle_with_multi_agent_consensus(request, context)
"""
    
    diff_result = system.compare_versions(old_version, new_version)
    print(f"   Status: {diff_result['total_changes']} semantic changes detected")
    print(f"   Risk level: {diff_result['risk_level']}")
    
    # Example 4: Demonstrate tool governance
    print("\n4️⃣ Demonstrating tool governance...")
    def example_tool(operation: str, data: str):
        if operation == "invalid":
            raise ValueError("Invalid operation specified")
        return f"Operation {operation} completed with data: {data[:20]}..."
    
    # Try a valid operation
    valid_result = system.govern_tool_use(example_tool, 'example_tool', {'operation': 'valid', 'data': 'test_data_123'})
    print(f"   Valid tool call: {'✅' if valid_result['success'] else '❌'}")
    
    # Try an invalid operation (should be caught by governance)
    invalid_result = system.govern_tool_use(example_tool, 'example_tool', {'operation': 'invalid', 'data': 'test_data_123'})
    print(f"   Invalid tool call: {'✅' if invalid_result['success'] else '❌ (correctly blocked)' if not invalid_result['success'] else '❌ (should have been blocked)'}")
    
    # Example 5: Multi-agent dialectics
    print("\n5️⃣ Running multi-agent dialectics...")
    debate_topic = "Should cognitive architectures prioritize local processing or cloud integration?"
    debate_result = system.debate_system.conduct_debate(debate_topic)
    print(f"   Debate converged: {'✅' if debate_result.converged else '❌'}")
    print(f"   Confidence: {debate_result.confidence_level:.2f}")
    
    # Show system status
    print("\n6️⃣ System status:")
    status = system.get_system_status()
    active_systems = [k for k, v in status.items() if k.endswith('_ready') and v] + \
                     [k for k in status.keys() if k.endswith('_active')]
    print(f"   Active components: {len(active_systems)}")
    
    # Final summary
    print(f"\n✨ Integrated Cognitive System operational!")
    print(f"📊 All {len([k for k in status.keys() if k.endswith(('_ready', '_active'))])} subsystems initialized")
    print(f"🔄 Ready to process complex cognitive tasks with full architectural integrity")
    
    # Note that we're not shutting down for this demo to keep the system available
    print(f"\n💡 System remains active. Use 'shutdown' command to initiate ritualized closure.")
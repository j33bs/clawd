#!/usr/bin/env python3
"""
Constraint-Aware Prompt Synthesis System
Generates prompts with explicit resource budgets (tokens, latency, model class) baked in
Forces the agent to reason about cost and fidelity simultaneously
"""

import json
import random
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import time


class ModelClass(Enum):
    """Categories of models with different capabilities and costs"""
    LIGHTWEIGHT = "lightweight"      # Fast, cheap, basic reasoning
    BALANCED = "balanced"            # Good balance of speed and capability
    REASONING = "reasoning"          # Advanced reasoning, moderate cost
    SPECIALIZED = "specialized"      # Specialized for specific tasks
    EXPENSIVE = "expensive"          # Most capable but expensive


@dataclass
class ResourceBudget:
    """Defines resource constraints for prompt generation"""
    max_tokens: int
    max_latency_ms: int
    model_class: ModelClass
    max_cost_cents: Optional[float] = None
    temperature: float = 0.7
    top_p: float = 0.9


@dataclass
class ConstraintAwarePrompt:
    """A prompt with built-in constraints and resource awareness"""
    original_task: str
    constrained_prompt: str
    resource_budget: ResourceBudget
    estimated_complexity: str  # 'low', 'medium', 'high', 'very_high'
    cost_estimate_cents: float
    expected_latency_ms: int
    fidelity_tradeoffs: List[str]


class PromptSynthesizer:
    """
    Synthesizes prompts with explicit resource constraints and cost-fidelity reasoning
    """
    
    def __init__(self):
        self.model_specs = {
            ModelClass.LIGHTWEIGHT: {
                'speed_tokens_per_sec': 100,
                'cost_per_1k_tokens': 0.05,  # cents
                'reasoning_power': 0.4,
                'max_context': 8000,
                'capabilities': ['simple_qa', 'text_summarization', 'basic_analysis']
            },
            ModelClass.BALANCED: {
                'speed_tokens_per_sec': 60,
                'cost_per_1k_tokens': 0.15,
                'reasoning_power': 0.6,
                'max_context': 16000,
                'capabilities': ['moderate_reasoning', 'analysis', 'generation', 'editing']
            },
            ModelClass.REASONING: {
                'speed_tokens_per_sec': 30,
                'cost_per_1k_tokens': 0.5,
                'reasoning_power': 0.8,
                'max_context': 32000,
                'capabilities': ['complex_reasoning', 'analysis', 'planning', 'strategy']
            },
            ModelClass.SPECIALIZED: {
                'speed_tokens_per_sec': 40,
                'cost_per_1k_tokens': 0.3,
                'reasoning_power': 0.7,
                'max_context': 16000,
                'capabilities': ['code_generation', 'mathematical', 'scientific', 'technical']
            },
            ModelClass.EXPENSIVE: {
                'speed_tokens_per_sec': 15,
                'cost_per_1k_tokens': 1.5,
                'reasoning_power': 0.95,
                'max_context': 128000,
                'capabilities': ['expert_reasoning', 'creative_work', 'complex_analysis']
            }
        }
        
        self.complexity_estimators = {
            'simple_qa': {'complexity': 'low', 'tokens': (50, 200)},
            'text_summarization': {'complexity': 'medium', 'tokens': (100, 500)},
            'basic_analysis': {'complexity': 'medium', 'tokens': (200, 800)},
            'moderate_reasoning': {'complexity': 'medium', 'tokens': (300, 1000)},
            'analysis': {'complexity': 'high', 'tokens': (500, 1500)},
            'generation': {'complexity': 'high', 'tokens': (400, 1200)},
            'editing': {'complexity': 'medium', 'tokens': (200, 600)},
            'complex_reasoning': {'complexity': 'very_high', 'tokens': (800, 2000)},
            'planning': {'complexity': 'high', 'tokens': (600, 1800)},
            'strategy': {'complexity': 'very_high', 'tokens': (1000, 2500)},
            'code_generation': {'complexity': 'high', 'tokens': (500, 1500)},
            'mathematical': {'complexity': 'high', 'tokens': (400, 1200)},
            'scientific': {'complexity': 'very_high', 'tokens': (800, 2000)},
            'technical': {'complexity': 'high', 'tokens': (600, 1800)},
            'expert_reasoning': {'complexity': 'very_high', 'tokens': (1000, 3000)},
            'creative_work': {'complexity': 'very_high', 'tokens': (800, 2500)},
            'complex_analysis': {'complexity': 'very_high', 'tokens': (1000, 2500)}
        }
    
    def estimate_task_complexity(self, task_description: str) -> Tuple[str, int]:
        """Estimate the complexity and token requirements for a task"""
        task_lower = task_description.lower()
        
        # Identify task type based on keywords
        for capability, specs in self.complexity_estimators.items():
            if any(keyword in task_lower for keyword in [
                capability.replace('_', ' '), 
                capability.split('_')[0] if '_' in capability else capability
            ]):
                complexity = specs['complexity']
                min_tokens, max_tokens = specs['tokens']
                estimated_tokens = random.randint(min_tokens, max_tokens)
                return complexity, estimated_tokens
        
        # Default estimation based on length and keywords
        length_based_complexity = 'low'
        if len(task_description) > 200:
            length_based_complexity = 'medium'
        if len(task_description) > 500:
            length_based_complexity = 'high'
        
        # Check for complexity indicators
        complexity_indicators = [
            'analyze', 'compare', 'evaluate', 'synthesize', 'plan', 
            'design', 'implement', 'research', 'investigate', 'strategize'
        ]
        
        indicator_count = sum(1 for indicator in complexity_indicators if indicator in task_lower)
        
        if indicator_count >= 3:
            length_based_complexity = 'very_high'
        elif indicator_count >= 2:
            length_based_complexity = 'high'
        elif indicator_count >= 1:
            length_based_complexity = 'medium'
        
        # Estimate tokens based on length and complexity
        base_tokens = max(100, len(task_description) // 3)
        complexity_multiplier = {
            'low': 1.0,
            'medium': 1.5,
            'high': 2.5,
            'very_high': 4.0
        }
        
        estimated_tokens = int(base_tokens * complexity_multiplier[length_based_complexity])
        
        return length_based_complexity, min(estimated_tokens, 4000)  # Cap at 4000 tokens
    
    def select_appropriate_model(self, budget: ResourceBudget, estimated_tokens: int) -> ModelClass:
        """Select the most appropriate model class based on budget and requirements"""
        # Calculate required performance based on tokens and latency
        required_speed = estimated_tokens / (budget.max_latency_ms / 1000)  # tokens per sec
        
        # Find models that meet the requirements
        suitable_models = []
        for model_class, specs in self.model_specs.items():
            # Check if model meets speed requirement
            meets_speed = specs['speed_tokens_per_sec'] >= required_speed * 0.8  # 80% tolerance
            # Check if model meets cost requirement if specified
            estimated_cost = (estimated_tokens / 1000) * specs['cost_per_1k_tokens']
            meets_cost = budget.max_cost_cents is None or estimated_cost <= budget.max_cost_cents
            # Check if model has enough context for the task
            meets_context = specs['max_context'] >= estimated_tokens * 2  # Need room for response
            
            if meets_speed and meets_cost and meets_context:
                suitable_models.append((model_class, specs['reasoning_power']))
        
        if not suitable_models:
            # If no model meets all requirements, select the best compromise
            # Prioritize by reasoning power and speed
            all_models = [(mc, s['reasoning_power']) for mc, s in self.model_specs.items()]
            suitable_models = sorted(all_models, key=lambda x: x[1], reverse=True)[:2]
        
        # Return the model with the highest reasoning power among suitable options
        if suitable_models:
            return sorted(suitable_models, key=lambda x: x[1], reverse=True)[0][0]
        
        # Fallback to balanced model
        return ModelClass.BALANCED
    
    def generate_constraint_aware_prompt(self, task: str, budget: ResourceBudget) -> ConstraintAwarePrompt:
        """Generate a prompt that respects the given resource budget"""
        # Estimate task complexity and token requirements
        estimated_complexity, estimated_tokens = self.estimate_task_complexity(task)
        
        # Select appropriate model
        selected_model = self.select_appropriate_model(budget, estimated_tokens)
        
        # Adjust budget based on selected model
        model_specs = self.model_specs[selected_model]
        adjusted_budget = ResourceBudget(
            max_tokens=min(budget.max_tokens, model_specs['max_context']),
            max_latency_ms=budget.max_latency_ms,
            model_class=selected_model,
            max_cost_cents=budget.max_cost_cents,
            temperature=budget.temperature,
            top_p=budget.top_p
        )
        
        # Calculate cost and latency estimates
        estimated_cost = (estimated_tokens / 1000) * model_specs['cost_per_1k_tokens']
        estimated_latency = (estimated_tokens / model_specs['speed_tokens_per_sec']) * 1000  # ms
        
        # Generate tradeoffs based on budget constraints
        tradeoffs = self._generate_fidelity_tradeoffs(task, budget, estimated_complexity)
        
        # Create the constrained prompt
        constrained_prompt = self._construct_constrained_prompt(task, budget, estimated_complexity)
        
        return ConstraintAwarePrompt(
            original_task=task,
            constrained_prompt=constrained_prompt,
            resource_budget=adjusted_budget,
            estimated_complexity=estimated_complexity,
            cost_estimate_cents=estimated_cost,
            expected_latency_ms=int(estimated_latency),
            fidelity_tradeoffs=tradeoffs
        )
    
    def _generate_fidelity_tradeoffs(self, task: str, budget: ResourceBudget, complexity: str) -> List[str]:
        """Generate a list of fidelity tradeoffs based on constraints"""
        tradeoffs = []
        
        # Cost vs. fidelity tradeoffs
        if budget.max_cost_cents and budget.max_cost_cents < 1.0:
            tradeoffs.append("Cost-constrained: Prioritizing efficiency over extensive analysis")
        
        if budget.max_cost_cents and budget.max_cost_cents > 5.0:
            tradeoffs.append("Budget-permissive: Can afford thorough analysis and verification")
        
        # Latency vs. fidelity tradeoffs
        if budget.max_latency_ms < 2000:  # Less than 2 seconds
            tradeoffs.append("Latency-critical: Providing concise response without deep exploration")
        
        if budget.max_latency_ms > 10000:  # More than 10 seconds
            tradeoffs.append("Latency-flexible: Can perform detailed analysis and multiple verification steps")
        
        # Token vs. fidelity tradeoffs
        if budget.max_tokens < 500:
            tradeoffs.append("Token-limited: Focusing on essential points only")
        
        if budget.max_tokens > 2000:
            tradeoffs.append("Token-rich: Can provide comprehensive coverage with examples")
        
        # Complexity-specific tradeoffs
        if complexity == 'very_high' and budget.max_cost_cents and budget.max_cost_cents < 2.0:
            tradeoffs.append("High complexity with low budget: Will provide high-level overview rather than detailed analysis")
        
        if complexity == 'low' and budget.max_tokens > 1000:
            tradeoffs.append("Simple task with high token budget: Can provide extensive detail if requested")
        
        return tradeoffs
    
    def _construct_constrained_prompt(self, task: str, budget: ResourceBudget, complexity: str) -> str:
        """Construct the actual prompt with constraints baked in"""
        # Start with the original task
        prompt_parts = [f"Task: {task}"]
        
        # Add resource constraints as instructions
        constraints = []
        
        if budget.max_tokens < 1000:
            constraints.append(f"RESPONSE LIMIT: Keep response under {budget.max_tokens} tokens")
        
        if budget.model_class == ModelClass.LIGHTWEIGHT:
            constraints.append("APPROACH: Use straightforward, direct reasoning")
        
        if budget.model_class == ModelClass.EXPENSIVE:
            constraints.append("APPROACH: Provide comprehensive, expert-level analysis")
        
        if complexity in ['high', 'very_high'] and budget.max_cost_cents and budget.max_cost_cents < 2.0:
            constraints.append("BUDGET CONSTRAINT: Provide high-level summary rather than detailed analysis")
        
        if budget.max_latency_ms < 3000:
            constraints.append("TIME CONSTRAINT: Respond quickly with essential information only")
        
        # Add cost awareness
        if budget.max_cost_cents:
            constraints.append(f"COST AWARENESS: This request has a budget of ${budget.max_cost_cents/100:.2f}")
        
        # Add the constraints to the prompt
        if constraints:
            prompt_parts.append("\nCONSTRAINTS AND INSTRUCTIONS:")
            for constraint in constraints:
                prompt_parts.append(f"- {constraint}")
        
        # Add quality guidance based on model class
        quality_guidance = self._get_quality_guidance(budget.model_class, complexity)
        if quality_guidance:
            prompt_parts.append(f"\nQUALITY GUIDANCE: {quality_guidance}")
        
        return "\n\n".join(prompt_parts)
    
    def _get_quality_guidance(self, model_class: ModelClass, complexity: str) -> str:
        """Get quality guidance based on model class and task complexity"""
        guidance_map = {
            ModelClass.LIGHTWEIGHT: {
                'low': "Provide clear, direct answers without elaboration",
                'medium': "Give concise explanations with key points only",
                'high': "Focus on main conclusions; skip detailed reasoning",
                'very_high': "Provide high-level summary; avoid deep analysis"
            },
            ModelClass.BALANCED: {
                'low': "Provide clear answers with brief explanations",
                'medium': "Include relevant details and reasoning",
                'high': "Provide thorough analysis with supporting points",
                'very_high': "Give comprehensive response with key insights"
            },
            ModelClass.REASONING: {
                'low': "Verify your reasoning is sound, then respond",
                'medium': "Apply systematic reasoning to ensure accuracy",
                'high': "Use multi-step reasoning with cross-validation",
                'very_high': "Apply rigorous analytical frameworks and verify conclusions"
            },
            ModelClass.EXPENSIVE: {
                'low': "Despite simplicity, apply expert-level rigor",
                'medium': "Provide authoritative, expert-level explanations",
                'high': "Deliver comprehensive expert analysis with multiple perspectives",
                'very_high': "Apply highest level of expertise with exhaustive analysis"
            }
        }
        
        class_guidance = guidance_map.get(model_class, {})
        return class_guidance.get(complexity, "Provide appropriate level of detail for the task")
    
    def optimize_prompt_for_budget(self, task: str, target_cost_cents: float, 
                                  target_latency_ms: int = 5000) -> ConstraintAwarePrompt:
        """Optimize a prompt for specific cost and latency targets"""
        # Start with conservative budget and increase until we find the sweet spot
        budget = ResourceBudget(
            max_tokens=500,
            max_latency_ms=target_latency_ms,
            model_class=ModelClass.BALANCED,
            max_cost_cents=target_cost_cents
        )
        
        return self.generate_constraint_aware_prompt(task, budget)


class ConstraintAwareAgent:
    """
    An agent that uses constraint-aware prompting by default
    """
    
    def __init__(self):
        self.synthesizer = PromptSynthesizer()
    
    def process_request(self, task: str, budget: ResourceBudget) -> Dict[str, Any]:
        """Process a request using constraint-aware prompting"""
        # Generate the constrained prompt
        constrained_prompt_obj = self.synthesizer.generate_constraint_aware_prompt(task, budget)
        
        # Simulate processing the prompt (in reality, this would call an LLM)
        simulated_response = self._simulate_llm_response(constrained_prompt_obj.constrained_prompt)
        
        return {
            'original_task': task,
            'constrained_prompt': constrained_prompt_obj.constrained_prompt,
            'response': simulated_response,
            'resource_utilization': {
                'used_tokens': min(budget.max_tokens, len(simulated_response.split())),
                'latency_ms': constrained_prompt_obj.expected_latency_ms,
                'estimated_cost_cents': constrained_prompt_obj.cost_estimate_cents
            },
            'budget_adherence': {
                'within_token_limit': len(simulated_response.split()) <= budget.max_tokens,
                'within_latency_limit': constrained_prompt_obj.expected_latency_ms <= budget.max_latency_ms,
                'within_cost_limit': (
                    budget.max_cost_cents is None or 
                    constrained_prompt_obj.cost_estimate_cents <= budget.max_cost_cents
                )
            },
            'fidelity_tradeoffs': constrained_prompt_obj.fidelity_tradeoffs
        }
    
    def _simulate_llm_response(self, prompt: str) -> str:
        """Simulate an LLM response based on the prompt constraints"""
        # This is a simulation - in practice, this would call an actual LLM
        if "COST AWARENESS" in prompt:
            return f"Simulated response to: {prompt.split('Task: ')[1].split('\n')[0]}. This response was generated with cost awareness and resource constraints in mind."
        else:
            return f"Simulated response to: {prompt.split('Task: ')[1].split('\n')[0]}. Standard response without explicit resource constraints."
    
    def suggest_optimal_budget(self, task: str) -> ResourceBudget:
        """Suggest an optimal budget based on task analysis"""
        complexity, estimated_tokens = self.synthesizer.estimate_task_complexity(task)
        
        # Set budget based on complexity
        complexity_budgets = {
            'low': ResourceBudget(
                max_tokens=500,
                max_latency_ms=2000,
                model_class=ModelClass.LIGHTWEIGHT,
                max_cost_cents=0.5
            ),
            'medium': ResourceBudget(
                max_tokens=1000,
                max_latency_ms=5000,
                model_class=ModelClass.BALANCED,
                max_cost_cents=1.0
            ),
            'high': ResourceBudget(
                max_tokens=2000,
                max_latency_ms=8000,
                model_class=ModelClass.REASONING,
                max_cost_cents=2.0
            ),
            'very_high': ResourceBudget(
                max_tokens=3000,
                max_latency_ms=15000,
                model_class=ModelClass.EXPENSIVE,
                max_cost_cents=5.0
            )
        }
        
        return complexity_budgets.get(complexity, complexity_budgets['medium'])


def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python constraint_prompt_synthesis.py <task_description>")
        sys.exit(1)
    
    task = " ".join(sys.argv[1:])
    
    synthesizer = PromptSynthesizer()
    
    # Test with different budgets
    budgets = [
        ResourceBudget(
            max_tokens=500,
            max_latency_ms=2000,
            model_class=ModelClass.LIGHTWEIGHT,
            max_cost_cents=0.5,
            temperature=0.3
        ),
        ResourceBudget(
            max_tokens=2000,
            max_latency_ms=10000,
            model_class=ModelClass.REASONING,
            max_cost_cents=2.0,
            temperature=0.7
        )
    ]
    
    print("Constraint-Aware Prompt Synthesis")
    print("=" * 50)
    
    for i, budget in enumerate(budgets, 1):
        print(f"\nBudget {i}: {budget.model_class.value} model, ${budget.max_cost_cents} budget")
        result = synthesizer.generate_constraint_aware_prompt(task, budget)
        
        print(f"Estimated Complexity: {result.estimated_complexity}")
        print(f"Cost Estimate: ${result.cost_estimate_cents/100:.2f}")
        print(f"Latency Estimate: {result.expected_latency_ms}ms")
        print(f"Fidelity Tradeoffs: {len(result.fidelity_tradeoffs)}")
        
        print(f"\nConstrained Prompt:")
        print("-" * 30)
        print(result.constrained_prompt)
        print("-" * 30)


if __name__ == "__main__":
    print("Constraint-Aware Prompt Synthesis System")
    print("=" * 60)
    
    agent = ConstraintAwareAgent()
    
    # Example tasks to demonstrate the system
    tasks = [
        "Summarize the key points of a 500-word article about climate change",
        "Analyze the security implications of a complex software architecture",
        "Create a detailed marketing strategy for a new tech product",
        "Solve this mathematical equation: 2x^2 + 5x - 3 = 0"
    ]
    
    print("Demonstrating constraint-aware prompting with various tasks:\n")
    
    for i, task in enumerate(tasks, 1):
        print(f"📝 Task {i}: {task}")
        
        # Create a conservative budget for this demonstration
        budget = ResourceBudget(
            max_tokens=1000,
            max_latency_ms=5000,
            model_class=ModelClass.BALANCED,
            max_cost_cents=1.0
        )
        
        # Process the request
        result = agent.process_request(task, budget)
        
        print(f"💰 Estimated Cost: ${result['resource_utilization']['estimated_cost_cents']/100:.2f}")
        print(f"⏱️  Estimated Latency: {result['resource_utilization']['latency_ms']}ms")
        print(f"📊 Budget Adherence: {result['budget_adherence']}")
        
        if result['fidelity_tradeoffs']:
            print(f"⚖️  Fidelity Tradeoffs:")
            for tradeoff in result['fidelity_tradeoffs']:
                print(f"   • {tradeoff}")
        
        print(f"✅ Response generated successfully\n")
    
    # Demonstrate optimal budget suggestion
    print("🎯 Optimal Budget Suggestion Example:")
    complex_task = "Design a comprehensive cybersecurity framework for a financial institution with multiple threat vectors and compliance requirements"
    
    optimal_budget = agent.suggest_optimal_budget(complex_task)
    print(f"For task: '{complex_task[:60]}...'")
    print(f"Suggested budget: {optimal_budget.model_class.value} model, ${optimal_budget.max_cost_cents}, {optimal_budget.max_tokens} tokens")
    
    # Generate and show the constraint-aware prompt for the complex task
    result = agent.process_request(complex_task, optimal_budget)
    print(f"Generated {len(result['fidelity_tradeoffs'])} fidelity tradeoffs for resource optimization")
    
    print(f"\n✨ The system successfully balances cost, latency, and capability requirements")
    print(f"🔄 Forces simultaneous reasoning about cost and fidelity")
    print(f"📊 Provides clear visibility into resource utilization")
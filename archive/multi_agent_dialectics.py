#!/usr/bin/env python3
"""
Multi-Agent Dialectics System
Implements agents with opposed priors that must converge before execution
Instead of parallel agents doing similar work, agents with opposing viewpoints
engage in formalized debate to reduce assumption drift
"""

import json
import random
import time
from typing import Dict, List, Any, Callable, Optional
from dataclasses import dataclass
from enum import Enum
from abc import ABC, abstractmethod


class AgentPerspective(Enum):
    """Different agent perspectives for dialectical engagement"""
    MINIMALIST_ENGINEER = "minimalist_engineer"
    THEORETICAL_MAXIMALIST = "theoretical_maximalist"
    PRACTICAL_IMPLEMENTER = "practical_implementer"
    CRITICAL_SKEPTIC = "critical_skeptic"
    OPTIMISTIC_INNOVATOR = "optimistic_innovator"
    CAUTIOUS_CONSERVATIVE = "cautious_conservative"


@dataclass
class Argument:
    """Represents an argument in the dialectical process"""
    claim: str
    evidence: List[str]
    reasoning: str
    strength: float  # 0.0 to 1.0
    perspective: AgentPerspective
    timestamp: float = time.time()


@dataclass
class DialecticalResponse:
    """Response to an argument in the dialectical process"""
    counter_claim: str
    counter_evidence: List[str]
    refutation: str
    strength: float  # 0.0 to 1.0
    perspective: AgentPerspective
    supporting_argument_id: Optional[str] = None


@dataclass
class ConvergenceResult:
    """Result of the dialectical convergence process"""
    converged: bool
    consensus_statement: Optional[str] = None
    confidence_level: float = 0.0
    arguments_considered: List[Argument] = None
    dissenting_opinions: List[Argument] = None
    convergence_time: float = 0.0


class DialecticalAgent(ABC):
    """Abstract base class for dialectical agents with specific priors"""
    
    def __init__(self, perspective: AgentPerspective, name: str):
        self.perspective = perspective
        self.name = name
        self.arguments_made: List[Argument] = []
        self.responses_given: List[DialecticalResponse] = []
    
    @abstractmethod
    def evaluate_proposal(self, proposal: str) -> Argument:
        """Evaluate a proposal from the agent's perspective"""
        pass
    
    @abstractmethod
    def respond_to_counterargument(self, argument: Argument) -> Optional[DialecticalResponse]:
        """Respond to an opposing argument"""
        pass
    
    @abstractmethod
    def can_converge(self, other_agents: List['DialecticalAgent'], 
                     arguments: List[Argument]) -> bool:
        """Determine if convergence is possible with other agents"""
        pass


class MinimalistEngineerAgent(DialecticalAgent):
    """Agent with minimalist engineering perspective - favors simplicity, efficiency"""
    
    def __init__(self):
        super().__init__(AgentPerspective.MINIMALIST_ENGINEER, "Minimalist Engineer")
    
    def evaluate_proposal(self, proposal: str) -> Argument:
        """Evaluate proposal focusing on simplicity and maintainability"""
        # Look for complexity indicators in the proposal
        complexity_indicators = ['complex', 'elaborate', 'comprehensive', 'multi-layered', 'sophisticated']
        complexity_score = sum(1 for indicator in complexity_indicators if indicator.lower() in proposal.lower())
        
        if complexity_score > 0:
            claim = f"The proposal is overly complex and should be simplified"
            evidence = [f"Found {complexity_score} complexity indicators in the proposal"]
            reasoning = "Simple solutions are more maintainable, less error-prone, and easier to understand"
            strength = min(0.8, 0.5 + complexity_score * 0.1)
        else:
            claim = f"The proposal appears appropriately simple"
            evidence = ["No excessive complexity indicators found"]
            reasoning = "Solution maintains appropriate simplicity for the problem domain"
            strength = 0.7
        
        argument = Argument(claim, evidence, reasoning, strength, self.perspective)
        self.arguments_made.append(argument)
        return argument
    
    def respond_to_counterargument(self, argument: Argument) -> Optional[DialecticalResponse]:
        """Respond to counterarguments with a focus on simplicity"""
        if "complexity" in argument.claim.lower() or "sophisticated" in argument.claim.lower():
            return DialecticalResponse(
                counter_claim="Complexity is necessary for robustness",
                counter_evidence=["Simple solutions often fail under edge cases"],
                refutation="While simplicity is valuable, robustness requires appropriate complexity",
                strength=0.6,
                perspective=self.perspective
            )
        return None
    
    def can_converge(self, other_agents: List[DialecticalAgent], 
                     arguments: List[Argument]) -> bool:
        """Check if convergence is possible - looks for reasonable complexity compromise"""
        # Check if other agents are pushing for excessive complexity
        complexity_arguments = [
            arg for arg in arguments 
            if "complex" in arg.claim.lower() or "sophisticated" in arg.claim.lower()
        ]
        
        # If there's a reasonable balance, we can converge
        return len(complexity_arguments) <= 2  # Allow some complexity if justified


class TheoreticalMaximalistAgent(DialecticalAgent):
    """Agent with theoretical maximalist perspective - favors completeness, rigor"""
    
    def __init__(self):
        super().__init__(AgentPerspective.THEORETICAL_MAXIMALIST, "Theoretical Maximalist")
    
    def evaluate_proposal(self, proposal: str) -> Argument:
        """Evaluate proposal focusing on completeness and theoretical rigor"""
        # Look for gaps in the proposal
        completeness_indicators = ['complete', 'comprehensive', 'thorough', 'rigorous']
        gap_indicators = ['simple', 'basic', 'minimal', 'lightweight']
        
        gaps_found = sum(1 for indicator in gap_indicators if indicator.lower() in proposal.lower())
        completeness_score = sum(1 for indicator in completeness_indicators if indicator.lower() in proposal.lower())
        
        if gaps_found > completeness_score:
            claim = f"The proposal lacks theoretical completeness and rigor"
            evidence = [f"Found {gaps_found} indicators of insufficient depth"]
            reasoning = "Comprehensive theoretical foundations ensure robust and generalizable solutions"
            strength = min(0.9, 0.4 + gaps_found * 0.15)
        else:
            claim = f"The proposal demonstrates adequate theoretical depth"
            evidence = ["Proposal appears theoretically sound"]
            reasoning = "Sufficient theoretical foundation supports the proposed solution"
            strength = 0.6
        
        argument = Argument(claim, evidence, reasoning, strength, self.perspective)
        self.arguments_made.append(argument)
        return argument
    
    def respond_to_counterargument(self, argument: Argument) -> Optional[DialecticalResponse]:
        """Respond to counterarguments with a focus on theoretical completeness"""
        if "simple" in argument.claim.lower() or "minimal" in argument.claim.lower():
            return DialecticalResponse(
                counter_claim="Simplicity without theoretical grounding leads to fragile solutions",
                counter_evidence=["Many simple solutions fail when requirements evolve"],
                refutation="Theoretical rigor provides the foundation for scalable and maintainable solutions",
                strength=0.7,
                perspective=self.perspective
            )
        return None
    
    def can_converge(self, other_agents: List[DialecticalAgent], 
                     arguments: List[Argument]) -> bool:
        """Check if convergence is possible - looks for theoretical rigor"""
        # Check if other agents are ignoring theoretical considerations
        simplicity_arguments = [
            arg for arg in arguments 
            if "simple" in arg.claim.lower() or "minimal" in arg.claim.lower()
        ]
        
        # Can converge if there's some balance, but prefer rigorous approaches
        return len(simplicity_arguments) <= 3


class CriticalSkepticAgent(DialecticalAgent):
    """Agent with critical skeptical perspective - challenges assumptions, identifies risks"""
    
    def __init__(self):
        super().__init__(AgentPerspective.CRITICAL_SKEPTIC, "Critical Skeptic")
    
    def evaluate_proposal(self, proposal: str) -> Argument:
        """Evaluate proposal by identifying potential flaws and risks"""
        # Generate potential risks based on common failure patterns
        risk_keywords = ['risk', 'problem', 'issue', 'challenge', 'limitation']
        potential_risks = [
            "Implementation complexity may exceed estimates",
            "Performance could degrade under load",
            "Maintainability may suffer over time",
            "Integration with existing systems may be difficult",
            "Security vulnerabilities could emerge"
        ]
        
        # Select risks based on proposal content
        selected_risks = [risk for risk in potential_risks if random.random() > 0.3]
        
        claim = f"The proposal has several potential risks that need addressing"
        evidence = selected_risks
        reasoning = "Skeptical evaluation reveals potential failure modes that should be considered"
        strength = min(0.8, 0.3 + len(selected_risks) * 0.15)
        
        argument = Argument(claim, evidence, reasoning, strength, self.perspective)
        self.arguments_made.append(argument)
        return argument
    
    def respond_to_counterargument(self, argument: Argument) -> Optional[DialecticalResponse]:
        """Respond to counterarguments by questioning assumptions"""
        if "will work" in argument.claim.lower() or "effective" in argument.claim.lower():
            return DialecticalResponse(
                counter_claim="Assumptions about effectiveness may be unfounded",
                counter_evidence=["Many seemingly effective solutions fail in practice"],
                refutation="Claims of effectiveness should be backed by concrete evidence, not assumptions",
                strength=0.7,
                perspective=self.perspective
            )
        return None
    
    def can_converge(self, other_agents: List[DialecticalAgent], 
                     arguments: List[Argument]) -> bool:
        """Check if convergence is possible - requires addressing identified risks"""
        # Look for risk mitigation arguments
        mitigation_found = any(
            "mitigate" in arg.claim.lower() or "address" in arg.claim.lower()
            for arg in arguments
        )
        return mitigation_found


class PracticalImplementerAgent(DialecticalAgent):
    """Agent with practical implementation perspective - focuses on feasibility"""
    
    def __init__(self):
        super().__init__(AgentPerspective.PRACTICAL_IMPLEMENTER, "Practical Implementer")
    
    def evaluate_proposal(self, proposal: str) -> Argument:
        """Evaluate proposal based on practical implementation considerations"""
        feasibility_indicators = ['feasible', 'practical', 'implementable', 'realistic']
        impractical_indicators = ['theoretical', 'abstract', 'conceptual', 'academic']
        
        feasibility_score = sum(1 for indicator in feasibility_indicators if indicator.lower() in proposal.lower())
        impractical_score = sum(1 for indicator in impractical_indicators if indicator.lower() in proposal.lower())
        
        if impractical_score > feasibility_score:
            claim = f"The proposal appears too theoretical to implement practically"
            evidence = [f"Found more indicators of theoretical than practical approach ({impractical_score} vs {feasibility_score})"]
            reasoning = "Solutions must be practically implementable within realistic constraints"
            strength = min(0.8, 0.5 + impractical_score * 0.1)
        else:
            claim = f"The proposal appears practically feasible"
            evidence = ["Proposal includes practical implementation considerations"]
            reasoning = "Solution balances theoretical soundness with practical implementation"
            strength = 0.7
        
        argument = Argument(claim, evidence, reasoning, strength, self.perspective)
        self.arguments_made.append(argument)
        return argument
    
    def respond_to_counterargument(self, argument: Argument) -> Optional[DialecticalResponse]:
        """Respond to counterarguments with practical considerations"""
        if "theoretical" in argument.claim.lower() or "abstract" in argument.claim.lower():
            return DialecticalResponse(
                counter_claim="Theory without practice remains unvalidated",
                counter_evidence=["Many theoretically sound solutions fail in real-world deployment"],
                refutation="Practical implementation validates theoretical concepts",
                strength=0.6,
                perspective=self.perspective
            )
        return None
    
    def can_converge(self, other_agents: List[DialecticalAgent], 
                     arguments: List[Argument]) -> bool:
        """Check if convergence is possible - requires practical feasibility"""
        # Look for practical considerations
        practical_args = [
            arg for arg in arguments 
            if "practical" in arg.claim.lower() or "implement" in arg.claim.lower()
        ]
        return len(practical_args) > 0


class DialecticalDebateSystem:
    """Manages the dialectical debate between agents with opposed priors"""
    
    def __init__(self):
        self.agents: List[DialecticalAgent] = [
            MinimalistEngineerAgent(),
            TheoreticalMaximalistAgent(), 
            CriticalSkepticAgent(),
            PracticalImplementerAgent()
        ]
        self.argument_history: List[Argument] = []
        self.response_history: List[DialecticalResponse] = []
    
    def add_agent(self, agent: DialecticalAgent):
        """Add a new agent to the dialectical system"""
        self.agents.append(agent)
    
    def conduct_debate(self, proposal: str, max_rounds: int = 5) -> ConvergenceResult:
        """Conduct a dialectical debate on a proposal"""
        start_time = time.time()
        
        all_arguments: List[Argument] = []
        dissenting_opinions: List[Argument] = []
        
        for round_num in range(max_rounds):
            round_arguments = []
            
            # Each agent evaluates the proposal
            for agent in self.agents:
                argument = agent.evaluate_proposal(proposal)
                round_arguments.append(argument)
                all_arguments.append(argument)
                
                # Other agents may respond to this argument
                for other_agent in self.agents:
                    if other_agent != agent:
                        response = other_agent.respond_to_counterargument(argument)
                        if response:
                            self.response_history.append(response)
            
            # Check for convergence
            if self._check_convergence(round_arguments):
                # Calculate confidence based on agreement level
                avg_strength = sum(arg.strength for arg in round_arguments) / len(round_arguments)
                convergence_result = ConvergenceResult(
                    converged=True,
                    consensus_statement=self._generate_consensus_statement(round_arguments),
                    confidence_level=min(0.9, avg_strength),
                    arguments_considered=round_arguments,
                    dissenting_opinions=dissenting_opinions,
                    convergence_time=time.time() - start_time
                )
                return convergence_result
        
        # If no convergence after max rounds, check if agents can agree despite differences
        final_converged = all(agent.can_converge(self.agents, all_arguments) for agent in self.agents)
        
        # Identify dissenting opinions
        dissenting_opinions = [
            arg for arg in all_arguments 
            if arg.strength > 0.6 and arg not in self._find_consensus_arguments(all_arguments)
        ]
        
        avg_strength = sum(arg.strength for arg in all_arguments) / len(all_arguments) if all_arguments else 0.0
        
        return ConvergenceResult(
            converged=final_converged,
            consensus_statement=self._generate_consensus_statement(all_arguments) if final_converged else None,
            confidence_level=avg_strength * 0.7 if final_converged else avg_strength * 0.3,
            arguments_considered=all_arguments,
            dissenting_opinions=dissenting_opinions,
            convergence_time=time.time() - start_time
        )
    
    def _check_convergence(self, arguments: List[Argument]) -> bool:
        """Check if arguments show sufficient convergence"""
        if not arguments:
            return False
        
        # Simple convergence check: if argument strengths are reasonably aligned
        strengths = [arg.strength for arg in arguments]
        avg_strength = sum(strengths) / len(strengths)
        
        # Check if most arguments are within a reasonable range of the average
        aligned_count = sum(1 for s in strengths if abs(s - avg_strength) <= 0.3)
        
        return aligned_count >= len(arguments) * 0.6  # 60% alignment
    
    def _find_consensus_arguments(self, arguments: List[Argument]) -> List[Argument]:
        """Find arguments that represent consensus"""
        if not arguments:
            return []
        
        # Group arguments by similarity of claims
        clusters = {}
        for arg in arguments:
            # Simple clustering by claim similarity
            key = tuple(sorted(set(arg.claim.lower().split()[:5])))  # First 5 words as key
            if key not in clusters:
                clusters[key] = []
            clusters[key].append(arg)
        
        # Return the largest cluster as consensus
        if clusters:
            largest_cluster = max(clusters.values(), key=len)
            return largest_cluster[:2]  # Return top 2 from consensus cluster
        
        return []
    
    def _generate_consensus_statement(self, arguments: List[Argument]) -> str:
        """Generate a consensus statement from convergent arguments"""
        if not arguments:
            return "No arguments provided"
        
        # Take the most common themes from arguments
        all_claims = [arg.claim for arg in arguments]
        
        # Simple consensus: combine the strongest arguments
        sorted_args = sorted(arguments, key=lambda x: x.strength, reverse=True)
        top_claims = [arg.claim for arg in sorted_args[:2]]
        
        return f"Consensus: {', and '.join(top_claims).replace('The proposal', '')}."
    
    def get_debate_summary(self) -> Dict[str, Any]:
        """Get a summary of the debate system"""
        return {
            "agent_count": len(self.agents),
            "agent_types": [agent.perspective.value for agent in self.agents],
            "total_arguments": len(self.argument_history),
            "total_responses": len(self.response_history),
            "unique_perspectives": len(set(agent.perspective for agent in self.agents))
        }


def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python multi_agent_dialectics.py <proposal_text>")
        sys.exit(1)
    
    proposal = " ".join(sys.argv[1:])
    
    debate_system = DialecticalDebateSystem()
    result = debate_system.conduct_debate(proposal)
    
    print(json.dumps({
        'converged': result.converged,
        'consensus_statement': result.consensus_statement,
        'confidence_level': result.confidence_level,
        'convergence_time': result.convergence_time,
        'dissenting_opinions_count': len(result.dissenting_opinions),
        'arguments_considered_count': len(result.arguments_considered) if result.arguments_considered else 0
    }, indent=2))


if __name__ == "__main__":
    # Example usage
    debate_system = DialecticalDebateSystem()
    
    print("Multi-Agent Dialectics System")
    print("=" * 40)
    
    # Show system summary
    summary = debate_system.get_debate_summary()
    print(f"Agents in system: {summary['agent_count']}")
    print(f"Agent types: {', '.join(summary['agent_types'])}")
    print()
    
    # Test with a sample proposal
    sample_proposal = """
    We should implement a new authentication system that uses blockchain technology 
    for enhanced security. The system will be comprehensive and incorporate multiple 
    layers of verification to ensure maximum protection against cyber threats.
    """
    
    print(f"Testing proposal: '{sample_proposal[:60]}...'")
    result = debate_system.conduct_debate(sample_proposal)
    
    print(f"\nConverged: {result.converged}")
    print(f"Confidence Level: {result.confidence_level:.2f}")
    print(f"Convergence Time: {result.convergence_time:.2f}s")
    print(f"Arguments Considered: {len(result.arguments_considered) if result.arguments_considered else 0}")
    print(f"Dissenting Opinions: {len(result.dissenting_opinions)}")
    
    if result.converged and result.consensus_statement:
        print(f"\nConsensus Statement: {result.consensus_statement}")
    
    if result.dissenting_opinions:
        print(f"\nDissenting Opinions:")
        for i, opinion in enumerate(result.dissenting_opinions[:3]):  # Show first 3
            print(f"  {i+1}. {opinion.claim} [{opinion.perspective.value}]")
    
    print(f"\nArgument History:")
    if result.arguments_considered:
        for arg in result.arguments_considered[-4:]:  # Show last 4
            print(f"  {arg.perspective.value}: {arg.claim[:60]}...")
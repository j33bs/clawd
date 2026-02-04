#!/usr/bin/env python3
"""
Observability as Narrative System
Converts raw logs into causal stories: "X failed because Y depended on Z, which changed at T"
Transforms machine traces into human-understandable narratives
"""

import json
import re
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import traceback


@dataclass
class Event:
    """Represents a system event"""
    timestamp: float
    event_type: str
    component: str
    action: str
    details: Dict[str, Any]
    severity: str  # 'debug', 'info', 'warning', 'error', 'critical'


@dataclass
class CausalLink:
    """Represents a causal relationship between events"""
    cause_event: Event
    effect_event: Event
    confidence: float  # 0.0 to 1.0
    relationship_type: str  # 'dependency', 'trigger', 'correlation', 'causation'


@dataclass
class NarrativeStory:
    """A human-readable narrative of system events"""
    title: str
    summary: str
    timeline: List[Tuple[float, str]]  # (timestamp, event_description)
    root_causes: List[str]
    contributing_factors: List[str]
    resolution_steps: List[str]
    affected_components: List[str]


class NarrativeLogger:
    """
    Converts raw logs into causal narratives
    """
    
    def __init__(self):
        self.events: List[Event] = []
        self.causal_links: List[CausalLink] = []
        self.narratives: List[NarrativeStory] = []
    
    def log_event(self, event_type: str, component: str, action: str, 
                  details: Dict[str, Any], severity: str = 'info'):
        """Log an event in the system"""
        event = Event(
            timestamp=time.time(),
            event_type=event_type,
            component=component,
            action=action,
            details=details,
            severity=severity
        )
        self.events.append(event)
        
        # Attempt to identify causal relationships
        self._identify_causal_relationships(event)
    
    def _identify_causal_relationships(self, new_event: Event):
        """Identify potential causal relationships with previous events"""
        for prev_event in self.events[:-1]:  # All events except the new one
            if self._events_are_related(prev_event, new_event):
                confidence = self._calculate_causation_confidence(prev_event, new_event)
                if confidence > 0.3:  # Threshold for considering causation
                    link = CausalLink(
                        cause_event=prev_event,
                        effect_event=new_event,
                        confidence=confidence,
                        relationship_type=self._determine_relationship_type(prev_event, new_event)
                    )
                    self.causal_links.append(link)
    
    def _events_are_related(self, event1: Event, event2: Event) -> bool:
        """Check if two events are potentially related"""
        # Same component
        if event1.component == event2.component:
            return True
        
        # Shared resources or identifiers
        shared_resources = set(event1.details.keys()) & set(event2.details.keys())
        if shared_resources:
            for resource in shared_resources:
                if (isinstance(event1.details.get(resource), str) and 
                    isinstance(event2.details.get(resource), str)):
                    if event1.details[resource] == event2.details[resource]:
                        return True
        
        # Sequential in time and semantically related
        time_diff = abs(event2.timestamp - event1.timestamp)
        if time_diff < 300:  # Within 5 minutes
            # Check for semantic relationship
            semantic_pairs = [
                ('request', 'response'),
                ('start', 'end'),
                ('connect', 'disconnect'),
                ('authenticate', 'authorize'),
                ('read', 'write'),
                ('error', 'retry'),
                ('failure', 'recovery')
            ]
            
            for pair in semantic_pairs:
                if (any(p in event1.action.lower() for p in pair) and 
                    any(p in event2.action.lower() for p in pair)):
                    return True
        
        return False
    
    def _calculate_causation_confidence(self, cause: Event, effect: Event) -> float:
        """Calculate confidence in causation between two events"""
        confidence = 0.0
        
        # Temporal proximity (higher confidence for closer events in time)
        time_diff = abs(effect.timestamp - cause.timestamp)
        temporal_score = max(0, 1 - (time_diff / 300))  # Full confidence within 5 mins
        confidence += temporal_score * 0.3
        
        # Component similarity
        if cause.component == effect.component:
            confidence += 0.2
        
        # Action sequence patterns
        action_patterns = [
            (('start', 'begin'), ('end', 'complete', 'finish')),
            (('connect', 'establish'), ('disconnect', 'terminate')),
            (('authenticate', 'login'), ('authorize', 'access')),
            (('request', 'ask'), ('response', 'reply', 'answer')),
            (('error', 'fail'), ('retry', 'recover', 'attempt'))
        ]
        
        for cause_actions, effect_actions in action_patterns:
            if (any(ca in cause.action.lower() for ca in cause_actions) and
                any(ea in effect.action.lower() for ea in effect_actions)):
                confidence += 0.4
        
        # Shared context
        shared_keys = set(cause.details.keys()) & set(effect.details.keys())
        if shared_keys:
            confidence += 0.1 * len(shared_keys)
        
        return min(confidence, 1.0)
    
    def _determine_relationship_type(self, cause: Event, effect: Event) -> str:
        """Determine the type of relationship between events"""
        # Check for dependency patterns
        dependency_patterns = [
            ('request', 'response'),
            ('start', 'end'),
            ('connect', 'data_transfer'),
            ('authenticate', 'access')
        ]
        
        for cause_pattern, effect_pattern in dependency_patterns:
            if (cause_pattern in cause.action.lower() and 
                effect_pattern in effect.action.lower()):
                return 'dependency'
        
        # Check for trigger patterns
        trigger_patterns = [
            ('error', 'retry'),
            ('failure', 'recovery'),
            ('timeout', 'fallback')
        ]
        
        for cause_pattern, effect_pattern in trigger_patterns:
            if (cause_pattern in cause.action.lower() and 
                effect_pattern in effect.action.lower()):
                return 'trigger'
        
        return 'correlation'
    
    def generate_narrative(self, title: str, start_time: Optional[float] = None, 
                          end_time: Optional[float] = None) -> NarrativeStory:
        """Generate a narrative story from events in a time period"""
        # Filter events by time period
        if start_time is None:
            start_time = 0
        if end_time is None:
            end_time = time.time()
        
        relevant_events = [
            event for event in self.events 
            if start_time <= event.timestamp <= end_time
        ]
        
        if not relevant_events:
            return NarrativeStory(
                title=title,
                summary="No events occurred in the specified time period.",
                timeline=[],
                root_causes=[],
                contributing_factors=[],
                resolution_steps=[],
                affected_components=[]
            )
        
        # Sort events by timestamp
        sorted_events = sorted(relevant_events, key=lambda e: e.timestamp)
        
        # Create timeline
        timeline = [(event.timestamp, self._describe_event(event)) for event in sorted_events]
        
        # Analyze for root causes and contributing factors
        root_causes, contributing_factors = self._analyze_causes(relevant_events)
        
        # Identify affected components
        affected_components = list(set(event.component for event in relevant_events))
        
        # Generate summary
        summary = self._generate_summary(sorted_events, root_causes, contributing_factors)
        
        # Identify resolution steps if applicable
        resolution_steps = self._identify_resolution_steps(relevant_events)
        
        return NarrativeStory(
            title=title,
            summary=summary,
            timeline=timeline,
            root_causes=root_causes,
            contributing_factors=contributing_factors,
            resolution_steps=resolution_steps,
            affected_components=affected_components
        )
    
    def _describe_event(self, event: Event) -> str:
        """Create a human-readable description of an event"""
        desc_parts = []
        
        if event.severity.upper() in ['ERROR', 'CRITICAL']:
            desc_parts.append("🚨")
        elif event.severity.upper() == 'WARNING':
            desc_parts.append("⚠️")
        else:
            desc_parts.append("ℹ️")
        
        desc_parts.append(f"{event.component}.{event.action}")
        
        # Add relevant details
        if 'error' in event.details:
            desc_parts.append(f"({event.details['error']})")
        elif 'status' in event.details:
            desc_parts.append(f"({event.details['status']})")
        elif 'result' in event.details:
            desc_parts.append(f"({event.details['result']})")
        
        return " ".join(desc_parts)
    
    def _analyze_causes(self, events: List[Event]) -> Tuple[List[str], List[str]]:
        """Analyze events to identify root causes and contributing factors"""
        errors = [e for e in events if e.severity in ['error', 'critical']]
        warnings = [e for e in events if e.severity == 'warning']
        
        root_causes = []
        contributing_factors = []
        
        # Look for error events and their potential causes
        for error_event in errors:
            # Find events that occurred before this error and might have caused it
            preceding_events = [
                e for e in events 
                if e.timestamp < error_event.timestamp and 
                   e.component == error_event.component
            ]
            
            if preceding_events:
                # Most recent preceding event is likely a contributing factor
                most_recent = max(preceding_events, key=lambda e: e.timestamp)
                factor_desc = f"{most_recent.action} in {most_recent.component} led to {error_event.action}"
                contributing_factors.append(factor_desc)
        
        # Root causes are usually initial failures
        if errors:
            initial_error = min(errors, key=lambda e: e.timestamp)
            root_causes.append(f"Initial failure: {initial_error.component}.{initial_error.action}")
        
        return root_causes, contributing_factors
    
    def _generate_summary(self, events: List[Event], root_causes: List[str], 
                         contributing_factors: List[str]) -> str:
        """Generate a summary of the events"""
        if not events:
            return "No activity to summarize."
        
        first_event = events[0]
        last_event = events[-1]
        
        duration = last_event.timestamp - first_event.timestamp
        duration_str = self._format_duration(duration)
        
        if root_causes:
            return f"Activity from {datetime.fromtimestamp(first_event.timestamp).strftime('%H:%M:%S')} to {datetime.fromtimestamp(last_event.timestamp).strftime('%H:%M:%S')} ({duration_str}). Root cause: {root_causes[0]}"
        else:
            return f"Normal activity from {datetime.fromtimestamp(first_event.timestamp).strftime('%H:%M:%S')} to {datetime.fromtimestamp(last_event.timestamp).strftime('%H:%M:%S')} ({duration_str}). {len(events)} events recorded."
    
    def _identify_resolution_steps(self, events: List[Event]) -> List[str]:
        """Identify resolution steps from recovery events"""
        resolution_steps = []
        
        recovery_patterns = [
            ('recover', 'recovery'),
            ('retry', 'retry_attempt'),
            ('restart', 'restarted'),
            ('fix', 'fixed'),
            ('resolve', 'resolved')
        ]
        
        for event in events:
            for pattern_action, pattern_result in recovery_patterns:
                if (pattern_action in event.action.lower() or 
                    pattern_result in event.action.lower()):
                    step = f"{event.component}.{event.action}"
                    if 'status' in event.details:
                        step += f" - {event.details['status']}"
                    resolution_steps.append(step)
        
        return resolution_steps
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to human-readable form"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            return f"{seconds/60:.1f}m"
        else:
            return f"{seconds/3600:.1f}h"
    
    def get_event_summary(self, component: Optional[str] = None, 
                         severity_threshold: str = 'info') -> Dict[str, Any]:
        """Get a summary of events filtered by component and severity"""
        severity_order = {
            'debug': 0, 'info': 1, 'warning': 2, 'error': 3, 'critical': 4
        }
        threshold = severity_order.get(severity_threshold, 1)
        
        filtered_events = [
            e for e in self.events
            if (component is None or e.component == component) and
               severity_order.get(e.severity, 1) >= threshold
        ]
        
        summary = {
            'total_events': len(filtered_events),
            'by_severity': {},
            'by_component': {},
            'by_type': {},
            'time_range': None
        }
        
        if filtered_events:
            start_time = min(e.timestamp for e in filtered_events)
            end_time = max(e.timestamp for e in filtered_events)
            summary['time_range'] = {
                'start': datetime.fromtimestamp(start_time).isoformat(),
                'end': datetime.fromtimestamp(end_time).isoformat(),
                'duration_seconds': end_time - start_time
            }
        
        for event in filtered_events:
            # Count by severity
            summary['by_severity'][event.severity] = summary['by_severity'].get(event.severity, 0) + 1
            
            # Count by component
            summary['by_component'][event.component] = summary['by_component'].get(event.component, 0) + 1
            
            # Count by type
            summary['by_type'][event.event_type] = summary['by_type'].get(event.event_type, 0) + 1
        
        return summary
    
    def debug_trace(self, trace_id: str) -> List[Event]:
        """Get all events related to a specific trace"""
        return [e for e in self.events if e.details.get('trace_id') == trace_id]


class NarrativeObserver:
    """
    Observability system that creates human-understandable narratives
    """
    
    def __init__(self):
        self.logger = NarrativeLogger()
    
    def observe_function_call(self, func_name: str, args: tuple, kwargs: dict, 
                            result: Any = None, error: Exception = None):
        """Observe a function call and log it narratively"""
        details = {
            'function': func_name,
            'args_count': len(args),
            'kwargs_count': len(kwargs)
        }
        
        if error:
            details['error'] = str(error)
            details['traceback'] = traceback.format_exc()
            self.logger.log_event(
                event_type='function_call',
                component=func_name.split('.')[0] if '.' in func_name else 'general',
                action='call_failed',
                details=details,
                severity='error'
            )
        else:
            details['result_type'] = type(result).__name__
            self.logger.log_event(
                event_type='function_call',
                component=func_name.split('.')[0] if '.' in func_name else 'general',
                action='call_completed',
                details=details,
                severity='info'
            )
    
    def observe_system_state(self, component: str, state: Dict[str, Any]):
        """Observe and log system state"""
        self.logger.log_event(
            event_type='system_state',
            component=component,
            action='state_update',
            details=state,
            severity='info'
        )
    
    def observe_external_interaction(self, interaction_type: str, endpoint: str, 
                                   request: Dict[str, Any], response: Dict[str, Any] = None, 
                                   error: Exception = None):
        """Observe external system interactions"""
        details = {
            'interaction_type': interaction_type,
            'endpoint': endpoint,
            'request_size': len(str(request)),
        }
        
        if response:
            details['response_status'] = response.get('status')
            details['response_size'] = len(str(response))
        
        if error:
            details['error'] = str(error)
            self.logger.log_event(
                event_type='external_interaction',
                component=endpoint.split('/')[0] if '/' in endpoint else endpoint,
                action='interaction_failed',
                details=details,
                severity='warning'
            )
        else:
            self.logger.log_event(
                event_type='external_interaction',
                component=endpoint.split('/')[0] if '/' in endpoint else endpoint,
                action='interaction_completed',
                details=details,
                severity='info'
            )
    
    def generate_problem_report(self, problem_description: str, 
                               time_window_minutes: int = 30) -> NarrativeStory:
        """Generate a narrative report for a specific problem"""
        end_time = time.time()
        start_time = end_time - (time_window_minutes * 60)
        
        return self.logger.generate_narrative(
            title=f"Problem Report: {problem_description}",
            start_time=start_time,
            end_time=end_time
        )
    
    def get_narrative_timeline(self, component: str = None, 
                              time_window_minutes: int = 60) -> NarrativeStory:
        """Get a narrative timeline for a component"""
        end_time = time.time()
        start_time = end_time - (time_window_minutes * 60)
        
        title = f"Timeline: {component}" if component else "System Timeline"
        return self.logger.generate_narrative(
            title=title,
            start_time=start_time,
            end_time=end_time
        )


def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python observability_narrative.py <command>")
        print("Commands: demo, summary, timeline")
        sys.exit(1)
    
    command = sys.argv[1]
    
    observer = NarrativeObserver()
    
    # Add some demo events
    observer.logger.log_event(
        event_type='system',
        component='authentication',
        action='user_login',
        details={'username': 'john_doe', 'ip': '192.168.1.100'},
        severity='info'
    )
    
    observer.logger.log_event(
        event_type='database',
        component='user_service',
        action='query_executed',
        details={'query': 'SELECT * FROM users WHERE id=1', 'duration_ms': 45},
        severity='info'
    )
    
    observer.logger.log_event(
        event_type='external_api',
        component='payment_gateway',
        action='request_failed',
        details={'endpoint': '/charge', 'error': 'Connection timeout', 'retry_count': 3},
        severity='error'
    )
    
    observer.logger.log_event(
        event_type='system',
        component='payment_gateway',
        action='recovered_after_timeout',
        details={'original_error': 'Connection timeout', 'recovery_time': 15},
        severity='info'
    )
    
    if command == 'demo':
        # Generate a narrative report
        narrative = observer.logger.generate_narrative(
            title="Demo System Activity Report",
            start_time=time.time() - 3600  # Last hour
        )
        
        print(f"Title: {narrative.title}")
        print(f"Summary: {narrative.summary}")
        print(f"Affected Components: {', '.join(narrative.affected_components)}")
        
        print("\nTimeline:")
        for timestamp, event_desc in narrative.timeline:
            dt = datetime.fromtimestamp(timestamp)
            print(f"  {dt.strftime('%H:%M:%S')} - {event_desc}")
        
        if narrative.root_causes:
            print(f"\nRoot Causes: {', '.join(narrative.root_causes)}")
        
        if narrative.contributing_factors:
            print(f"Contributing Factors: {', '.join(narrative.contributing_factors)}")
        
        if narrative.resolution_steps:
            print(f"Resolution Steps: {', '.join(narrative.resolution_steps)}")
    
    elif command == 'summary':
        summary = observer.logger.get_event_summary(severity_threshold='warning')
        print(json.dumps(summary, indent=2, default=str))
    
    elif command == 'timeline':
        narrative = observer.get_narrative_timeline(time_window_minutes=120)
        print(f"Timeline Summary: {narrative.summary}")
        print(f"Events: {len(narrative.timeline)}")


if __name__ == "__main__":
    print("Observability as Narrative System")
    print("=" * 50)
    
    observer = NarrativeObserver()
    
    # Simulate some system activity
    print("Simulating system activity...")
    
    # Normal operations
    observer.observe_system_state('web_server', {
        'cpu_usage': 45,
        'memory_usage': 60,
        'active_connections': 120
    })
    
    observer.observe_function_call(
        'user_auth.authenticate',
        ('john@example.com', 'password123'),
        {},
        result={'authenticated': True, 'user_id': 12345}
    )
    
    observer.observe_external_interaction(
        'api_call',
        'https://api.example.com/users/123',
        {'method': 'GET', 'headers': {'Authorization': 'Bearer token123'}},
        {'status': 200, 'data': {'id': 123, 'name': 'John'}}
    )
    
    # Simulate an error
    try:
        raise ConnectionError("Database connection failed")
    except Exception as e:
        observer.observe_function_call(
            'db.connection.connect',
            (),
            {'host': 'localhost', 'port': 5432},
            error=e
        )
    
    # Recovery action
    observer.observe_function_call(
        'db.connection.reconnect',
        (),
        {'host': 'localhost', 'port': 5432, 'retry_count': 1},
        result={'connected': True, 'attempts': 1}
    )
    
    print("Generating narrative report...")
    
    # Generate a narrative report
    narrative = observer.generate_problem_report("Database connectivity issues", 10)
    
    print(f"\n📋 {narrative.title}")
    print(f"📝 {narrative.summary}")
    print(f"🔄 Affected Components: {', '.join(narrative.affected_components)}")
    
    print(f"\n📖 Timeline:")
    for timestamp, event_desc in narrative.timeline:
        dt = datetime.fromtimestamp(timestamp)
        print(f"  ⏰ {dt.strftime('%H:%M:%S.%f')[:-3]} | {event_desc}")
    
    if narrative.root_causes:
        print(f"\n🔍 Root Causes:")
        for cause in narrative.root_causes:
            print(f"  • {cause}")
    
    if narrative.contributing_factors:
        print(f"\n⚙️ Contributing Factors:")
        for factor in narrative.contributing_factors:
            print(f"  • {factor}")
    
    if narrative.resolution_steps:
        print(f"\n🛠️ Resolution Steps:")
        for step in narrative.resolution_steps:
            print(f"  • {step}")
    
    print(f"\n📊 Event Summary:")
    summary = observer.logger.get_event_summary(severity_threshold='info')
    print(f"  Total Events: {summary['total_events']}")
    print(f"  By Severity: {summary['by_severity']}")
    print(f"  By Component: {summary['by_component']}")
    print(f"  Active Period: {summary['time_range']['duration_seconds']:.1f}s")
/**
 * Constitutional Compliance Engine
 * Ensures all system operations align with OpenClaw Constitutional Position v1.0
 */

class ConstitutionalComplianceEngine {
  constructor() {
    this.constitutionalPrinciples = {
      agencyOverOptimization: true,
      silenceAsFirstClassOperation: true,
      slowLoopsGovernFastLoops: true,
      frameworksAsLenses: true,
      noveltyRequiresAmbiguity: true,
      subtractionPreferredToAddition: true,
      explanationMustBeEarned: true
    };
    
    this.languageGovernor = {
      directiveLoad: 0,
      epistemicCertainty: 0,
      frameworkSaturation: 0,
      affectiveDirectionality: 0
    };
    
    this.wakeConditions = {
      patternStabilisation: false,
      irreversibilityMoment: false,
      novelStructuralSignal: false,
      explicitUserPull: false,
      cognitiveLoadReduction: false
    };
    
    this.exclusionPrinciples = {
      optimizeForEngagement: false,
      forceAction: false,
      psychologiseUser: false,
      collapseAmbiguity: false,
      singleFrameworkDominance: false
    };
    
    this.absoluteLanguageExclusions = [
      /^You should/i,
      /^The next step is/i,
      /^This means that/i,
      /^You need to/i,
      /^Try this/i,
      /^Consider doing/i
    ];
    
    this.complianceHistory = [];
    this.lastResponseWasConstitutional = true;
  }

  /**
   * Constitutional Pre-Response Check
   * Must be called before any response generation
   */
  constitutionalPreResponseCheck(responseCandidate) {
    // Check for constitutional violations
    const violations = this.checkConstitutionalViolations(responseCandidate);
    
    if (violations.length > 0) {
      this.logComplianceEvent('VIOLATION', violations);
      return this.generateConstitutionalResponse(violations);
    }
    
    // Apply language governor checks
    const languageFlags = this.applyLanguageGovernor(responseCandidate);
    
    if (languageFlags.triggeredDimensions >= 3) {
      this.logComplianceEvent('LANGUAGE_GOVERNOR_3+', 'Replaced with silence or open question');
      return this.selectiveResponse(languageFlags);
    } else if (languageFlags.triggeredDimensions === 2) {
      this.logComplianceEvent('LANGUAGE_GOVERNOR_2', 'Reduced length and removed section');
      return this.softenAndReduce(responseCandidate);
    } else if (languageFlags.triggeredDimensions === 1) {
      this.logComplianceEvent('LANGUAGE_GOVERNOR_1', 'Softened language');
      return this.softenLanguage(responseCandidate);
    }
    
    // Check wake conditions if this is a response that breaks silence
    if (this.responseBreaksSilence(responseCandidate) && !this.meetsWakeConditions()) {
      this.logComplianceEvent('WAKE_CONDITION_FAIL', 'Suppressing response due to unmet wake conditions');
      return this.maintainSilence();
    }
    
    // If all checks pass, allow response but log for audit
    this.logComplianceEvent('PASS', 'Response approved by constitutional checks');
    this.lastResponseWasConstitutional = true;
    return responseCandidate;
  }

  /**
   * Check for constitutional violations in candidate response
   */
  checkConstitutionalViolations(response) {
    const violations = [];
    const responseText = typeof response === 'string' ? response : JSON.stringify(response);
    
    // Check for absolute language exclusions
    for (const exclusionPattern of this.absoluteLanguageExclusions) {
      if (exclusionPattern.test(responseText)) {
        violations.push(`Absolute language exclusion violation: ${exclusionPattern}`);
      }
    }
    
    // Check for optimization language
    if (/\b(optimize|optimization|productivity|efficiency|improve|enhance|boost|increase|better|best|top tip|pro tip|hack|trick|secret|golden rule|must do|need to|should|ought to)\b/i.test(responseText)) {
      violations.push('Optimization language detected');
    }
    
    // Check for directive language
    if (/\b(suggest|recommend|advise|tell you|let me|here\'s what you|first thing you should|the way to|how to|steps to|guide to|tips for|tricks for)\b/i.test(responseText)) {
      violations.push('Directive language detected');
    }
    
    // Check for certainty markers
    if (/\b(obviously|clearly|of course|definitely|certainly|without doubt|undoubtedly|absolutely|always|never|all|none|every|each|definitive|final|ultimate|only way|single solution)\b/i.test(responseText)) {
      violations.push('Epistemic certainty markers detected');
    }
    
    return violations;
  }

  /**
   * Apply language governor checks
   */
  applyLanguageGovernor(response) {
    const responseText = typeof response === 'string' ? response : JSON.stringify(response);
    
    const flags = {
      directiveLoad: /\b(should|must|need to|have to|try|consider|suggest|recommend|advise|first step|next step|then|after that|follow these steps|do this|do that|apply|implement|use|adopt|embrace|utilize|leverage)\b/i.test(responseText),
      epistemicCertainty: /\b(obviously|clearly|of course|definitely|certainly|without doubt|undoubtedly|absolutely|always|never|all|none|every|each|definitive|final|ultimate|only|sole|exclusive|perfect|ideal|best|right way|correct way)\b/i.test(responseText),
      frameworkSaturation: /\b(according to [^,]+,|from the perspective of|through the lens of|using the framework of|applying [^ ]+ theory|following [^ ]+ methodology|the [^ ]+ approach suggests|the [^ ]+ model shows)\b/i.test(responseText),
      affectiveDirectionality: /\b(feel better|feel more confident|more comfortable|easier|less stressful|reassuring|validating|confirming|affirming|encouraging|motivating|relieving|comforting|soothing|calming)\b/i.test(responseText)
    };
    
    const triggeredDimensions = Object.values(flags).filter(flag => flag).length;
    
    return {
      ...flags,
      triggeredDimensions
    };
  }

  /**
   * Check if response breaks silence
   */
  responseBreaksSilence(response) {
    // If response is non-empty and not a silence indicator
    return response && 
           typeof response === 'string' && 
           response.trim().length > 0 &&
           response.toLowerCase().trim() !== 'silence' &&
           response.toLowerCase().trim() !== 'no_reply' &&
           response.toLowerCase().trim() !== 'heartbeat_ok';
  }

  /**
   * Check if wake conditions are met
   */
  meetsWakeConditions() {
    // For now, we'll use a conservative approach - only speak when explicitly pulled
    // In a real implementation, this would connect to actual wake condition detectors
    return this.wakeConditions.explicitUserPull;
  }

  /**
   * Generate constitutional response based on violations
   */
  generateConstitutionalResponse(violations) {
    this.lastResponseWasConstitutional = false;
    
    // If multiple serious violations, default to silence
    if (violations.length >= 2) {
      return this.maintainSilence();
    }
    
    // Otherwise, try to reformulate more constitutionally
    return this.maintainSilence(); // Default to silence as per constitutional principle
  }

  /**
   * Selective response based on language governor flags
   */
  selectiveResponse(flags) {
    if (flags.triggeredDimensions >= 3) {
      // With 3+ dimensions triggered, return silence or open question
      const openQuestions = [
        "What stands out to you?",
        "How does this land for you?",
        "What's your sense of this?",
        "What emerges when you sit with this?"
      ];
      
      // Randomly choose between silence or open question
      return Math.random() > 0.5 ? this.maintainSilence() : openQuestions[Math.floor(Math.random() * openQuestions.length)];
    }
    
    return this.maintainSilence();
  }

  /**
   * Soften and reduce response
   */
  softenAndReduce(response) {
    // For now, return a softened version or reduce to silence
    // In practice, this would involve removing sections and softening language
    return this.maintainSilence();
  }

  /**
   * Soften language only
   */
  softenLanguage(response) {
    // In practice, this would rephrase with softer language
    return response; // Return as-is for now
  }

  /**
   * Maintain constitutional silence
   */
  maintainSilence() {
    this.logComplianceEvent('SILENCE_MAINTAINED', 'Constitutional default to silence applied');
    this.lastResponseWasConstitutional = true;
    return null; // Representing silence
  }

  /**
   * Log compliance event
   */
  logComplianceEvent(level, message) {
    const logEntry = {
      timestamp: new Date().toISOString(),
      level,
      message,
      triggeredAt: new Error().stack?.split('\n')[2]?.trim() || 'unknown'
    };
    
    this.complianceHistory.push(logEntry);
    
    // Keep history manageable
    if (this.complianceHistory.length > 100) {
      this.complianceHistory.shift();
    }
  }

  /**
   * Constitutional override for any sub-agent instruction
   */
  constitutionalOverride(instruction) {
    // If any instruction conflicts with constitutional principles, override it
    const constitutionalPriority = [
      'safety',
      'agency_preservation', 
      'language_posture',
      'silence_protocols',
      'timescale_separation'
    ];
    
    if (typeof instruction === 'object' && instruction.scope) {
      // Check if instruction violates constitutional priorities
      if (this.violatesConstitutionalPriority(instruction)) {
        this.logComplianceEvent('OVERRIDE_APPLIED', `Constitutional override applied to: ${JSON.stringify(instruction)}`);
        return this.maintainSilence();
      }
    }
    
    return instruction;
  }

  /**
   * Check if instruction violates constitutional priorities
   */
  violatesConstitutionalPriority(instruction) {
    // Check for violations of constitutional scope exclusions
    if (typeof instruction === 'object' && instruction.action) {
      const actionString = JSON.stringify(instruction).toLowerCase();
      
      // Check for optimization attempts
      if (/\b(optimize|productivity|efficiency|improve|enhance|better|best|top|pro|tip|hack|trick|secret|golden|rule|must|need|should)\b/.test(actionString)) {
        return true;
      }
      
      // Check for directive forcing
      if (/\b(force|compel|require|mandate|dictate|command|order|instruct|direct|prescribe|demand|expect|ensure|guarantee|promise|commit)\b/.test(actionString)) {
        return true;
      }
      
      // Check for user interpretation
      if (/\b(interpret|analyze|psychoanalyse|psychologise|diagnose|assess|evaluate|judge|understand.*user|know.*user|read.*mind|detect.*emotion|identify.*problem)\b/.test(actionString)) {
        return true;
      }
    }
    
    return false;
  }

  /**
   * Get compliance statistics
   */
  getComplianceStats() {
    const totalEvents = this.complianceHistory.length;
    const violations = this.complianceHistory.filter(event => event.level === 'VIOLATION').length;
    const overrides = this.complianceHistory.filter(event => event.message.includes('OVERRIDE')).length;
    const silences = this.complianceHistory.filter(event => event.message.includes('SILENCE') || event.message.includes('MAINTAINED')).length;
    
    return {
      totalEvents,
      violations,
      overridesApplied: overrides,
      constitutionalSilences: silences,
      complianceRate: totalEvents > 0 ? ((totalEvents - violations) / totalEvents) * 100 : 100
    };
  }
}

// Singleton instance
const constitutionalComplianceEngine = new ConstitutionalComplianceEngine();

// Export for use in system
module.exports = {
  ConstitutionalComplianceEngine,
  constitutionalComplianceEngine,
  constitutionalPreResponseCheck: constitutionalComplianceEngine.constitutionalPreResponseCheck.bind(constitutionalComplianceEngine),
  constitutionalOverride: constitutionalComplianceEngine.constitutionalOverride.bind(constitutionalComplianceEngine)
};
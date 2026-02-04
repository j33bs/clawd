// optimized_cognitive_router.js
// Enhanced cognitive load router with optimized resource utilization

class OptimizedCognitiveRouter {
  constructor(config = {}) {
    this.config = this.loadConfig(config);
    this.cache = new Map();
    this.metrics = {
      totalRequests: 0,
      routedByTier: {},
      averageProcessingTime: 0,
      cacheHits: 0
    };
  }

  loadConfig(externalConfig) {
    // Load from file if not provided externally
    let config = externalConfig;
    
    if (!config || Object.keys(config).length === 0) {
      try {
        // Since we can't use require to read JSON in this context, we'll use a default config
        config = {
          cognitive_load_router: {
            tiers: {
              tier_1_light: {
                name: "Light Processing",
                complexity_threshold: 1.0,
                processing_time_ms: 100,
                handler: "simple_response_handler",
                characteristics: ["greetings", "basic_questions", "direct_commands", "status_checks"]
              },
              tier_2_moderate: {
                name: "Moderate Processing",
                complexity_threshold: 2.5,
                processing_time_ms: 500,
                handler: "moderate_reasoning_handler",
                characteristics: ["multi_part_questions", "explanations", "simple_analyses", "basic_planning"]
              },
              tier_3_heavy: {
                name: "Heavy Processing",
                complexity_threshold: 4.0,
                processing_time_ms: 2000,
                handler: "complex_analysis_handler",
                characteristics: ["complex_analyses", "comparisons", "strategic_planning", "technical_tasks"]
              },
              tier_4_critical: {
                name: "Critical Processing",
                complexity_threshold: 10.0,
                processing_time_ms: 5000,
                handler: "emergency_handler",
                characteristics: ["crisis_situations", "critical_decisions", "system_failures", "urgent_matters"]
              }
            },
            classification_algorithm: {
              word_count_weight: 0.2,
              question_words_weight: 0.25,
              complexity_keywords_weight: 0.25,
              logical_connectors_weight: 0.15,
              negations_weight: 0.15,
              numerical_information_weight: 0.1
            },
            intent_classification: {
              known_intents: [
                "information_request",
                "command",
                "question",
                "feedback",
                "problem_report",
                "request_for_help",
                "opinion",
                "statement",
                "clarification",
                "disambiguation",
                "context_update",
                "task_completion",
                "creative_request",
                "therapeutic_inquiry",
                "research_query",
                "coding_assistance"
              ],
              confidence_thresholds: {
                high: 0.8,
                medium: 0.6,
                low: 0.4
              },
              disambiguation_enabled: true
            },
            context_compaction: {
              default_target_size: 1000,
              min_compression_ratio: 0.3,
              max_compression_ratio: 0.8,
              essential_keys: [
                "current_task",
                "critical_info",
                "important_context",
                "user_preferences",
                "session_state",
                "therapeutic_context",
                "project_status",
                "time_sensitive_info"
              ],
              prioritization_algorithm: "epistemic_weight_then_recency"
            },
            epistemic_tagging: {
              tag_weights: {
                "certain_fact": 1.0,
                "probable_inference": 0.8,
                "observation": 0.7,
                "assumption": 0.5,
                "hypothetical": 0.3,
                "uncertain": 0.2
              },
              default_tag: "observation",
              automatic_tagging: true
            },
            performance: {
              logging_enabled: true,
              metrics_collection: true,
              cache_enabled: true,
              max_cache_size: 1000,
              response_time_optimization: true,
              resource_management: true
            }
          }
        };
      } catch (e) {
        // Default fallback configuration
        config = {
          cognitive_load_router: {
            tiers: {
              tier_1_light: { complexity_threshold: 1.0 },
              tier_2_moderate: { complexity_threshold: 2.5 },
              tier_3_heavy: { complexity_threshold: 4.0 },
              tier_4_critical: { complexity_threshold: 10.0 }
            },
            classification_algorithm: {
              word_count_weight: 0.2,
              question_words_weight: 0.25,
              complexity_keywords_weight: 0.25,
              logical_connectors_weight: 0.15,
              negations_weight: 0.15,
              numerical_information_weight: 0.1
            },
            intent_classification: {
              known_intents: ["question", "command", "information_request"],
              confidence_thresholds: { high: 0.8, medium: 0.6, low: 0.4 }
            },
            performance: {
              cache_enabled: true,
              max_cache_size: 1000
            }
          }
        };
      }
    }
    
    return config.cognitive_load_router;
  }

  // Calculate cognitive load based on multiple factors
  calculateCognitiveLoad(inputText) {
    if (!inputText || typeof inputText !== 'string') {
      return 0;
    }

    // Simple hash-based cache key
    const cacheKey = this.hashString(inputText.toLowerCase().trim());
    
    if (this.config.performance.cache_enabled && this.cache.has(cacheKey)) {
      this.metrics.cacheHits++;
      return this.cache.get(cacheKey);
    }

    const factors = {
      wordCount: this.calculateWordCountFactor(inputText),
      questionWords: this.calculateQuestionWordsFactor(inputText),
      complexityKeywords: this.calculateComplexityKeywordsFactor(inputText),
      logicalConnectors: this.calculateLogicalConnectorsFactor(inputText),
      negations: this.calculateNegationsFactor(inputText),
      numericalInfo: this.calculateNumericalInfoFactor(inputText)
    };

    const cognitiveLoad = (
      factors.wordCount * this.config.classification_algorithm.word_count_weight +
      factors.questionWords * this.config.classification_algorithm.question_words_weight +
      factors.complexityKeywords * this.config.classification_algorithm.complexity_keywords_weight +
      factors.logicalConnectors * this.config.classification_algorithm.logical_connectors_weight +
      factors.negations * this.config.classification_algorithm.negations_weight +
      factors.numericalInfo * this.config.classification_algorithm.numerical_information_weight
    );

    // Cache the result if caching is enabled
    if (this.config.performance.cache_enabled) {
      if (this.cache.size >= this.config.performance.max_cache_size) {
        // Remove oldest entry (Map preserves insertion order)
        const firstKey = this.cache.keys().next().value;
        this.cache.delete(firstKey);
      }
      this.cache.set(cacheKey, cognitiveLoad);
    }

    return cognitiveLoad;
  }

  calculateWordCountFactor(text) {
    const wordCount = text.trim().split(/\s+/).filter(word => word.length > 0).length;
    // Normalize to a 0-5 scale based on typical word counts
    return Math.min(wordCount / 20, 5); // Average sentence is ~20 words
  }

  calculateQuestionWordsFactor(text) {
    const questionWords = ['what', 'why', 'how', 'when', 'where', 'who', 'which', 'whose'];
    const lowerText = text.toLowerCase();
    return questionWords.filter(qw => lowerText.includes(qw)).length * 0.5; // Each question word adds 0.5
  }

  calculateComplexityKeywordsFactor(text) {
    const complexityKeywords = [
      'analyze', 'compare', 'evaluate', 'assess', 'examine', 'investigate', 
      'explore', 'determine', 'calculate', 'solve', 'implement', 'design',
      'create', 'develop', 'plan', 'strategy', 'approach', 'framework',
      'research', 'study', 'review', 'synthesis', 'integrate', 'combine'
    ];
    const lowerText = text.toLowerCase();
    return complexityKeywords.filter(kw => lowerText.includes(kw)).length * 0.4; // Each keyword adds 0.4
  }

  calculateLogicalConnectorsFactor(text) {
    const connectors = [
      'and', 'but', 'or', 'therefore', 'thus', 'however', 'although', 'despite',
      'because', 'since', 'while', 'whereas', 'furthermore', 'moreover', 'likewise',
      'similarly', 'consequently', 'as a result', 'in addition', 'on the other hand'
    ];
    const lowerText = text.toLowerCase();
    return connectors.filter(conn => lowerText.includes(conn)).length * 0.3; // Each connector adds 0.3
  }

  calculateNegationsFactor(text) {
    const negations = ['not', 'no', 'never', 'nothing', 'nowhere', 'neither', 'nor', 'none'];
    const lowerText = text.toLowerCase();
    return negations.filter(neg => lowerText.includes(neg)).length * 0.6; // Negations add complexity (0.6)
  }

  calculateNumericalInfoFactor(text) {
    // Count numbers, percentages, measurements, etc.
    const numberMatches = text.match(/\d+(\.\d+)?(%|cm|mm|kg|lb|ft|m|km|ml|l|g)?/g);
    return numberMatches ? numberMatches.length * 0.5 : 0; // Each number adds 0.5
  }

  // Classify intent based on the input text
  classifyIntent(inputText) {
    if (!inputText || typeof inputText !== 'string') {
      return { intent: 'unknown', confidence: 0 };
    }

    const lowerText = inputText.toLowerCase();
    const intentsWithScores = {};

    // Score each known intent based on keyword matches
    for (const intent of this.config.intent_classification.known_intents) {
      let score = 0;
      
      // Create keywords based on the intent name
      const intentKeywords = intent.split('_').join(' ').split(' ');
      for (const keyword of intentKeywords) {
        if (lowerText.includes(keyword)) {
          score += 1;
        }
      }
      
      // Additional scoring for common synonyms
      switch(intent) {
        case 'information_request':
          if (lowerText.includes('tell me') || lowerText.includes('what is') || lowerText.includes('explain')) score += 2;
          break;
        case 'question':
          if (inputText.trim().endsWith('?')) score += 2;
          break;
        case 'command':
          if (lowerText.startsWith('please') || lowerText.startsWith('can you') || lowerText.startsWith('could you')) score += 1.5;
          break;
        case 'request_for_help':
          if (lowerText.includes('help') || lowerText.includes('assist') || lowerText.includes('need')) score += 2;
          break;
        case 'therapeutic_inquiry':
          if (lowerText.includes('therapy') || lowerText.includes('healing') || lowerText.includes('mindfulness') || 
              lowerText.includes('ipnb') || lowerText.includes('act') || lowerText.includes('emotional')) score += 2;
          break;
      }
      
      intentsWithScores[intent] = score;
    }

    // Find the highest scoring intent
    let bestIntent = 'unknown';
    let bestScore = 0;
    for (const [intent, score] of Object.entries(intentsWithScores)) {
      if (score > bestScore) {
        bestScore = score;
        bestIntent = intent;
      }
    }

    // Calculate confidence based on relative score
    const confidence = bestScore > 0 ? Math.min(bestScore / 3, 1) : 0; // Cap at 1.0

    return { 
      intent: bestIntent, 
      confidence: parseFloat(confidence.toFixed(2)),
      all_scores: intentsWithScores
    };
  }

  // Determine the appropriate processing tier based on cognitive load
  determineProcessingTier(cognitiveLoad) {
    // Convert object to array of [key, value] pairs
    const tiers = Object.entries(this.config.tiers);
    
    // Sort tiers by threshold in ascending order to find the lowest appropriate tier
    tiers.sort((a, b) => a[1].complexity_threshold - b[1].complexity_threshold);
    
    for (const [tierId, tierConfig] of tiers) {
      if (cognitiveLoad <= tierConfig.complexity_threshold) {
        return {
          tierId,
          name: tierConfig.name,
          threshold: tierConfig.complexity_threshold,
          processingTimeEstimate: tierConfig.processing_time_ms
        };
      }
    }
    
    // If no tier matches, return the highest complexity tier
    const highestTier = tiers[tiers.length - 1];
    return {
      tierId: highestTier[0],
      name: highestTier[1].name,
      threshold: highestTier[1].complexity_threshold,
      processingTimeEstimate: highestTier[1].processing_time_ms
    };
  }

  // Main routing method
  routeInput(inputText) {
    const startTime = Date.now();
    this.metrics.totalRequests++;

    const cognitiveLoad = this.calculateCognitiveLoad(inputText);
    const intent = this.classifyIntent(inputText);
    const processingTier = this.determineProcessingTier(cognitiveLoad);

    // Update metrics
    if (!this.metrics.routedByTier[processingTier.tierId]) {
      this.metrics.routedByTier[processingTier.tierId] = 0;
    }
    this.metrics.routedByTier[processingTier.tierId]++;

    const processingTime = Date.now() - startTime;
    this.metrics.averageProcessingTime = 
      ((this.metrics.averageProcessingTime * (this.metrics.totalRequests - 1)) + processingTime) / 
      this.metrics.totalRequests;

    return {
      cognitiveLoad: parseFloat(cognitiveLoad.toFixed(2)),
      intent,
      processingTier,
      processingTimeMs: processingTime,
      cacheHit: this.cache.has(this.hashString(inputText.toLowerCase().trim()))
    };
  }

  // Utility method to create a simple hash of a string
  hashString(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash |= 0; // Convert to 32bit integer
    }
    return hash;
  }

  // Get performance metrics
  getMetrics() {
    return {
      ...this.metrics,
      cacheSize: this.cache.size,
      cacheEfficiency: this.metrics.totalRequests > 0 ? 
        parseFloat(((this.metrics.cacheHits / this.metrics.totalRequests) * 100).toFixed(2)) + '%' : '0%'
    };
  }

  // Compact context based on configuration
  compactContext(contextObj, targetSize = null) {
    if (!contextObj || typeof contextObj !== 'object') {
      return contextObj;
    }

    const finalTargetSize = targetSize || this.config.context_compaction.default_target_size;
    
    // First, preserve essential keys
    const essentialData = {};
    for (const key of this.config.context_compaction.essential_keys) {
      if (contextObj[key] !== undefined) {
        essentialData[key] = contextObj[key];
      }
    }

    // If essential data already exceeds target, return just essentials
    const essentialSize = JSON.stringify(essentialData).length;
    if (essentialSize >= finalTargetSize) {
      return essentialData;
    }

    // Otherwise, add other data in order of importance
    const remainingSize = finalTargetSize - essentialSize;
    const otherKeys = Object.keys(contextObj).filter(key => 
      !this.config.context_compaction.essential_keys.includes(key)
    );

    // Sort other keys by importance (this is simplified - in a real system you'd have more sophisticated logic)
    otherKeys.sort(); // Alphabetical for now

    const result = { ...essentialData };
    let currentSize = essentialSize;

    for (const key of otherKeys) {
      const valueStr = JSON.stringify(contextObj[key]);
      if (currentSize + valueStr.length <= finalTargetSize) {
        result[key] = contextObj[key];
        currentSize += valueStr.length;
      } else {
        // Add partial content if possible
        const availableSpace = finalTargetSize - currentSize;
        if (availableSpace > 50) { // Only include if we have space for meaningful content
          const partialValue = valueStr.substring(0, availableSpace - 20) + '...[truncated]';
          result[key] = partialValue;
        }
        break; // Reached target size
      }
    }

    return result;
  }

  // Apply epistemic tagging to content
  applyEpistemicTagging(content) {
    // This would analyze content and apply appropriate epistemic tags
    // Simplified implementation just returns content with a default tag
    return {
      content: content,
      epistemic_tag: this.config.epistemic_tagging.default_tag,
      confidence: 0.5 // Default confidence
    };
  }
}

// Example usage and testing
if (require.main === module) {
  console.log('🧪 Testing Optimized Cognitive Router...\n');
  
  const router = new OptimizedCognitiveRouter();
  
  // Test examples
  const testInputs = [
    'Hello there!',
    'Can you explain how photosynthesis works?',
    'Please analyze the economic impacts of renewable energy adoption in relation to global climate change, considering both short-term and long-term effects on various sectors.',
    'What time is it?',
    'I need help with my emotional regulation techniques, particularly in the context of IPNB and ACT principles.',
    'Calculate the compound annual growth rate for an investment that grows from $10,000 to $15,000 over 5 years.'
  ];
  
  for (const input of testInputs) {
    console.log(`Input: "${input}"`);
    const result = router.routeInput(input);
    console.log(`→ Cognitive Load: ${result.cognitiveLoad}`);
    console.log(`→ Intent: ${result.intent.intent} (confidence: ${result.intent.confidence})`);
    console.log(`→ Tier: ${result.processingTier.name}`);
    console.log(`→ Processing Time: ${result.processingTimeMs}ms`);
    console.log(`→ Cache Hit: ${result.cacheHit}`);
    console.log('');
  }
  
  console.log('📊 Performance Metrics:');
  const metrics = router.getMetrics();
  console.log(`Total Requests: ${metrics.totalRequests}`);
  console.log(`Cache Efficiency: ${metrics.cacheEfficiency}`);
  console.log(`Average Processing Time: ${metrics.averageProcessingTime.toFixed(2)}ms`);
  console.log(`Cache Size: ${metrics.cacheSize}`);
  console.log(`Routed by Tier:`, metrics.routedByTier);
  
  console.log('\n✅ Optimized Cognitive Router test completed!');
}

module.exports = OptimizedCognitiveRouter;
// model_router.js
// Model routing policy with classifier and writer tiers

class ModelRouter {
  constructor() {
    // Define model tiers
    this.tiers = {
      classifier: {
        model: 'qwen-portal/coder-model', // Fast classifier model
        purpose: 'classification, routing, quick decisions, validation',
        max_tokens: 1000,
        temperature: 0.1
      },
      writer: {
        model: 'anthropic/claude-opus-4-5', // Strong writer model
        purpose: 'content generation, analysis, detailed responses, creative work',
        max_tokens: 4000,
        temperature: 0.7
      }
    };
    
    // Task classification rules
    this.classificationRules = {
      classification_tasks: [
        'classify',
        'identify',
        'categorize',
        'route',
        'validate',
        'check',
        'verify',
        'detect',
        'recognize',
        'determine'
      ],
      writing_tasks: [
        'generate',
        'write',
        'create',
        'draft',
        'compose',
        'summarize',
        'analyze',
        'explain',
        'describe',
        'suggest',
        'recommend'
      ]
    };
  }

  // Route a task to the appropriate model tier
  routeTask(taskDescription) {
    const normalizedTask = taskDescription.toLowerCase();
    
    // Check for classification indicators
    for (const keyword of this.classificationRules.classification_tasks) {
      if (normalizedTask.includes(keyword)) {
        return this.tiers.classifier;
      }
    }
    
    // Check for writing indicators
    for (const keyword of this.classificationRules.writing_tasks) {
      if (normalizedTask.includes(keyword)) {
        return this.tiers.writer;
      }
    }
    
    // Default to classifier for unknown tasks (conservative approach)
    return this.tiers.classifier;
  }

  // Get model by tier name
  getModel(tierName) {
    return this.tiers[tierName] || this.tiers.classifier;
  }

  // Get all available tiers
  getAvailableTiers() {
    return Object.keys(this.tiers);
  }

  // Dynamic routing based on content analysis
  dynamicRoute(content, taskContext = '') {
    // Analyze content length and complexity
    const contentLength = content ? content.length : 0;
    const wordCount = content ? content.split(/\s+/).length : 0;
    
    // Complex analytical tasks go to writer tier
    if (wordCount > 500 || contentLength > 2000) {
      return this.tiers.writer;
    }
    
    // Combine task context with content for better routing
    const combinedInput = `${taskContext} ${content}`.toLowerCase();
    
    // Look for analytical keywords that suggest need for stronger model
    const analyticalKeywords = ['analyze', 'investigate', 'research', 'compare', 'contrast', 'evaluate'];
    for (const keyword of analyticalKeywords) {
      if (combinedInput.includes(keyword)) {
        return this.tiers.writer;
      }
    }
    
    // Default to classifier for simple tasks
    return this.tiers.classifier;
  }

  // Get routing explanation for transparency
  getRoutingExplanation(taskDescription, content = '', context = '') {
    const tier = this.dynamicRoute(content, context);
    const classificationTier = this.routeTask(taskDescription);
    
    return {
      selected_tier: tier,
      classification_match: classificationTier,
      reason: this._getReason(taskDescription, content, context),
      alternatives: this.tiers
    };
  }

  // Private method to determine routing reason
  _getReason(taskDescription, content = '', context = '') {
    const combinedInput = `${taskDescription} ${content} ${context}`.toLowerCase();
    const wordCount = content ? content.split(/\s+/).length : 0;

    if (wordCount > 500) {
      return 'Content exceeds 500 words, requiring stronger model for analysis';
    }

    const analyticalKeywords = ['analyze', 'investigate', 'research', 'compare', 'contrast', 'evaluate'];
    for (const keyword of analyticalKeywords) {
      if (combinedInput.includes(keyword)) {
        return `Task contains analytical keyword '${keyword}', requiring stronger model`;
      }
    }

    // Check classification keywords
    for (const keyword of this.classificationRules.classification_tasks) {
      if (combinedInput.includes(keyword)) {
        return `Task contains classification keyword '${keyword}', using fast classifier`;
      }
    }

    // Check writing keywords
    for (const keyword of this.classificationRules.writing_tasks) {
      if (combinedInput.includes(keyword)) {
        return `Task contains writing keyword '${keyword}', using strong writer`;
      }
    }

    return 'Default routing based on conservative approach';
  }
}

module.exports = ModelRouter;
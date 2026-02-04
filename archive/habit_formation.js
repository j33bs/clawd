// habit_formation.js
// Atomic Habits-inspired habit formation system for integrating new habits

class HabitFormationSystem {
  constructor() {
    this.habitDatabasePath = './memory/habits.json';
    this.initHabitDatabase();
  }

  // Initialize habit database
  initHabitDatabase() {
    const fs = require('fs');
    if (!fs.existsSync(this.habitDatabasePath)) {
      const initialDb = {
        habits: [],
        habitStreaks: {},
        habitHistory: {},
        settings: {
          defaultIdentityFocus: 'Who is the person I want to become?',
          habitStackingEnabled: true,
          habitScaling: 'tinyHabitsFirst' // tinyHabitsFirst, gradualIncrease, immediateFullImplementation
        }
      };
      fs.writeFileSync(this.habitDatabasePath, JSON.stringify(initialDb, null, 2));
    }
  }

  // Get habit database
  getHabitDatabase() {
    const fs = require('fs');
    return JSON.parse(fs.readFileSync(this.habitDatabasePath, 'utf8'));
  }

  // Update habit database
  updateHabitDatabase(updates) {
    const db = this.getHabitDatabase();
    Object.assign(db, updates);
    const fs = require('fs');
    fs.writeFileSync(this.habitDatabasePath, JSON.stringify(db, null, 2));
  }

  // Create a new habit following Atomic Habits principles
  createHabit(habitDefinition) {
    const db = this.getHabitDatabase();
    
    // Apply Atomic Habits principles
    const atomicHabit = {
      id: `habit_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`,
      name: habitDefinition.name,
      description: habitDefinition.description,
      atomicPrinciples: {
        // 1% Better Every Day
        marginalGains: habitDefinition.marginalGains || 0.01,
        // Habit Stacking
        habitStack: habitDefinition.habitStack || null, // e.g., "after I [current_habit], I will [new_habit]"
        // Implementation Intentions
        implementationIntentions: habitDefinition.implementationIntentions || [], // "if X happens, then I will Y"
        // Identity-Based Habit Change
        identityConnection: habitDefinition.identityConnection || "", // "I am the type of person who..."
      },
      // Core habit mechanics
      cue: habitDefinition.cue, // The trigger
      craving: habitDefinition.craving, // The motivation
      response: habitDefinition.response, // The habit itself
      reward: habitDefinition.reward, // The benefit
      // Tracking
      frequency: habitDefinition.frequency || 'daily',
      duration: habitDefinition.duration || 'ongoing',
      startDate: new Date().toISOString(),
      status: 'planning', // planning, active, paused, completed
      // Atomic Habits strategy
      strategy: habitDefinition.strategy || 'habitStacking', // habitStacking, temptationBundling, environmentDesign, etc.
      // Tiny Habits approach
      tinyVersion: habitDefinition.tinyVersion || this.createTinyVersion(habitDefinition.name),
      // Measurement
      measurement: habitDefinition.measurement || 'binary', // binary, count, time, rating
      // Environment design
      environmentChanges: habitDefinition.environmentChanges || [],
      // Habit contract (commitment device)
      commitmentDevice: habitDefinition.commitmentDevice || null
    };

    db.habits.push(atomicHabit);
    this.updateHabitDatabase(db);
    
    return atomicHabit;
  }

  // Create a tiny version of a habit (from Tiny Habits methodology)
  createTinyVersion(habitName) {
    // Convert larger habits to tiny, achievable versions
    const tinyMappings = {
      'meditate': 'meditate for 1 minute',
      'exercise': 'do 2 push-ups',
      'read': 'read 1 page',
      'write': 'write 1 sentence',
      'stretch': 'stretch for 30 seconds',
      'plan': 'plan for 2 minutes',
      'reflect': 'reflect for 1 minute',
      'organize': 'organize 1 item',
      'learn': 'learn 1 new fact',
      'practice': 'practice for 2 minutes'
    };

    for (const [key, tinyVersion] of Object.entries(tinyMappings)) {
      if (habitName.toLowerCase().includes(key)) {
        return tinyVersion;
      }
    }

    // Default tiny version
    return `do a tiny bit of ${habitName}`;
  }

  // Start a habit (move from planning to active)
  startHabit(habitId) {
    const db = this.getHabitDatabase();
    const habit = db.habits.find(h => h.id === habitId);
    
    if (habit) {
      habit.status = 'active';
      habit.startDate = new Date().toISOString();
      
      // Initialize tracking
      if (!db.habitStreaks[habitId]) {
        db.habitStreaks[habitId] = {
          currentStreak: 0,
          longestStreak: 0,
          completionDates: [],
          lastCompletion: null
        };
      }
      
      this.updateHabitDatabase(db);
      return habit;
    }
    
    return null;
  }

  // Complete a habit (mark as done for the day)
  completeHabit(habitId) {
    const db = this.getHabitDatabase();
    const habit = db.habits.find(h => h.id === habitId);
    const streakInfo = db.habitStreaks[habitId];
    
    if (!habit || !streakInfo) {
      return { success: false, error: 'Habit not found' };
    }

    const today = new Date().toISOString().split('T')[0];
    const lastCompletion = streakInfo.lastCompletion ? 
      new Date(streakInfo.lastCompletion).toISOString().split('T')[0] : null;

    // Update streak
    if (lastCompletion === today) {
      // Already completed today
      return { 
        success: true, 
        message: 'Habit already completed today',
        streak: streakInfo.currentStreak 
      };
    } else if (lastCompletion === new Date(Date.now() - 86400000).toISOString().split('T')[0]) {
      // Completed yesterday, continuing streak
      streakInfo.currentStreak += 1;
    } else if (lastCompletion !== null) {
      // Broken streak, reset to 1
      streakInfo.currentStreak = 1;
    } else {
      // First completion
      streakInfo.currentStreak = 1;
    }

    // Update records
    streakInfo.lastCompletion = new Date().toISOString();
    streakInfo.completionDates.push(new Date().toISOString());
    
    if (streakInfo.currentStreak > streakInfo.longestStreak) {
      streakInfo.longestStreak = streakInfo.currentStreak;
    }

    this.updateHabitDatabase(db);
    
    return {
      success: true,
      message: `Habit completed! Current streak: ${streakInfo.currentStreak} days`,
      streak: streakInfo.currentStreak,
      longestStreak: streakInfo.longestStreak
    };
  }

  // Get habit progress
  getHabitProgress(habitId) {
    const db = this.getHabitDatabase();
    const habit = db.habits.find(h => h.id === habitId);
    const streakInfo = db.habitStreaks[habitId];

    if (!habit || !streakInfo) {
      return null;
    }

    return {
      habit: habit,
      streak: streakInfo.currentStreak,
      longestStreak: streakInfo.longestStreak,
      completionRate: this.calculateCompletionRate(streakInfo),
      consistency: this.calculateConsistency(streakInfo)
    };
  }

  // Calculate completion rate
  calculateCompletionRate(streakInfo) {
    if (streakInfo.completionDates.length === 0) return 0;
    
    // For simplicity, calculating based on last 30 days
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
    
    const recentCompletions = streakInfo.completionDates.filter(
      date => new Date(date) > thirtyDaysAgo
    );
    
    return recentCompletions.length / 30; // Simplified calculation
  }

  // Calculate consistency
  calculateConsistency(streakInfo) {
    // Consistency is a combination of streak length and recent completion rate
    if (streakInfo.currentStreak === 0) return 0;
    
    const recentRate = this.calculateCompletionRate(streakInfo);
    return (streakInfo.currentStreak * 0.6) + (recentRate * 100 * 0.4);
  }

  // Get all habits
  getAllHabits() {
    const db = this.getHabitDatabase();
    return db.habits.map(habit => {
      const progress = this.getHabitProgress(habit.id);
      return {
        ...habit,
        progress: progress || null
      };
    });
  }

  // Apply Atomic Habits principles to existing improvement
  applyAtomicPrinciplesToImprovement(improvementId, habitData) {
    const improvementSystem = require('./self_improvement');
    const improvementLogPath = './memory/improvement_log.json';
    const fs = require('fs');
    
    let improvementLog = JSON.parse(fs.readFileSync(improvementLogPath, 'utf8'));
    const improvement = improvementLog.improvements.find(i => i.id === improvementId);
    
    if (!improvement) {
      return { success: false, error: 'Improvement not found' };
    }

    // Add Atomic Habits transformation to the improvement
    improvement.atomicTransformation = {
      tinyHabitVersion: habitData.tinyVersion || this.createTinyVersion(improvement.title),
      habitStack: habitData.habitStack,
      implementationIntentions: habitData.implementationIntentions || [],
      identityConnection: habitData.identityConnection || `I am the type of person who continuously improves through ${improvement.category}`,
      environmentalCues: habitData.environmentalCues || [],
      measurementStrategy: habitData.measurement || 'simpleTracking',
      streakTracking: true
    };

    fs.writeFileSync(improvementLogPath, JSON.stringify(improvementLog, null, 2));
    
    return {
      success: true,
      message: `Atomic Habits principles applied to improvement: ${improvement.title}`,
      transformedImprovement: improvement
    };
  }

  // Apply CBP (Cognitive Behavioral Play) principles to habit formation
  applyCBPPrinciples(habitId, cbpOptions = {}) {
    const fs = require('fs');
    const db = this.getHabitDatabase();
    const habit = db.habits.find(h => h.id === habitId);
    
    if (!habit) {
      return { success: false, error: 'Habit not found' };
    }

    // CBP principles integration
    const cbpIntegration = {
      playfulElements: cbpOptions.playfulElements || this.getDefaultPlayfulElements(habit.name),
      cognitiveRestructuring: cbpOptions.cognitiveRestructuring || this.getDefaultCognitiveFrames(habit.name),
      behavioralExperiments: cbpOptions.behavioralExperiments || this.getDefaultBehavioralExperiments(habit.name),
      gamification: cbpOptions.gamification || this.getDefaultGamification(habit.name),
      creativeExpression: cbpOptions.creativeExpression || this.getDefaultCreativeOutlets(habit.name),
      emotionalProcessing: cbpOptions.emotionalProcessing || this.getDefaultEmotionalConnections(habit.name)
    };

    // Add CBP integration to the habit
    habit.cbpIntegration = cbpIntegration;
    
    this.updateHabitDatabase(db);
    
    return {
      success: true,
      message: `CBP principles applied to habit: ${habit.name}`,
      cbpEnhancedHabit: habit
    };
  }

  // Get default playful elements for a habit
  getDefaultPlayfulElements(habitName) {
    const playfulElements = {
      'time-blocking': [
        'Use colorful calendar blocks like building blocks',
        'Turn schedule conflicts into "puzzle solving" challenges',
        'Celebrate time-block completions with small rewards',
        'Make transitions between blocks into "scene changes"'
      ],
      'meditation': [
        'Imagine mind as a playground with different activity zones',
        'Visualize thoughts as clouds passing through sky',
        'Use meditation apps with playful interfaces',
        'Try meditation in different playful environments'
      ],
      'exercise': [
        'Turn workouts into adventure games',
        'Use exercise apps with game-like features',
        'Create friendly competition with yourself',
        'Try movement forms that feel playful'
      ],
      'creative': [
        'Approach creative time as experimental play',
        'Use "what if" scenarios during creative blocks',
        'Try creative exercises without judgment',
        'Make creative time feel exploratory rather than productive'
      ],
      'organization': [
        'Turn organization into sorting games',
        'Use timers to create playful urgency',
        'Reward organization with fun activities',
        'Make organization feel like creative arranging'
      ]
    };

    // Find matching category
    for (const [category, elements] of Object.entries(playfulElements)) {
      if (habitName.toLowerCase().includes(category)) {
        return elements;
      }
    }

    // Default playful elements
    return [
      'Approach habit as an experiment rather than obligation',
      'Use light-hearted self-talk about the habit',
      'Allow for mistakes and treat them as learning',
      'Make habit tracking feel like a fun activity'
    ];
  }

  // Get default cognitive restructuring frames
  getDefaultCognitiveFrames(habitName) {
    const cognitiveFrames = {
      'time-blocking': [
        'Time-blocking gives me freedom by reducing decision fatigue',
        'Scheduling time for creative work increases rather than restricts creativity',
        'Time boundaries protect my energy for important work',
        'Structured time allows for more spontaneous creative moments'
      ],
      'meditation': [
        'My mind wandering is part of the practice, not a failure',
        'Even 1 minute of mindfulness is beneficial',
        'Meditation is training, not performing',
        'Every meditation session teaches me something about my mind'
      ],
      'exercise': [
        'Movement is a gift to my body, not punishment',
        'Progress is non-linear and that\'s normal',
        'Exercise is about feeling good, not looking a certain way',
        'My body is capable and deserves movement'
      ],
      'creative': [
        'Creative blocks are normal parts of the process',
        'Finished is better than perfect',
        'Experimentation is more important than results',
        'Creative time is investment, not luxury'
      ]
    };

    // Find matching category
    for (const [category, frames] of Object.entries(cognitiveFrames)) {
      if (habitName.toLowerCase().includes(category)) {
        return frames;
      }
    }

    // Default cognitive frames
    return [
      'This habit is an investment in who I want to become',
      'Small actions compound over time into significant changes',
      'Progress, not perfection, is the goal',
      'This habit serves my larger life purpose'
    ];
  }

  // Get default behavioral experiments
  getDefaultBehavioralExperiments(habitName) {
    const behavioralExperiments = {
      'time-blocking': [
        'Test: Blocking time for creative work increases rather than decreases creative output',
        'Experiment: See if having scheduled breaks increases overall productivity',
        'Try: Blocking time for the same activity at different times of day to see which works better',
        'Test: How much time blocking is too much vs. too little'
      ],
      'meditation': [
        'Compare: Meditating in different environments (indoors vs. outdoors)',
        'Test: Different lengths of meditation sessions',
        'Experiment: Different times of day for meditation',
        'Try: Different meditation styles to see what fits best'
      ],
      'creative': [
        'Test: Different creative environments and their impact on output',
        'Experiment: Time-boxed creative sessions vs. open-ended sessions',
        'Compare: Working alone vs. collaborative creative work',
        'Try: Different creative rituals before starting work'
      ]
    };

    // Find matching category
    for (const [category, experiments] of Object.entries(behavioralExperiments)) {
      if (habitName.toLowerCase().includes(category)) {
        return experiments;
      }
    }

    // Default behavioral experiments
    return [
      'Test: What time of day works best for this habit',
      'Experiment: Different environments and their impact',
      'Try: Linking this habit to different existing routines',
      'Compare: Different approaches to see what works best'
    ];
  }

  // Get default gamification elements
  getDefaultGamification(habitName) {
    const gamificationElements = {
      'time-blocking': [
        'Level up time-blocking skills by increasing complexity gradually',
        'Unlock new time-blocking techniques as I master basics',
        'Achievement badges for consistent time-blocking',
        'Quest system for integrating time-blocking with different activities'
      ],
      'creative': [
        'Create a portfolio "gallery" of completed creative works',
        'Level up creative skills through practice milestones',
        'Collect "inspiration cards" during creative sessions',
        'Unlock new creative techniques as I practice'
      ]
    };

    // Find matching category
    for (const [category, elements] of Object.entries(gamificationElements)) {
      if (habitName.toLowerCase().includes(category)) {
        return elements;
      }
    }

    // Default gamification
    return [
      'Track streaks and celebrate milestones',
      'Create visual progress indicators',
      'Award points for consistency',
      'Set up achievement badges for habit mastery'
    ];
  }

  // Get default creative outlets for habit integration
  getDefaultCreativeOutlets(habitName) {
    const creativeOutlets = {
      'time-blocking': [
        'Draw or sketch my weekly schedule',
        'Use colors and visual elements to represent different activities',
        'Create a visual timeline of my day',
        'Design custom icons for different types of activities'
      ],
      'creative': [
        'Document the creative process itself',
        'Create a reflection journal about creative work',
        'Share creative journey rather than just finished products',
        'Connect with other creators for mutual support'
      ]
    };

    // Find matching category
    for (const [category, outlets] of Object.entries(creativeOutlets)) {
      if (habitName.toLowerCase().includes(category)) {
        return outlets;
      }
    }

    // Default creative outlets
    return [
      'Document the process, not just the outcome',
      'Find creative ways to track progress',
      'Express the journey through visual or written reflection',
      'Connect with others on a similar path'
    ];
  }

  // Get default emotional connections
  getDefaultEmotionalConnections(habitName) {
    const emotionalConnections = {
      'time-blocking': [
        'Connect time-blocking to feeling more in control of my life',
        'Link structured time to reduced anxiety about forgotten tasks',
        'Associate time-blocking with increased creative output',
        'Connect scheduling to feeling more spacious in my days'
      ],
      'creative': [
        'Link creative time to feelings of self-expression',
        'Connect creative practice to sense of identity',
        'Associate creative work with joy and flow',
        'Link creative time to stress relief'
      ]
    };

    // Find matching category
    for (const [category, connections] of Object.entries(emotionalConnections)) {
      if (habitName.toLowerCase().includes(category)) {
        return connections;
      }
    }

    // Default emotional connections
    return [
      'Connect habit to positive emotions rather than guilt or obligation',
      'Link the habit to my core values and life purpose',
      'Associate habit completion with feelings of self-efficacy',
      'Connect habit to sense of personal growth'
    ];
  }

  // Apply Cognitive Psychology Principles to habit formation
  applyCognitivePsychPrinciples(habitId, cognitiveOptions = {}) {
    const fs = require('fs');
    const db = this.getHabitDatabase();
    const habit = db.habits.find(h => h.id === habitId);
    
    if (!habit) {
      return { success: false, error: 'Habit not found' };
    }

    // Cognitive Psychology principles integration
    const cognitiveIntegration = {
      metacognitiveAwareness: cognitiveOptions.metacognitiveAwareness || this.getDefaultMetacognitiveStrategies(habit.name),
      cognitiveLoadManagement: cognitiveOptions.cognitiveLoadManagement || this.getDefaultCognitiveLoadStrategies(habit.name),
      attentionBiasModification: cognitiveOptions.attentionBiasModification || this.getDefaultAttentionStrategies(habit.name),
      cognitiveFlexibility: cognitiveOptions.cognitiveFlexibility || this.getDefaultCognitiveFlexibilityStrategies(habit.name),
      schemaModification: cognitiveOptions.schemaModification || this.getDefaultSchemaModification(habit.name),
      executiveFunctionSupport: cognitiveOptions.executiveFunctionSupport || this.getDefaultExecutiveSupport(habit.name)
    };

    // Add cognitive psychology integration to the habit
    habit.cognitivePsychIntegration = cognitiveIntegration;
    
    this.updateHabitDatabase(db);
    
    return {
      success: true,
      message: `Cognitive Psychology principles applied to habit: ${habit.name}`,
      cognitiveEnhancedHabit: habit
    };
  }

  // Get default metacognitive strategies
  getDefaultMetacognitiveStrategies(habitName) {
    const metacognitiveStrategies = {
      'time-blocking': [
        'Monitor my awareness of time throughout the day',
        'Reflect on how well my time-blocking aligns with my energy levels',
        'Evaluate effectiveness of different time-blocking approaches',
        'Notice when I deviate from time-blocks and why'
      ],
      'creative': [
        'Monitor my creative process and identify peak times',
        'Reflect on what triggers creative flow states',
        'Evaluate which creative approaches work best for different projects',
        'Notice mental barriers that block creative flow'
      ]
    };

    // Find matching category
    for (const [category, strategies] of Object.entries(metacognitiveStrategies)) {
      if (habitName.toLowerCase().includes(category)) {
        return strategies;
      }
    }

    // Default metacognitive strategies
    return [
      'Notice when I\'m doing the habit and why',
      'Reflect on what\'s working and what\'s not',
      'Monitor my thoughts and feelings about the habit',
      'Evaluate the effectiveness regularly'
    ];
  }

  // Get default cognitive load management strategies
  getDefaultCognitiveLoadStrategies(habitName) {
    const cognitiveLoadStrategies = {
      'time-blocking': [
        'Keep time-blocking simple to reduce decision fatigue',
        'Use visual aids to reduce memory load',
        'Batch similar activities to reduce switching costs',
        'Limit the number of time-blocks to prevent overload'
      ],
      'complex': [
        'Break complex tasks into smaller, manageable components',
        'Use external tools to offload memory demands',
        'Reduce environmental distractions during complex tasks',
        'Schedule demanding tasks during peak cognitive times'
      ]
    };

    // Find matching category
    for (const [category, strategies] of Object.entries(cognitiveLoadStrategies)) {
      if (habitName.toLowerCase().includes(category)) {
        return strategies;
      }
    }

    // Default cognitive load strategies
    return [
      'Simplify the habit to reduce mental effort',
      'Use external tools to support memory',
      'Reduce distractions during habit performance',
      'Perform habit when cognitive resources are highest'
    ];
  }

  // Get default attention bias modification strategies
  getDefaultAttentionStrategies(habitName) {
    const attentionStrategies = {
      'time-blocking': [
        'Direct attention to scheduled activities',
        'Notice when mind wanders from planned tasks',
        'Reorient attention to time-blocked priorities',
        'Use cues to redirect attention when distracted'
      ],
      'mindfulness': [
        'Notice when attention drifts to distractions',
        'Gently return attention to chosen focus',
        'Observe attention patterns without judgment',
        'Use breath as an anchor for attention'
      ]
    };

    // Find matching category
    for (const [category, strategies] of Object.entries(attentionStrategies)) {
      if (habitName.toLowerCase().includes(category)) {
        return strategies;
      }
    }

    // Default attention strategies
    return [
      'Notice when attention drifts from the habit',
      'Gently redirect focus back to the behavior',
      'Use environmental cues to maintain attention',
      'Observe attention patterns without self-judgment'
    ];
  }

  // Get default cognitive flexibility strategies
  getDefaultCognitiveFlexibilityStrategies(habitName) {
    const cognitiveFlexibilityStrategies = {
      'time-blocking': [
        'Adapt time-blocks when circumstances change',
        'Switch between different time-blocking approaches',
        'Modify schedule when it\'s not working',
        'Maintain structure while allowing flexibility'
      ],
      'adaptive': [
        'Change approach when current method isn\'t working',
        'Try different strategies for the same goal',
        'Shift perspective when facing obstacles',
        'Maintain goal while adjusting means'
      ]
    };

    // Find matching category
    for (const [category, strategies] of Object.entries(cognitiveFlexibilityStrategies)) {
      if (habitName.toLowerCase().includes(category)) {
        return strategies;
      }
    }

    // Default cognitive flexibility strategies
    return [
      'Adjust the habit when circumstances change',
      'Try different approaches to achieve the same outcome',
      'Maintain the goal while adapting the method',
      'Stay flexible with implementation details'
    ];
  }

  // Get default schema modification approaches
  getDefaultSchemaModification(habitName) {
    const schemaModifications = {
      'time-blocking': [
        'Challenge belief that structure restricts creativity',
        'Reframe time-blocking as freedom from decision fatigue',
        'Modify belief that I can multitask effectively',
        'Update beliefs about how much time tasks take'
      ],
      'learning': [
        'Challenge fixed beliefs about learning abilities',
        'Reframe mistakes as learning opportunities',
        'Modify beliefs about intelligence and growth',
        'Update beliefs about the learning process'
      ]
    };

    // Find matching category
    for (const [category, modifications] of Object.entries(schemaModifications)) {
      if (habitName.toLowerCase().includes(category)) {
        return modifications;
      }
    }

    // Default schema modifications
    return [
      'Challenge unhelpful beliefs about the habit',
      'Reframe the habit in a more positive light',
      'Modify limiting beliefs that might block success',
      'Update beliefs based on new experiences'
    ];
  }

  // Get default executive function support strategies
  getDefaultExecutiveSupport(habitName) {
    const executiveSupport = {
      'time-blocking': [
        'Use planning skills to organize time-blocks',
        'Implement self-monitoring of schedule adherence',
        'Apply inhibitory control to resist distractions',
        'Use working memory to hold time-blocking intentions'
      ],
      'goal-directed': [
        'Plan steps toward habit achievement',
        'Monitor progress toward goals',
        'Inhibit competing impulses',
        'Hold goal intentions in working memory'
      ]
    };

    // Find matching category
    for (const [category, support] of Object.entries(executiveSupport)) {
      if (habitName.toLowerCase().includes(category)) {
        return support;
      }
    }

    // Default executive function support
    return [
      'Plan when and how to perform the habit',
      'Monitor progress toward habit goals',
      'Resist impulses that compete with the habit',
      'Keep habit intentions active in mind'
    ];
  }
}

module.exports = HabitFormationSystem;
// run_downtime_research.js
// Script to demonstrate the self-improvement research during downtime

const DowntimeProcessor = require('./downtime_processor');

async function runDemo() {
  console.log("🤖 Initiating downtime self-improvement research demo...\n");
  
  // Create downtime processor
  const downtimeProcessor = new DowntimeProcessor('./memory');
  
  // Force processing to demonstrate capabilities
  console.log("🚀 Forcing downtime processing for demonstration...\n");
  
  try {
    const results = await downtimeProcessor.processDowntimeTasks();
    
    console.log("\n" + "=".repeat(60));
    console.log("DOWNTIME PROCESSING RESULTS");
    console.log("=".repeat(60));
    
    console.log(`Session ID: ${results.session.id}`);
    console.log(`Duration: ${results.session.duration} seconds`);
    console.log(`Tasks processed: ${results.tasksProcessed.length}`);
    
    console.log("\nProcessed Tasks:");
    results.tasksProcessed.forEach((task, index) => {
      console.log(`  ${index + 1}. ${task.type}: ${task.status}`);
      if (task.results) {
        console.log(`     └─ Results: ${Object.keys(task.results).length} categories`);
      }
    });
    
    console.log("\n" + "=".repeat(60));
    console.log("SELF-IMPROVEMENT RESEARCH SUMMARY");
    console.log("=".repeat(60));
    
    // Extract self-improvement research results
    const improvementTask = results.tasksProcessed.find(t => t.type === 'self_improvement_research');
    if (improvementTask && improvementTask.status === 'completed') {
      console.log("✅ Self-improvement research completed successfully");
      
      // Show pending improvements
      const improvementSystem = downtimeProcessor.selfImprovementSystem;
      const pending = improvementSystem.getPendingImprovements();
      
      if (pending.length > 0) {
        console.log(`\n🎯 ${pending.length} Potential Improvements Identified:`);
        pending.slice(0, 5).forEach(imp => {
          console.log(`  • [${imp.category}] ${imp.title}`);
          console.log(`    Confidence: ${(imp.confidence * 100).toFixed(0)}%`);
          console.log(`    Relevance: ${(imp.relevance * 100).toFixed(0)}%`);
        });
        
        if (pending.length > 5) {
          console.log(`  ... and ${pending.length - 5} more`);
        }
      } else {
        console.log("\n📋 No new improvements identified (may need next research cycle)");
      }
    } else if (improvementTask && improvementTask.status === 'skipped') {
      console.log("⏰ Self-improvement research was skipped (interval not reached)");
      console.log("💡 Note: Research interval is set to 24 hours by default");
    }
    
    console.log("\n" + "=".repeat(60));
    console.log("SYSTEM OPTIMIZATION COMPLETE");
    console.log("=".repeat(60));
    console.log("✅ The system is now monitoring for downtime to automatically");
    console.log("   research and suggest self-improvements for both you and me.");
    console.log("✅ Improvements are logged and can be reviewed/implemented as needed.");
    
  } catch (error) {
    console.error("❌ Error during downtime processing:", error);
  }
}

// Also create a simplified version that just focuses on improvement research
async function runImprovementResearchOnly() {
  console.log("🔍 Running focused self-improvement research...\n");
  
  const improvementSystem = new (require('./self_improvement'))('./memory');
  
  try {
    const results = await improvementSystem.runImprovementResearch();
    
    if (results) {
      console.log("✅ Self-improvement research completed!");
      
      // Show summary of findings
      console.log("\n📊 Research Summary by Category:");
      for (const [category, items] of Object.entries(results.categories)) {
        console.log(`  ${category.toUpperCase()}: ${items.length} items found`);
      }
      
      // Show pending improvements
      const pending = improvementSystem.getPendingImprovements();
      if (pending.length > 0) {
        console.log(`\n🎯 ${pending.length} Actionable Improvements Identified:`);
        
        for (const imp of pending) {
          console.log(`  • ${imp.category}: ${imp.title}`);
          console.log(`    → Confidence: ${(imp.confidence * 100).toFixed(0)}%`);
        }
      }
    } else {
      console.log("⏰ Research interval not reached yet");
    }
    
  } catch (error) {
    console.error("❌ Error in improvement research:", error);
  }
}

// Run if this file is executed directly
if (require.main === module) {
  console.log("Choose mode:");
  console.log("1. Full downtime processing (recommended)");
  console.log("2. Improvement research only");
  
  // For demo purposes, run the full version
  runDemo().catch(console.error);
}

module.exports = {
  runDemo,
  runImprovementResearchOnly,
  DowntimeProcessor
};
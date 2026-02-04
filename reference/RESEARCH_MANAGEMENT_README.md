# Research Management System

## Overview
This system provides tools for managing research PDFs relevant to IPNB and therapeutic practice. It includes features for storing, evaluating, and maintaining current research materials.

## Components

### 1. Advanced IPNB Research Summary
- Located at: `ADVANCED_IPNB_RESEARCH_SUMMARY.md`
- Contains advanced research insights with APA citations
- Focuses on practical mechanisms for therapeutic application
- Includes cutting-edge neuroscience discoveries

### 2. Research PDF Storage
- Directory: `research_pdfs/`
- Store full-text research articles here
- Organize by topic or date as needed
- Will be evaluated monthly for validity

### 3. Monthly Evaluation System
- Located at: `MONTHLY_RESEARCH_EVALUATION.md`
- Provides protocol for checking retractions/redactions
- Includes scripts for automated evaluation
- Ensures only valid research informs practice

### 4. Management Scripts
- `manage_research_pdfs.js`: JavaScript tool for managing research collection
- `launch_advanced_ipnb_summary.sh`: Opens the research summary
- `launch_ipnb_report.sh`: Opens the original IPNB report

## Usage Instructions

### To View Advanced Research Summary:
```bash
./launch_advanced_ipnb_summary.sh
```

### To View Original IPNB Report:
```bash
./launch_ipnb_report.sh
```

### To Manage Research PDFs:
```bash
# List all PDFs in collection
node manage_research_pdfs.js list

# Create monthly evaluation report
node manage_research_pdfs.js evaluate

# Show collection statistics
node manage_research_pdfs.js stats

# Show help
node manage_research_pdfs.js help
```

### To Add New Research:
1. Place PDF files in the `research_pdfs/` directory
2. Run monthly evaluation to incorporate new additions
3. Update your practice based on new findings

## Monthly Evaluation Process

The system includes a protocol for evaluating research validity:

1. **File Inventory**: Count and verify all PDFs
2. **Citation Verification**: Check for retractions or redactions
3. **Content Relevance**: Assess applicability to practice
4. **Update Recommendations**: Determine retention/removal

## Important Notes

- Always verify that research articles are current and not retracted
- The system will alert you to potential retractions during evaluation
- Only use research that has been validated for therapeutic application
- Keep the research collection updated with the latest findings

## Next Steps

1. Add relevant research PDFs to the `research_pdfs/` directory
2. Run the monthly evaluation to integrate new materials
3. Apply the advanced mechanisms and findings to your therapeutic practice
4. Set up automated monthly evaluations (instructions provided in the system)

This research management system is designed to support your therapeutic practice with current, validated, and applicable research in IPNB and related fields.
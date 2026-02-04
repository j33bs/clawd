# Monthly Research Evaluation Protocol

## Purpose
This document outlines the monthly evaluation process for research articles stored in the research_pdfs folder. The evaluation ensures that only current, valid research informs therapeutic practice.

## Monthly Evaluation Checklist

### 1. File Inventory
- [ ] Count total PDFs in research_pdfs folder
- [ ] Verify file integrity (check for corrupted files)
- [ ] Document any new additions since last evaluation

### 2. Citation Verification
- [ ] Cross-reference article titles with original sources
- [ ] Check for any retraction notices
- [ ] Verify authors' credentials and institutional affiliations
- [ ] Confirm publication venue legitimacy

### 3. Content Relevance Assessment
- [ ] Evaluate each article's relevance to IPNB practice
- [ ] Assess methodological rigor
- [ ] Rate applicability to therapeutic interventions
- [ ] Note any conflicting findings with established research

### 4. Update Recommendations
- [ ] Identify articles for continued use
- [ ] Flag articles for removal due to retraction/redaction
- [ ] Recommend new research areas to explore
- [ ] Suggest integration strategies for validated findings

## Sample Retraction Detection Script

```python
import os
import requests
import json
from datetime import datetime

def check_retractions(pdf_folder_path):
    """
    Basic script to check for retractions in research database
    """
    print(f"Evaluating research PDFs in: {pdf_folder_path}")
    
    # Get list of PDFs
    pdf_files = [f for f in os.listdir(pdf_folder_path) if f.endswith('.pdf')]
    
    for pdf_file in pdf_files:
        print(f"Checking: {pdf_file}")
        
        # This is a simplified check - in practice, you'd query databases like:
        # - PubMed's retraction watch
        # - CrossMark
        # - Retraction Watch database
        # - Publisher retraction notices
        
        # Placeholder for actual retraction check
        is_retracted = False  # This would be determined by actual database queries
        
        if is_retracted:
            print(f"ALERT: {pdf_file} appears to be retracted.")
            # Here you would notify the user and ask about removal
            
    print("Monthly evaluation complete.")

# Example usage
if __name__ == "__main__":
    check_retractions("./research_pdfs")
```

## Database Query Examples

### PubMed Retraction Search
```
"{article_title}" AND (retraction OR retracted OR withdrawal OR withdrawn)
```

### Journal-Specific Checks
- Check publisher websites for errata or correction notices
- Review institutional repositories for author disclaimers
- Monitor academic social networks for discussion of problematic findings

## Integration Protocols

### Validated Research Integration
1. Create annotation layer with practice applications
2. Develop implementation protocols for therapeutic use
3. Design outcome measures to assess effectiveness
4. Establish peer review process among practitioners

### Removal Procedures
1. Document reason for removal
2. Consult with user about removal decision
3. Remove file from research_pdfs folder
4. Update any linked references or applications
5. Document the removal in audit trail

## Reporting Template

Monthly evaluation report should include:

**Summary Statistics:**
- Total articles evaluated: [X]
- Articles maintained: [X]
- Articles flagged for review: [X]
- Articles recommended for removal: [X]

**Notable Findings:**
- Emerging research trends
- Methodological improvements in field
- New integration opportunities

**Action Items:**
- Specific articles requiring attention
- New research to acquire
- Protocol updates needed

## Best Practices

1. Maintain detailed logs of all evaluations
2. Establish clear criteria for retention/removal
3. Regularly update search protocols
4. Cross-reference multiple verification sources
5. Document decision rationale for all actions
6. Schedule evaluations at consistent intervals

This protocol ensures that the research base informing therapeutic practice remains current, valid, and applicable to IPNB-informed interventions.
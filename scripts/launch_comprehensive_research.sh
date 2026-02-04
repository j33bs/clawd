#!/bin/bash

# Script to launch all research materials for comprehensive review

echo "Launching Comprehensive IPNB Research Materials..."

# Check if files exist and open them
if [ -f "./COMPREHENSIVE_IPNB_RESEARCH_REPORT.md" ]; then
    echo "Opening original IPNB research report..."
    open "./COMPREHENSIVE_IPNB_RESEARCH_REPORT.md"
else
    echo "Warning: Original report not found"
fi

if [ -f "./ADVANCED_IPNB_RESEARCH_SUMMARY.md" ]; then
    echo "Opening advanced IPNB research summary..."
    open "./ADVANCED_IPNB_RESEARCH_SUMMARY.md"
else
    echo "Warning: Advanced summary not found"
fi

if [ -f "./RESEARCH_MANAGEMENT_README.md" ]; then
    echo "Opening research management documentation..."
    open "./RESEARCH_MANAGEMENT_README.md"
else
    echo "Warning: Management documentation not found"
fi

if [ -f "./MONTHLY_RESEARCH_EVALUATION.md" ]; then
    echo "Opening monthly evaluation protocol..."
    open "./MONTHLY_RESEARCH_EVALUATION.md"
else
    echo "Warning: Monthly evaluation protocol not found"
fi

echo "All research materials launched in separate windows."
echo ""
echo "Next Steps:"
echo "1. Review the advanced research summary for practical mechanisms"
echo "2. Examine the original report for foundational concepts"
echo "3. Read the management documentation to understand the system"
echo "4. Place research PDFs in the research_pdfs folder for evaluation"
echo "5. Run 'node manage_research_pdfs.js evaluate' to process new PDFs"
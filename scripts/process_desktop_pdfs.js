#!/usr/bin/env node

/**
 * Daily PDF Processing Script
 * Processes PDFs placed in the desktop pdf_processing folder
 */

const fs = require('fs');
const path = require('path');

async function processDesktopPDFs() {
    const desktopPath = path.join(require('os').homedir(), 'Desktop', 'pdf_processing');
    
    try {
        // Check if the directory exists
        if (!fs.existsSync(desktopPath)) {
            console.log(`Directory does not exist: ${desktopPath}`);
            return;
        }

        // Read all files in the directory
        const files = fs.readdirSync(desktopPath);
        
        // Filter for PDF files
        const pdfFiles = files.filter(file => 
            path.extname(file).toLowerCase() === '.pdf'
        );

        if (pdfFiles.length === 0) {
            console.log('No PDF files found in the processing folder.');
            return;
        }

        console.log(`Found ${pdfFiles.length} PDF file(s) to process:`);
        
        for (const pdfFile of pdfFiles) {
            const fullPath = path.join(desktopPath, pdfFile);
            const stats = fs.statSync(fullPath);
            
            console.log(`- ${pdfFile} (${(stats.size / 1024 / 1024).toFixed(2)} MB)`);
            
            // Move the PDF to the authorized corpus for processing
            const targetDir = './pdf';
            if (!fs.existsSync(targetDir)) {
                fs.mkdirSync(targetDir, { recursive: true });
                console.log(`Created directory: ${targetDir}`);
            }
            
            const targetPath = path.join(targetDir, pdfFile);
            
            // Check if file already exists in target
            if (fs.existsSync(targetPath)) {
                console.log(`  - File already exists in target directory, skipping: ${pdfFile}`);
                continue;
            }
            
            // Move the file to the authorized corpus
            fs.copyFileSync(fullPath, targetPath);
            console.log(`  - Moved to authorized corpus: ${targetPath}`);
            
            // Optionally, remove from desktop folder after processing
            // Uncomment the next line if you want to remove the original after copying
            // fs.unlinkSync(fullPath);
        }

        console.log('\nProcessing complete. Files have been moved to the authorized corpus for verification and analysis.');
    } catch (error) {
        console.error('Error processing PDFs:', error);
    }
}

// Run the processing function
if (require.main === module) {
    processDesktopPDFs().catch(console.error);
}

module.exports = processDesktopPDFs;
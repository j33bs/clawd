#!/usr/bin/env python3
"""
Executable Research Notebook Processor
Treats markdown + code + citations as a single living object
"""

import json
import re
import subprocess
import tempfile
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import nbformat
from nbconvert import PythonExporter


@dataclass
class NotebookCell:
    """Represents a cell in the executable notebook"""
    id: str
    type: str  # 'markdown', 'code', 'citation'
    content: str
    execution_count: Optional[int] = None
    outputs: List[str] = None
    metadata: Dict[str, Any] = None


class NotebookProcessor:
    """
    Processes executable research notebooks as first-class artifacts
    Combines markdown, code, and citations into a single living object
    """
    
    def __init__(self):
        self.cells: List[NotebookCell] = []
    
    def parse_markdown_notebook(self, content: str) -> List[NotebookCell]:
        """Parse markdown content into notebook cells"""
        lines = content.split('\n')
        cells = []
        current_cell_content = []
        current_cell_type = 'markdown'
        cell_id = 0
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Check for code block start
            if line.strip().startswith('```'):
                # End current markdown cell if any
                if current_cell_content and current_cell_type == 'markdown':
                    cell_content = '\n'.join(current_cell_content).strip()
                    if cell_content:
                        cells.append(NotebookCell(
                            id=f"cell_{cell_id}",
                            type='markdown',
                            content=cell_content
                        ))
                        cell_id += 1
                        current_cell_content = []
                
                # Start new code cell
                lang_match = re.match(r'```(\w*)', line.strip())
                language = lang_match.group(1) if lang_match else 'python'
                
                if language.lower() in ['python', 'py', 'bash', 'sh', 'javascript', 'js']:
                    current_cell_type = 'code'
                else:
                    current_cell_type = 'markdown'  # Non-executable code blocks treated as markdown
                
                i += 1
                code_lines = []
                
                # Collect code until closing ```
                while i < len(lines) and not lines[i].strip().startswith('```'):
                    code_lines.append(lines[i])
                    i += 1
                
                if current_cell_type == 'code':
                    cells.append(NotebookCell(
                        id=f"cell_{cell_id}",
                        type='code',
                        content='\n'.join(code_lines).rstrip()
                    ))
                    cell_id += 1
                else:
                    # Add the whole code block as markdown
                    code_block = '```' + language + '\n' + '\n'.join(code_lines) + '\n```'
                    current_cell_content.append(code_block)
                
                current_cell_type = 'markdown'  # Back to markdown after code block
            
            # Check for citation patterns
            elif re.search(r'\[@\w+\]', line) or 'et al.' in line.lower():
                if current_cell_content and current_cell_type == 'markdown':
                    cell_content = '\n'.join(current_cell_content).strip()
                    if cell_content:
                        cells.append(NotebookCell(
                            id=f"cell_{cell_id}",
                            type='markdown',
                            content=cell_content
                        ))
                        cell_id += 1
                        current_cell_content = []
                
                cells.append(NotebookCell(
                    id=f"cell_{cell_id}",
                    type='citation',
                    content=line.strip()
                ))
                cell_id += 1
            
            else:
                current_cell_content.append(line)
                i += 1
        
        # Add final markdown cell if any content remains
        if current_cell_content and current_cell_type == 'markdown':
            cell_content = '\n'.join(current_cell_content).strip()
            if cell_content:
                cells.append(NotebookCell(
                    id=f"cell_{cell_id}",
                    type='markdown',
                    content=cell_content
                ))
        
        return cells
    
    def execute_code_cell(self, code: str, language: str = 'python') -> Dict[str, Any]:
        """Execute a code cell and return results"""
        if language.lower() in ['python', 'py']:
            return self._execute_python_code(code)
        elif language.lower() in ['bash', 'sh']:
            return self._execute_bash_command(code)
        else:
            return {
                'success': False,
                'error': f'Unsupported language: {language}',
                'output': '',
                'execution_time': 0
            }
    
    def _execute_python_code(self, code: str) -> Dict[str, Any]:
        """Execute Python code in a safe environment"""
        try:
            # Create a temporary file to execute
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_file = f.name
            
            # Execute the code with timeout
            result = subprocess.run(
                ['python3', temp_file],
                capture_output=True,
                text=True,
                timeout=30  # 30 second timeout
            )
            
            # Clean up
            os.unlink(temp_file)
            
            return {
                'success': result.returncode == 0,
                'output': result.stdout,
                'error': result.stderr,
                'return_code': result.returncode
            }
        except subprocess.TimeoutExpired:
            os.unlink(temp_file) if 'temp_file' in locals() else None
            return {
                'success': False,
                'output': '',
                'error': 'Execution timed out after 30 seconds',
                'return_code': -1
            }
        except Exception as e:
            return {
                'success': False,
                'output': '',
                'error': str(e),
                'return_code': -1
            }
    
    def _execute_bash_command(self, code: str) -> Dict[str, Any]:
        """Execute bash command"""
        try:
            result = subprocess.run(
                code,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return {
                'success': result.returncode == 0,
                'output': result.stdout,
                'error': result.stderr,
                'return_code': result.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'output': '',
                'error': 'Execution timed out after 30 seconds',
                'return_code': -1
            }
        except Exception as e:
            return {
                'success': False,
                'output': '',
                'error': str(e),
                'return_code': -1
            }
    
    def process_notebook(self, content: str) -> Dict[str, Any]:
        """Process an entire notebook and execute runnable cells"""
        cells = self.parse_markdown_notebook(content)
        
        results = {
            'cells': [],
            'summary': {
                'total_cells': len(cells),
                'code_cells': 0,
                'executed_successfully': 0,
                'errors': 0
            }
        }
        
        for cell in cells:
            cell_result = {
                'id': cell.id,
                'type': cell.type,
                'content': cell.content,
                'execution_result': None
            }
            
            if cell.type == 'code':
                results['summary']['code_cells'] += 1
                exec_result = self.execute_code_cell(cell.content)
                cell_result['execution_result'] = exec_result
                
                if exec_result['success']:
                    results['summary']['executed_successfully'] += 1
                else:
                    results['summary']['errors'] += 1
            
            results['cells'].append(cell_result)
        
        return results
    
    def export_to_jupyter(self, cells: List[NotebookCell], filename: str):
        """Export cells to a Jupyter notebook format"""
        nb = nbformat.v4.new_notebook()
        
        for cell in cells:
            if cell.type == 'code':
                nb.cells.append(nbformat.v4.new_code_cell(cell.content))
            else:
                nb.cells.append(nbformat.v4.new_markdown_cell(cell.content))
        
        with open(filename, 'w', encoding='utf-8') as f:
            nbformat.write(nb, f)
    
    def import_from_jupyter(self, filepath: str) -> str:
        """Import from Jupyter notebook to markdown format"""
        with open(filepath, 'r', encoding='utf-8') as f:
            nb = nbformat.read(f, as_version=4)
        
        md_content = []
        for cell in nb.cells:
            if cell.cell_type == 'markdown':
                md_content.append(cell.source)
            elif cell.cell_type == 'code':
                md_content.append(f"```python\n{cell.source}\n```")
            # Ignore other cell types for now
        
        return '\n\n'.join(md_content)


def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python notebook_processor.py <notebook_file.md>")
        sys.exit(1)
    
    notebook_file = sys.argv[1]
    
    with open(notebook_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    processor = NotebookProcessor()
    result = processor.process_notebook(content)
    
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    # Example usage with a sample notebook
    sample_notebook = """
# Research on Cognitive Load Routing

We propose implementing a tiered cognitive-load routing system that handles classification, summarization, and intent disambiguation locally before escalating to cloud models.

## Local Model Classification

```python
def classify_intent(query):
    simple_keywords = ['hello', 'hi', 'time']
    complex_keywords = ['analyze', 'research', 'implement']
    
    simple_count = sum(1 for kw in simple_keywords if kw in query.lower())
    complex_count = sum(1 for kw in complex_keywords if kw in query.lower())
    
    return "simple" if simple_count > complex_count else "complex"

print(classify_intent("What time is it?"))
print(classify_intent("Analyze the market trends"))
```

## Benefits

This approach preserves quota, reduces latency, and keeps the "thinking surface" close to the machine. According to [@smith2023], local processing can handle up to 70% of requests efficiently.

## Implementation Strategy

```bash
echo "Installing local model system..."
mkdir -p local_models
touch local_models/__init__.py
```

The key design principle is cognitive triage, not redundancy.
"""
    
    processor = NotebookProcessor()
    result = processor.process_notebook(sample_notebook)
    
    print(f"Processed {result['summary']['total_cells']} total cells")
    print(f"Code cells: {result['summary']['code_cells']}")
    print(f"Executed successfully: {result['summary']['executed_successfully']}")
    print(f"Errors: {result['summary']['errors']}")
    
    print("\nCell execution results:")
    for cell_result in result['cells']:
        if cell_result['type'] == 'code':
            exec_res = cell_result['execution_result']
            print(f"  {cell_result['id']}: {'✓' if exec_res['success'] else '✗'} ({exec_res.get('return_code', 'N/A')})")
            if exec_res['output'].strip():
                print(f"    Output: {exec_res['output'].strip()}")
            if exec_res['error'].strip():
                print(f"    Error: {exec_res['error'].strip()}")
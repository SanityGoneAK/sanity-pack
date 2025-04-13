# This is a modified version of
# https://github.com/isHarryh/Ark-FBS-Py/blob/main/Compile.py
# By https://github.com/isHarryh
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

def get_root_type_name(fbs_file: Path) -> Optional[str]:
    """Extract the root type name from a FBS file."""
    import re
    with open(fbs_file, encoding='UTF-8') as f:
        content = f.readlines()
    for line in content:
        match = re.match(r'root_type\s(.+);', line)
        if match:
            return match.group(1)
    return None

def compile_fbs(flatc: str, fbs_dir: Path, output_dir: Path) -> None:
    """Compile FBS files into Python scripts.
    
    Args:
        flatc: Path to the flatc executable
        fbs_dir: Path to the source FBS directory
        output_dir: Path to the output directory
    """
    print("Starting FBS compilation...")
    
    if output_dir.exists():
        print(f"Removing existing output directory: {output_dir}")
        shutil.rmtree(output_dir)
    
    print(f"Creating output directory: {output_dir}")
    output_dir.mkdir(parents=True)
    
    print(f"Processing FBS files from: {fbs_dir}")
    count = 0
    
    for fbs_file in fbs_dir.rglob("*.fbs"):
        # Compile
        pure_name = fbs_file.stem
        print(f"Compiling: {fbs_file}")
        
        subprocess.run([
            flatc,
            '--python',
            '--gen-onefile',
            '-o',
            str(output_dir),
            str(fbs_file)
        ])
        
        # Modify generated file
        py_file = output_dir / f'{pure_name}_generated.py'
        root_type_name = get_root_type_name(fbs_file)
        
        if root_type_name and py_file.exists():
            with open(py_file, encoding='UTF-8') as r:
                content = r.readlines()
            
            linesep = '\r\n' if content[0].endswith('\r\n') else '\n'
            while content[-1] == linesep:
                content.pop()
            
            content.extend([linesep, f'ROOT_TYPE = {root_type_name}', linesep])
            
            # Replace file
            new_file = output_dir / f'{pure_name}.py'
            os.unlink(py_file)
            with open(new_file, 'w', encoding='UTF-8') as w:
                w.writelines(content)
            
            count += 1
    
    print(f"Finished! {count} files compiled.")

def main():
    # Get the flatc executable path from environment or use default
    flatc = os.environ.get('FLATC_PATH', './flatc')
    
    # Define paths
    base_dir = Path(__file__).parent.parent
    fbs_dir = Path(__file__).parent
    output_dir = fbs_dir / '_generated'
    
    # Compile CN FBS files
    cn_fbs_dir = fbs_dir / 'cn' / 'FBS'
    cn_output_dir = output_dir / 'cn'
    compile_fbs(flatc, cn_fbs_dir, cn_output_dir)
    
    # Compile Global FBS files
    global_fbs_dir = fbs_dir / 'global' / 'FBS'
    global_output_dir = output_dir / 'global'
    compile_fbs(flatc, global_fbs_dir, global_output_dir)

if __name__ == '__main__':
    main() 
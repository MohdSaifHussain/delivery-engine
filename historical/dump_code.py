import os

# Files or directories to ignore (to keep the file size small)
IGNORE_LIST = {'.git', '__pycache__', '.venv', 'venv', '.idea', '.vscode', 'dist', 'build', 'node_modules'}
# Extensions we actually care about for the audit
EXTENSIONS = {'.py', '.md', '.toml', '.txt', '.yaml', '.yml', '.ini', '.json'}

def create_code_dump(output_filename="project_dump.txt"):
    with open(output_filename, 'w', encoding='utf-8') as outfile:
        for root, dirs, files in os.walk('.'):
            # Filter out ignored directories
            dirs[:] = [d for d in dirs if d not in IGNORE_LIST]
            
            for file in files:
                if any(file.endswith(ext) for ext in EXTENSIONS):
                    file_path = os.path.join(root, file)
                    outfile.write(f"\n\n{'='*60}\n")
                    outfile.write(f"FILE: {file_path}\n")
                    outfile.write(f"{'='*60}\n\n")
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as infile:
                            outfile.write(infile.read())
                    except Exception as e:
                        outfile.write(f"[Error reading file: {e}]\n")

    print(f"Done! Created {output_filename}. Now upload this file to me.")

if __name__ == "__main__":
    create_code_dump()
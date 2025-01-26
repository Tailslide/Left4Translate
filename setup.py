import os
import shutil
import subprocess
from pathlib import Path

def main():
    """Set up Left4Translate development environment."""
    print("Setting up Left4Translate development environment...")
    
    # Get the project root directory
    project_root = Path(__file__).parent.absolute()
    
    # Create virtual environment if it doesn't exist
    if not os.path.exists('venv'):
        print("\nCreating virtual environment...")
        subprocess.run(['python', '-m', 'venv', 'venv'], check=True)
    
    # Activate virtual environment and install dependencies
    print("\nInstalling dependencies...")
    if os.name == 'nt':  # Windows
        pip_path = os.path.join('venv', 'Scripts', 'pip')
    else:  # Unix/Linux/Mac
        pip_path = os.path.join('venv', 'bin', 'pip')
    
    subprocess.run([pip_path, 'install', '-r', 'requirements.txt'], check=True)
    
    # Clone and set up Turing Smart Screen library
    print("\nSetting up Turing Smart Screen library...")
    turing_dir = project_root / 'turing-smart-screen-python'
    library_dir = project_root / 'src' / 'library'
    
    # Remove existing directories if they exist
    if turing_dir.exists():
        shutil.rmtree(turing_dir)
    if library_dir.exists():
        shutil.rmtree(library_dir)
    
    # Clone the repository
    subprocess.run(['git', 'clone', 'https://github.com/mathoudebine/turing-smart-screen-python.git'], check=True)
    
    # Copy library files
    shutil.copytree(turing_dir / 'library', library_dir)
    
    # Create config.json if it doesn't exist
    config_file = project_root / 'config' / 'config.json'
    if not config_file.exists():
        print("\nCreating initial config.json...")
        shutil.copy(project_root / 'config' / 'config.sample.json', config_file)
        print("Please update config/config.json with your settings")
    
    print("\nSetup completed successfully!")
    print("\nNext steps:")
    print("1. Update config/config.json with your settings")
    print("2. Activate the virtual environment:")
    if os.name == 'nt':  # Windows
        print("   .\\venv\\Scripts\\activate")
    else:  # Unix/Linux/Mac
        print("   source venv/bin/activate")
    print("3. Run the application:")
    print("   python src/main.py")

if __name__ == '__main__':
    main()
import sys
from pathlib import Path

# Allow tests to import project modules from the root
sys.path.insert(0, str(Path(__file__).parent.parent))

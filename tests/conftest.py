import os
import sys
import warnings

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests", "tools"))
warnings.filterwarnings("ignore")

FIX = os.path.join(ROOT, "tests", "fixtures")

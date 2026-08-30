"""WorthApply — run with: streamlit run worthapply/app/main.py"""
import subprocess, sys
from pathlib import Path

app_path = Path(__file__).parent / "ui" / "streamlit_app.py"
subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_path)])

"""AgentCore Runtime entrypoint shim.

The deployable code lives in the src/cv_agent package; this root-level file is
what the AgentCore CodeZip runtime executes. It makes the src layout importable
whether or not the package was pip-installed, then starts the runtime app.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from cv_agent.runtime import app  # noqa: E402

if __name__ == "__main__":
    app.run()

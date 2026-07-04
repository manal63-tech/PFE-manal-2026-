# HydroMon

## Setup Instructions

### Prerequisites
- **Python 3.10+** installed on your system
- A terminal-friendly code editor (recommended: [VS Code](https://code.visualstudio.com/))

### Initial Setup

1. **Clone and navigate** to the project directory:
   ```bash
   cd HydroMon
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment**:
   
   | Platform | Command |
   |----------|---------|
   | Windows  | `venv\Scripts\activate` |
   | macOS/Linux | `source venv/bin/activate` |

4. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

### Running the Application

1. **Apply database migrations**:
   ```bash
   flask db upgrade
   ```

2. **Set the Flask application environment** (if needed):
   
   | Platform | Command |
   |----------|---------|
   | Windows  | `set FLASK_APP=app.py` |
   | macOS/Linux | `export FLASK_APP=app.py` |

3. **Start the development server**:
   ```bash
   flask run --debug
   ```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| **"Package not found" errors** | Ensure your virtual environment is activated (`venv\Scripts\activate` or `source venv/bin/activate`) |
| **Database failure** | Verify that the `instance/` folder was automatically created. If not, create it manually. |
| **Port already in use** | Run with a different port: `flask run --debug --port=5001` |

---

## Additional Commands

| Command | Description |
|---------|-------------|
| `flask shell` | Opens an interactive Python shell with the app context |
| `flask db migrate -m "message"` | Generate a new migration |
| `flask db downgrade` | Rollback the last migration |
| `python -m pytest` | Run tests (if configured) |

---


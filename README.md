## Prerequisites

Before starting, ensure the following are installed:

1.  **Python 3.x**
2.  **uv** (Python Package Manager).
    If `uv` is not installed, run this command:

    _Mac/Linux:_

    ```bash
    curl -LsSf [https://astral.sh/uv/install.sh](https://astral.sh/uv/install.sh) | sh
    ```

    _Windows:_

    ```powershell
    powershell -c "irm [https://astral.sh/uv/install.ps1](https://astral.sh/uv/install.ps1) | iex"
    ```

## Setup & Installation

Follow these steps after cloning the repository:

1.  **Navigate to your app directory**

    ```bash
    cd <your-app-directory>
    ```

2.  **Install Dependencies:**
    You don't need to create a `venv` because `uv` will automatically create one.

    ```bash
    uv sync
    ```

    _This command will read pyproject.toml and uv.lock, and then install all dependencies required for this app._

## Running server

To run the server in development mode (with _hot-reload_ feature):

```bash
uv run fastapi dev app/main.py
```

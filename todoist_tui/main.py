import os
from dotenv import load_dotenv
from .app import TodoistApp


def run() -> None:
    load_dotenv()
    token = os.environ.get("TODOIST_API_TOKEN")
    if not token:
        raise RuntimeError(
            "TODOIST_API_TOKEN is not set. "
            "Add it to a .env file or export it in your shell:\n"
            "  echo 'TODOIST_API_TOKEN=your_token_here' > .env"
        )
    app = TodoistApp(api_token=token)
    app.run()


if __name__ == "__main__":
    run()

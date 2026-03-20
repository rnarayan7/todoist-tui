from textual.app import ComposeResult
from textual.widgets import Input, RichLog
from textual.containers import Vertical
from textual._work_decorator import work

MIN_HEIGHT = 5
MAX_HEIGHT = 30
STEP = 3


class ChatPane(Vertical):
    """Bottom pane for chatting with the Claude task assistant."""

    def compose(self) -> ComposeResult:
        yield RichLog(id="chat-log", wrap=True, markup=True)
        yield Input(placeholder="Ask about your tasks…", id="chat-input")

    def on_mount(self) -> None:
        log = self.query_one("#chat-log", RichLog)
        log.write("[dim]Type a message and press Enter. Esc to return to tasks.[/dim]")
        log.write("[dim]Ctrl+J/K to resize pane.[/dim]")

    def focus_input(self) -> None:
        self.query_one("#chat-input", Input).focus()

    def _current_height(self) -> int:
        h = self.styles.height
        if h is not None and h.value is not None:
            return int(h.value)
        return 10

    def _resize(self, delta: int) -> None:
        new = max(MIN_HEIGHT, min(MAX_HEIGHT, self._current_height() + delta))
        self.styles.height = new

    def on_key(self, event) -> None:
        if event.key == "escape":
            from .task_list import TaskList
            self.app.query_one(TaskList).focus()
        elif event.key == "ctrl+k":
            event.stop()
            self._resize(STEP)
        elif event.key == "ctrl+j":
            event.stop()
            self._resize(-STEP)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if not value:
            return
        input_widget = self.query_one("#chat-input", Input)
        input_widget.value = ""

        log = self.query_one("#chat-log", RichLog)
        log.write(f"\n[bold cyan]You:[/bold cyan] {value}")
        log.write("[dim]Thinking…[/dim]")

        self._send_message(value)

    @work
    async def _send_message(self, message: str) -> None:
        log = self.query_one("#chat-log", RichLog)
        try:
            assistant = self.app._assistant  # type: ignore[attr-defined]
            response = await assistant.send(message)
            log.write(f"[bold green]Claude:[/bold green] {response}")
        except Exception as e:
            log.write(f"[bold red]Error:[/bold red] {e}")

        # Refresh the task list to reflect any changes Claude made
        self.app.action_reload()  # type: ignore[attr-defined]

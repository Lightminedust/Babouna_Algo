from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from rich.panel import Panel
import os
import sys
import time
import importlib

# Add parent folder to PYTHONPATH
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from db.connectDb import get_db

console = Console()

class Babouna:
    """
    Main class for language management.
    """

    def __init__(self, language=None):
        self.language = language.lower() if language else None
        self.db = get_db()
        self.scripts = {
            "extract": ("services.extract", "extract_and_insert"),
            "cleanData_1": ("snippets.cleanData_1", "filter_and_delete"),
            "cleanData_2": ("snippets.cleanData_2", "clean_duplicates"),
            "mappData": ("snippets.mappData", "link_in_memory"),
            "vectorize": ("services.Vectorisation", "vectorize")  # added vectorization
        }

    def display_welcome(self):
        console.print(Panel.fit(
            "[bold magenta]BABOUNA - LANGUAGE MANAGEMENT[/bold magenta]\n[dim]Developed by Gemmie[/dim]",
            border_style="cyan",
        ))

    def _run_script(self, key, *args):
        if key not in self.scripts:
            console.print(f"[red]Script '{key}' not found.[/red]")
            return
        module_name, func_name = self.scripts[key]
        console.print(f"[bold blue]Running: {module_name}.{func_name}...[/bold blue]")
        try:
            module = importlib.import_module(module_name)
            func = getattr(module, func_name)
            func(*args)
            console.print(f"[green]Completed: {func_name}[/green]\n")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]\n")
        time.sleep(1)

    def language_exists(self, language=None):
        name = language or self.language
        if not name:
            return False
        return f"mots_{name}" in self.db.list_collection_names()

    def create_from_pdf(self, pdf_path):
        if not self.language:
            raise ValueError("Language not defined.")
        if self.language_exists():
            raise ValueError(f"The language '{self.language}' already exists.")
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        console.print(Panel(f"Creating language [bold]{self.language}[/bold]\nFile: [cyan]{pdf_path}[/cyan]", style="magenta"))
        self._run_script("extract", pdf_path, self.language)
        self._run_script("cleanData_1", self.language)
        self._run_script("cleanData_2", self.language)
        self._run_script("mappData", self.language)
        self._run_script("vectorize", self.language)
        console.print(f"[bold green]Language '{self.language}' successfully created.[/bold green]")

    def add_from_pdf(self, pdf_path):
        if not self.language_exists():
            raise ValueError(f"Language '{self.language}' not found.")
        console.print(Panel(f"Adding data to language [bold]{self.language}[/bold]\nFile: [cyan]{pdf_path}[/cyan]", style="blue"))
        self._run_script("extract", pdf_path, self.language)

    def clean_and_map(self):
        console.print(Panel(f"Cleaning and mapping language [bold]{self.language}[/bold]", style="yellow"))
        self._run_script("cleanData_1", self.language)
        self._run_script("cleanData_2", self.language)
        self._run_script("mappData", self.language)

    def vectorize_language(self):
        console.print(Panel(f"Vectorizing language [bold]{self.language}[/bold]", style="cyan"))
        self._run_script("vectorize", self.language)

    def _ask_for_pdf(self):
        while True:
            path = Prompt.ask("Path to PDF file (or 'exit')")
            if path.lower() == "exit":
                return None
            if not os.path.exists(path):
                console.print("[red]File not found.[/red]")
                continue
            return path

    def _main_menu(self):
        table = Table(title="Main Menu", title_style="bold magenta")
        table.add_column("Option", style="cyan", justify="center")
        table.add_column("Action", style="green")
        table.add_row("1", "Add a new language")
        table.add_row("2", "Manage an existing language")
        table.add_row("0", "Exit")
        console.print(table)
        return Prompt.ask("Your choice", choices=["0", "1", "2"])

    def _existing_language_menu(self):
        console.print(f"\n[bold green]Selected language:[/bold green] [bold]{self.language}[/bold]")
        table = Table(title="Available Options")
        table.add_column("Option", justify="center", style="cyan")
        table.add_column("Action", style="green")
        table.add_row("1", "Add data from a PDF")
        table.add_row("2", "Clean and remap")
        table.add_row("3", "Vectorize data")
        table.add_row("0", "Back")
        console.print(table)
        return Prompt.ask("Your choice", choices=["0", "1", "2", "3"])

    def run(self):
        self.display_welcome()

        while True:
            choice = self._main_menu()

            if choice == "1":
                while True:
                    language = Prompt.ask("Name of the new language (or 'exit')").strip().lower()
                    if language == "exit":
                        break
                    self.language = language
                    if not language:
                        console.print("[red]Invalid name.[/red]")
                        continue
                    if self.language_exists():
                        console.print(f"[red]The language '{language}' already exists.[/red]")
                        continue
                    pdf = self._ask_for_pdf()
                    if pdf:
                        try:
                            self.create_from_pdf(pdf)
                            break
                        except Exception as e:
                            console.print(f"[red]{e}[/red]")
                    else:
                        break

            elif choice == "2":
                while True:
                    language = Prompt.ask("Name of the existing language (or 'exit')").strip().lower()
                    if language == "exit":
                        break
                    self.language = language
                    if not self.language_exists():
                        console.print(f"[red]The language '{language}' does not exist.[/red]")
                        continue

                    while True:
                        choice2 = self._existing_language_menu()
                        if choice2 == "0":
                            break
                        elif choice2 == "1":
                            pdf = self._ask_for_pdf()
                            if pdf:
                                try:
                                    self.add_from_pdf(pdf)
                                except Exception as e:
                                    console.print(f"[red]{e}[/red]")
                        elif choice2 == "2":
                            try:
                                self.clean_and_map()
                            except Exception as e:
                                console.print(f"[red]{e}[/red]")
                        elif choice2 == "3":
                            try:
                                self.vectorize_language()
                            except Exception as e:
                                console.print(f"[red]{e}[/red]")
                    break

            elif choice == "0":
                console.print("[bold green]Thank you for using Babouna.[/bold green]")
                break


if __name__ == "__main__":
    app = Babouna()
    app.run()

import datetime
import functools

import apprise
import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy.orm import Session

from nmba.data.database import SessionLocal
from nmba.data.models import Bill, Config

app = typer.Typer()
console = Console()


def concise_errors(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)

    return wrapper


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Notification/Config Commands ---
def setup_apprise(db):
    """Setup Apprise instance with notification targets."""
    a = apprise.Apprise()
    targets = db.query(Config).filter(Config.key == "notify_target").all()
    for t in targets:
        a.add(t.value)
    return a


@app.command()
@concise_errors
def config_set_notify_target(url: str):
    """Set a notification target URL (Apprise). Run multiple times to add more."""
    db = next(get_db())
    db.add(Config(key="notify_target", value=url))
    db.commit()
    console.print(f"[green]Added notification target:[/green] {url}")


@app.command()
@concise_errors
def config_show():
    """Show current notification config."""
    db = next(get_db())
    if targets := db.query(Config).filter(Config.key == "notify_target").all():
        for t in targets:
            console.print(f"[cyan]{t.value}[/cyan]")
    else:
        console.print("[yellow]No notification targets set.[/yellow]")


@app.command()
@concise_errors
def notify(
    lookahead_days: int = typer.Option(
        1,
        "--lookahead-days",
        "-l",
        help="How many days ahead to check for due bills (e.g. -l 3 for 3 days)",
        show_default=True,
    )
):
    """
    Check for unpaid bills due within the next N days and print them.
    Example usage:
      nmba notify --lookahead-days 3
      nmba notify -l 7
    Add this command to your crontab to get periodic notifications.
    Example crontab entry to run every morning at 8am:
      0 8 * * * /usr/bin/python3 /path/to/nmba/cli.py notify
    """
    db = next(get_db())
    today = datetime.date.today()
    due_days = [(today.day + i - 1) % 31 + 1 for i in range(lookahead_days)]
    bills = (
        db.query(Bill)
        .filter(
            Bill.paid == False,  # pylint: disable=singleton-comparison
            Bill.due_day.in_(due_days),
        )
        .all()
    )
    if not bills:
        console.print("[green]No bills due soon![/green]")
        return
    table = Table(title="Upcoming Bills")
    table.add_column("Name")
    table.add_column("Recipient")
    table.add_column("Due Day")
    table.add_column("Amount")
    for bill in bills:
        table.add_row(
            bill.name, bill.recipient, str(bill.due_day), f"${bill.amount:.2f}"  # type: ignore
        )
    console.print("[yellow]Bills due soon:[/yellow]")
    console.print(table)
    a = setup_apprise(db)
    if bills:
        msg = "\n".join(
            [
                f"{bill.name} to {bill.recipient} due on day {bill.due_day} for ${bill.amount:.2f}"
                for bill in bills
            ]
        )
        a.notify(body=msg, title="Upcoming Bills Reminder")
        console.print("[green]Notification sent via Apprise.[/green]")


# --- CRUD Commands ---
@app.command()
@concise_errors
def add_bill():
    """Add a new bill."""
    db = next(get_db())
    name = typer.prompt("Bill name")
    recipient = typer.prompt("Recipient")
    due_day = typer.prompt("Due day (1-31)", type=int)
    amount = typer.prompt("Amount", type=float)
    bill = Bill(
        name=name, recipient=recipient, due_day=due_day, amount=amount, paid=False
    )
    db.add(bill)
    db.commit()
    console.print(
        f"[green]Added bill:[/green] {name} for {recipient} (due day {due_day}, amount ${amount:.2f})"
    )


@app.command()
@concise_errors
def remove_bill(bill_id: int = typer.Argument(..., help="Bill ID to remove")):
    """Remove a bill by ID."""
    db = next(get_db())
    bill = db.query(Bill).filter(Bill.id == bill_id).first()
    if not bill:
        console.print(f"[red]No bill found with ID {bill_id}.[/red]")
        raise typer.Exit(1)
    db.delete(bill)
    db.commit()
    console.print(f"[green]Removed bill with ID {bill_id}.[/green]")


@app.command()
@concise_errors
def list_bills():
    """List all bills in a table."""
    db = next(get_db())
    bills = db.query(Bill).all()
    table = Table(title="Bills")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="bold")
    table.add_column("Recipient")
    table.add_column("Due Day", justify="right")
    table.add_column("Amount", justify="right")
    table.add_column("Paid", justify="center")
    for bill in bills:
        table.add_row(
            str(bill.id),
            bill.name,
            bill.recipient,
            str(bill.due_day),
            f"${bill.amount:.2f}",
            "✅" if bill.paid else "❌",
        )
    console.print(f"Today's date: {datetime.date.today()}\n")
    console.print(table)


@app.command()
@concise_errors
def mark_paid(bill_id: int = typer.Argument(..., help="Bill ID to mark as paid")):
    """Mark a bill as paid by ID."""
    db: Session = next(get_db())
    bill = db.query(Bill).filter(Bill.id == bill_id).first()
    if not bill:
        console.print(f"[red]No bill found with ID {bill_id}.[/red]")
        raise typer.Exit(1)
    bill.paid = True
    db.commit()
    console.print(f"[green]Marked bill ID {bill_id} as paid.[/green]")


@app.command()
@concise_errors
def edit_bill(
    bill_id: int = typer.Argument(..., help="Bill ID to edit"),
    name: str = typer.Option(None, help="New name"),
    recipient: str = typer.Option(None, help="New recipient"),
    due_day: int = typer.Option(None, help="New due day (1-31)"),
    amount: float = typer.Option(None, help="New amount"),
    paid: bool = typer.Option(None, help="Paid status (true/false)"),
):
    """Edit a bill by ID. Only specified fields are updated."""
    db: Session = next(get_db())
    bill = db.query(Bill).filter(Bill.id == bill_id).first()
    if not bill:
        console.print(f"[red]No bill found with ID {bill_id}.[/red]")
        raise typer.Exit(1)
    updated = False
    if name is not None:
        bill.name = name
        updated = True
    if recipient is not None:
        bill.recipient = recipient
        updated = True
    if due_day is not None:
        bill.due_day = due_day
        updated = True
    if amount is not None:
        bill.amount = amount
        updated = True
    if paid is not None:
        bill.paid = paid
        updated = True
    if updated:
        db.commit()
        console.print(f"[green]Updated bill ID {bill_id}.[/green]")
    else:
        console.print("[yellow]No fields updated.[/yellow]")


@app.command()
@concise_errors
def mark_unpaid(bill_id: int = typer.Argument(..., help="Bill ID to mark as unpaid")):
    """Mark a bill as unpaid by ID."""
    db: Session = next(get_db())
    bill = db.query(Bill).filter(Bill.id == bill_id).first()
    if not bill:
        console.print(f"[red]No bill found with ID {bill_id}.[/red]")
        raise typer.Exit(1)
    bill.paid = False
    db.commit()
    console.print(f"[green]Marked bill ID {bill_id} as unpaid.[/green]")


@app.command()
@concise_errors
def mark_all_paid():
    """Mark ALL bills as paid."""
    db: Session = next(get_db())
    updated = db.query(Bill).update({Bill.paid: True})
    db.commit()
    console.print(f"[green]Marked {updated} bill(s) as paid.[/green]")


@app.command()
@concise_errors
def mark_all_unpaid():
    """Mark ALL bills as unpaid."""
    db: Session = next(get_db())
    updated = db.query(Bill).update({Bill.paid: False})
    db.commit()
    console.print(f"[green]Marked {updated} bill(s) as unpaid.[/green]")


@app.command()
@concise_errors
def remove_all_bills():
    """Remove all bills from the database."""
    db: Session = next(get_db())
    deleted = db.query(Bill).delete()
    db.commit()
    console.print(f"[green]Removed {deleted} bill(s) from the database.[/green]")


@app.command()
@concise_errors
def import_csv(
    path: str = typer.Argument(..., help="Path to CSV file with bills"),
    overwrite: bool = typer.Option(
        False, "--overwrite", help="Delete all existing bills before import"
    ),
):
    """Import bills from a CSV file. Required columns: name, recipient, due_day, amount. Optional: paid. Use --overwrite to clear all existing bills first."""
    import csv

    db: Session = next(get_db())
    if overwrite:
        deleted = db.query(Bill).delete()
        db.commit()
        console.print(
            f"[yellow]Deleted {deleted} existing bill(s) before import.[/yellow]"
        )
    added = 0
    skipped = 0
    with open(path, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        required = {"name", "recipient", "due_day", "amount"}
        if missing := required - set(reader.fieldnames or []):
            console.print(f"[red]Missing required columns: {', '.join(missing)}[/red]")
            raise typer.Exit(1)
        for i, row in enumerate(reader, 1):
            try:
                name = row["name"].strip()
                recipient = row["recipient"].strip()
                due_day = int(row["due_day"])
                amount = float(row["amount"])
                paid = str(row.get("paid", "")).strip().lower() in {"true", "1", "yes"}
                db.add(
                    Bill(
                        name=name,
                        recipient=recipient,
                        due_day=due_day,
                        amount=amount,
                        paid=paid,
                    )
                )
                added += 1
            except Exception as e:
                skipped += 1
                console.print(f"[yellow]Skipping row {i}: {e}[/yellow]")
        db.commit()
    console.print(f"[green]Imported {added} bill(s). Skipped {skipped} row(s).[/green]")


@app.command()
@concise_errors
def export_csv(
    path: str = typer.Argument(..., help="Path to write CSV file with bills")
):
    """Export all bills to a CSV file. Columns: name, recipient, due_day, amount, paid."""
    import csv

    db: Session = next(get_db())
    bills = db.query(Bill).all()
    with open(path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(
            csvfile, fieldnames=["name", "recipient", "due_day", "amount", "paid"]
        )
        writer.writeheader()
        for bill in bills:
            writer.writerow(
                {
                    "name": bill.name,
                    "recipient": bill.recipient,
                    "due_day": bill.due_day,
                    "amount": f"{bill.amount:.2f}",
                    "paid": str(bool(bill.paid)),
                }
            )
    console.print(f"[green]Exported {len(bills)} bill(s) to {path}.[/green]")


@app.command()
@concise_errors
def version():
    """Prints the version of the tool."""
    try:
        try:
            from importlib.metadata import PackageNotFoundError, version
        except ImportError:
            from importlib_metadata import PackageNotFoundError, version  # type: ignore

        try:
            nmba_version = version("never-miss-a-bill-again")
            console.print(f"never-miss-a-bill-again version {nmba_version}")
        except PackageNotFoundError:
            console.print("[red]Package not found. Did you install with pip?[/red]")
    except ImportError:
        console.print("[red]importlib.metadata and importlib_metadata not found[/red]")


@app.command()
@concise_errors
def init():
    """Initialize the database in ~/.never_miss_a_bill_again/nmba.db"""
    import os

    from nmba.data.database import DB_DIR, DB_PATH, engine
    from nmba.data.models import Base

    os.makedirs(DB_DIR, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    console.print(f"[green]Initialized database at {DB_PATH}[/green]")


if __name__ == "__main__":
    app()

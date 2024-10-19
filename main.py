import typer
from src.noetic_game import graph

app = typer.Typer(pretty_exceptions_enable=False)

# def process_input(user_input: str):
    # Placeholder for whatever processing logic you need
    # return f"You entered: {user_input}"

@app.command()
def interactive():
    """Continuously accept input from the user."""
    while True:
        # Prompt the user for input
        user_input = input("Enter your input (or type 'exit' to quit): ")
        
        # Check if the user wants to exit the loop
        if user_input.lower() == 'exit':
            print("Exiting the CLI.")
            break
        
        # Process the input
        graph.process_input(user_input)


if __name__ == "__main__":
    app()
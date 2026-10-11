# ask the agent one question from the command line
# run: python -m agent.ask "What was the average carbon intensity in March 2025?"
#      --sql    also print the SQL the agent ran
#      --trace  print the full trace (every attempt, tokens, settings) instead
#      --prompt also print the system prompt the model sees

import argparse
import json

from agent.agent import Agent


def main():
    parser = argparse.ArgumentParser(description="Ask the grid SQL agent a question")
    parser.add_argument("question")
    parser.add_argument("--sql", action="store_true", help="also print the SQL the agent ran")
    parser.add_argument("--trace", action="store_true", help="print the full trace as JSON")
    parser.add_argument("--prompt", action="store_true", help="also print the system prompt")
    args = parser.parse_args()

    agent = Agent()
    if args.prompt:
        print(agent.system_prompt, "\n" + "-" * 60)

    result = agent.ask(args.question)
    if args.trace:
        print(json.dumps(result, indent=2, default=str))
        return

    if result["status"] != "answered":
        print(f"No answer ({result['status']}): {result['error']}")
        return
    print(f"Answer: {result['answer']}")
    print(f"{result['explanation']}")
    if args.sql:
        print(f"\nSQL: {result['final_sql']}")


if __name__ == "__main__":
    main()

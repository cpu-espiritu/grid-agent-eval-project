# ask the agent one question from the command line and print its trace
# run: python -m agent.ask "What was the average carbon intensity in March 2025?"
#      add --prompt to print the system prompt the model sees

import argparse
import json

from agent.agent import Agent


def main():
    parser = argparse.ArgumentParser(description="Ask the grid SQL agent a question")
    parser.add_argument("question")
    parser.add_argument("--prompt", action="store_true", help="also print the system prompt")
    args = parser.parse_args()

    agent = Agent()
    if args.prompt:
        print(agent.system_prompt, "\n" + "-" * 60)
    print(json.dumps(agent.ask(args.question), indent=2, default=str))


if __name__ == "__main__":
    main()

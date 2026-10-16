"""Run a local CSO demo that reads the fixed public Wikipedia page. Requires explicit web opt-in. Importing this manual check never initializes the app."""

import argparse
from pathlib import Path
import sys


def run_check():
    import privacy_bootstrap
    from crewai import Agent, Task, Crew, LLM

    from config import config
    from tools.research_tool import PageReaderTool

    ollama_llm = LLM(model=config.OLLAMA_MODEL, base_url=config.OLLAMA_BASE_URL)
    page_reader_tool = PageReaderTool()
    cso_agent = Agent(
        role="Chief Strategy Officer (CSO)",
        goal="Analyze strategic information by strictly consulting provided external sources.",
        backstory="You are a data-driven CSO who bases decisions exclusively on external sources accessed via available tools.",
        tools=[page_reader_tool],
        llm=ollama_llm,
        verbose=True,
        allow_delegation=False,
    )
    target_url = "https://en.wikipedia.org/wiki/Artificial_intelligence"
    task = Task(
        description=f"Use the tool 'read_web_page' with url='{target_url}' to fetch the page content. Then, summarize the main definition of artificial intelligence from the text in 2-3 English sentences.",
        expected_output="A concise 2-3 sentence summary in English based strictly on the fetched web page.",
        agent=cso_agent,
    )
    crew = Crew(agents=[cso_agent], tasks=[task], verbose=True)
    print("=" * 60)
    print("STARTING CSO TOOL TEST (ENGLISH OUTPUT)")
    print("=" * 60)
    result = crew.kickoff()
    print("\nResult:")
    print(result)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-web",
        action="store_true",
        help="Opt in to this manual demo; never part of automated discovery.",
    )
    args = parser.parse_args(argv)
    if not args.allow_web:
        parser.error("This demo requires --allow-web; no application was initialized.")
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))
    from scripts.run_tests import disposable_environment

    with disposable_environment():
        run_check()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

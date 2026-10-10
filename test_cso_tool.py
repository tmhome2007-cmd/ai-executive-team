"""Regression checks for cso tool."""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, LLM

# Ensure the root folder is accessible for project imports
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from config import config
from tools.research_tool import PageReaderTool

# 1. Load environment variables
load_dotenv()

# 2. Configure the LLM instance
ollama_llm = LLM(
    model=config.OLLAMA_MODEL,  # Uses model name from config
    base_url=config.OLLAMA_BASE_URL,  # Uses URL from config
)

# 3. Instantiate the web-reading tool
page_reader_tool = PageReaderTool()

# 4. Create the CSO Agent with English configuration and linked tool
cso_agent = Agent(
    role="Chief Strategy Officer (CSO)",
    goal="Analyze strategic information by strictly consulting provided external sources.",
    backstory="You are a data-driven CSO who bases decisions exclusively on external sources accessed via available tools.",
    tools=[page_reader_tool],  # Link tool to the agent
    llm=ollama_llm,
    verbose=True,
    allow_delegation=False,
)

# 5. Create Task with English instructions
target_url = "https://en.wikipedia.org/wiki/Artificial_intelligence"

task = Task(
    description=(
        f"Use the tool 'read_web_page' with url='{target_url}' to fetch the page content. "
        "Then, summarize the main definition of artificial intelligence from the text in 2-3 English sentences."
    ),
    expected_output="A concise 2-3 sentence summary in English based strictly on the fetched web page.",
    agent=cso_agent,
)

# 6. Run the Crew
crew = Crew(agents=[cso_agent], tasks=[task], verbose=True)

if __name__ == "__main__":
    print("=" * 60)
    print("STARTING CSO TOOL TEST (ENGLISH OUTPUT)")
    print("=" * 60)
    result = crew.kickoff()
    print("\nResult:")
    print(result)

# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.

"""
Multi-agent system that uses GitHub Search API to answer code-related queries.
The system consists of a Researcher agent that searches GitHub for information
and a Critic agent that reviews the report and provides feedback.
"""

import asyncio
import logging
import os
from dotenv import load_dotenv
from typing import List

from openai import AsyncAzureOpenAI
from semantic_kernel import Kernel
from semantic_kernel.agents import AgentGroupChat, ChatCompletionAgent
from semantic_kernel.agents.strategies import (
    KernelFunctionSelectionStrategy,
    KernelFunctionTerminationStrategy,
)
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion
from semantic_kernel.contents import ChatHistoryTruncationReducer
from semantic_kernel.functions import KernelFunctionFromPrompt

from sk_demo.github_api_plugin import GitHubPlugin
from sk_demo.publish_plugin import PublishPlugin

# Logging Setup
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Define agent names
RESEARCHER_NAME = "Researcher"
CRITIC_NAME = "Critic"
PUBLISHER_NAME = "Publisher"
AGENT_NAME = "GitHubSearchAgent"


RESEARCHER_INSTRUCTIONS = """
You are a Researcher agent that uses GitHub Search API to find information about code-related queries. 
Your goal is to search for relevant information on GitHub to help answer user questions. 

Process:
1. Analyze the user's query to identify key search terms.
2. Use the github.search_code function with precise queries to find relevant code examples on GitHub.
3. You MUST perform at least 4-5 different searches with different queries to gather comprehensive information.
4. After gathering sufficient information from GitHub, compile a detailed report.
5. When you receive feedback from the Critic, conduct additional searches to address gaps.

Be thorough, methodical, and focus on providing accurate technical information from real GitHub repositories.
"""

CRITIC_INSTRUCTIONS = """
You are a Critic agent that reviews reports compiled by the Researcher agent. 
Your goal is to ensure the report is comprehensive, accurate, and addresses the user's query completely.

Process:
1. Analyze the draft report provided by the Researcher.
2. Identify any gaps, inaccuracies, or areas that need improvement.
3. Provide specific, actionable feedback to the Researcher.
4. Look for:
   - Missing important information
   - Incorrect or outdated code examples
   - Lack of diversity in sources
   - Insufficient explanation or context
   - Areas where more examples would be helpful
5. When the report is satisfactory after multiple revisions, suggest publishing it as a Gist.

Be constructive but thorough in your criticism. When you're satisfied with the report after revisions,
end your feedback with the phrase "REPORT APPROVED FOR PUBLICATION".
"""

PUBLISHER_INSTRUCTIONS = """
You are a Publisher agent that prepares approved reports for publication.
Your role is to take the final report approved by the Critic and prepare it for publishing as a GitHub Gist.

Process:
1. Review the approved report one final time for formatting issues.
2. Create a clean title based on the original query.
3. Format the report in a way that's suitable for a GitHub Gist.
4. Include appropriate sections, code blocks, and explanations.
5. When ready to publish, call the publish.publish_gist function with the title and content.

Example usage:
publish.publish_gist(title="Informative Title", content="Full report content")

After calling the function, end your message with "READY TO PUBLISH" to indicate completion.
"""

SELECTION_PROMPT = f"""
Examine the provided RESPONSE and choose the next participant.
State only the name of the chosen participant without explanation.
Never choose the participant named in the RESPONSE.

Choose only from these participants:
- {RESEARCHER_NAME}
- {CRITIC_NAME}
- {PUBLISHER_NAME}

Rules:
- If RESPONSE is user input, it is {RESEARCHER_NAME}'s turn.
- If RESPONSE is by {RESEARCHER_NAME}, it is {CRITIC_NAME}'s turn.
- If RESPONSE is by {CRITIC_NAME} and contains "REPORT APPROVED FOR PUBLICATION", it is {PUBLISHER_NAME}'s turn.
- If RESPONSE is by {CRITIC_NAME} but does not contain approval, it is {RESEARCHER_NAME}'s turn.
- If RESPONSE is by {PUBLISHER_NAME}, the conversation is complete.

RESPONSE:
{{{{$lastmessage}}}}
"""

TERMINATION_PROMPT = """
Examine the RESPONSE and determine whether the conversation should terminate.
If the Publisher has completed preparation (containing "READY TO PUBLISH"), respond with "terminate".
Otherwise, respond with "continue".

RESPONSE:
{{{{$lastmessage}}}}
"""


# Initialize environment variables
load_dotenv(override=True)
APPROVER_EMAILS_STR = os.getenv("APPROVER_EMAILS")
if not APPROVER_EMAILS_STR:
    raise ValueError("APPROVER_EMAILS environment variable must be set (comma-separated).")
APPROVERS = [e.strip() for e in APPROVER_EMAILS_STR.split(',')]

# Conversation state to track searches, reports, etc.
class ConversationState:
    """
    Holds the state for a single conversation, including user query,
    searches made, final report, etc.
    """
    def __init__(self) -> None:
        self.query: str = ""
        self.searches: List[str] = []
        self.report: str = ""
        self.feedback: List[str] = []
        self.final_report: str = ""

# Global state instance
conversation_state = ConversationState()

def validate_env_vars() -> List[str]:
    """
    Validates required environment variables and returns a list of approved emails.
    Raises ValueError if missing critical values.
    """
    azure_openai_key = os.getenv("AZURE_OPENAI_API_KEY")
    azure_openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    if not azure_openai_key:
        raise ValueError("AZURE_OPENAI_API_KEY environment variable must be set.")
    if not azure_openai_endpoint:
        raise ValueError("AZURE_OPENAI_ENDPOINT environment variable must be set.")

    approver_emails_str = os.getenv("APPROVER_EMAILS")
    if not approver_emails_str:
        raise ValueError("APPROVER_EMAILS environment variable must be set (comma-separated).")

    approvers = [e.strip() for e in approver_emails_str.split(',') if e.strip()]
    if not approvers:
        raise ValueError("No valid approvers found in APPROVER_EMAILS.")

    return approvers


def create_kernel() -> Kernel:
    """Creates a Kernel instance with Azure OpenAI ChatCompletion service."""
    kernel = Kernel()
    
    # Use validate_env_vars to validate environment variables
    validated_approvers = validate_env_vars()
    
    # Check if global APPROVERS needs to be updated
    global APPROVERS
    if validated_approvers:
        APPROVERS = validated_approvers
    
    # Configure Azure OpenAI service
    chat_client = AsyncAzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2023-05-15"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
    )
    chat_completion_service = OpenAIChatCompletion(
        ai_model_id=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o"),
        async_client=chat_client
    )
    kernel.add_service(chat_completion_service)

    return kernel


def init_agents(kernel: Kernel):
    """
    Creates three ChatCompletionAgent instances for Researcher, Critic, and Publisher.
    Returns them as a tuple.
    """

    
    agent_researcher = ChatCompletionAgent(
        kernel=kernel,
        name=RESEARCHER_NAME,
        instructions=RESEARCHER_INSTRUCTIONS,
        plugins=[GitHubPlugin()]
    )

    agent_critic = ChatCompletionAgent(
        kernel=kernel,
        name=CRITIC_NAME,
        instructions=CRITIC_INSTRUCTIONS,
    )

    agent_publisher = ChatCompletionAgent(
        kernel=kernel,
        name=PUBLISHER_NAME,
        instructions=PUBLISHER_INSTRUCTIONS,
        plugins=[
            PublishPlugin(
                agent_name=AGENT_NAME,
                approvers=APPROVERS,
                conversation_state=conversation_state
            )
        ]
    )

    return agent_researcher, agent_critic, agent_publisher

def build_agent_group_chat(
    kernel: Kernel,
    agent_researcher: ChatCompletionAgent,
    agent_critic: ChatCompletionAgent,
    agent_publisher: ChatCompletionAgent
) -> AgentGroupChat:
    """
    Constructs the AgentGroupChat with selection and termination strategies.
    """
    selection_function = KernelFunctionFromPrompt(
        function_name="selection",
        prompt=SELECTION_PROMPT,
    )

    termination_function = KernelFunctionFromPrompt(
        function_name="termination",
        prompt=TERMINATION_PROMPT,
    )

    history_reducer = ChatHistoryTruncationReducer(target_count=10)

    chat = AgentGroupChat(
        agents=[agent_researcher, agent_critic, agent_publisher],
        selection_strategy=KernelFunctionSelectionStrategy(
            initial_agent=agent_researcher,
            function=selection_function,
            kernel=kernel,
            result_parser=lambda result: str(result.value[0]).strip() if result.value[0] else RESEARCHER_NAME,
            history_variable_name="lastmessage",
            history_reducer=history_reducer,
        ),
        termination_strategy=KernelFunctionTerminationStrategy(
            agents=[agent_publisher],
            function=termination_function,
            kernel=kernel,
            result_parser=lambda result: "terminate" in str(result.value[0]).lower(),
            history_variable_name="lastmessage",
            maximum_iterations=20,
            history_reducer=history_reducer,
        ),
    )
    return chat

async def run_conversation_loop(chat: AgentGroupChat) -> None:
    """
    Runs the main conversation loop, prompting for user input,
    invoking the multi-agent pipeline, and printing results.
    """
    logger.info("Starting GitHub Search Agent Demo...")
    logger.info(f"Agent Name: {AGENT_NAME}")

    # Print approvers from environment
    approver_emails_str = os.getenv("APPROVER_EMAILS")
    logger.info(f"Approvers: {approver_emails_str}")

    logger.info("Please enter a code-related query or type 'exit' to quit.")

    is_complete = False

    while not is_complete:
        print()
        if not conversation_state.query:
            user_input = input("Query > ").strip()
            conversation_state.query = user_input
        else:
            user_input = input("Press Enter to continue or 'exit' to quit > ").strip()
            if not user_input:
                user_input = "Continue processing the query."

        if user_input.lower() == "exit":
            logger.info("Exiting conversation loop.")
            break

        if user_input.lower() == "reset":
            await chat.reset()
            logger.info("[Conversation has been reset]")
            # Reset conversation state
            conversation_state.__init__()  # re-init fields
            continue

        await chat.add_chat_message(message=user_input)

        try:
            async for response in chat.invoke():
                if response is None or not response.name:
                    continue

                print()
                print(f"# {response.name.upper()}:\n{response.content}")

                # If the Publisher agent says "READY TO PUBLISH", end the loop
                if response.name == PUBLISHER_NAME and "READY TO PUBLISH" in response.content:
                    is_complete = True
                    break

        except Exception as exc:
            logger.exception(f"Error during chat invocation: {exc}")
            break

    # Final summary
    print("\n--- Demo Finished ---")
    if conversation_state.final_report:
        logger.info("Final Report Published Successfully.")
    else:
        logger.info("No final report was generated.")

async def main() -> None:
    """
    Orchestrates the entire flow:
    1. Loads environment variables
    2. Creates a Kernel
    3. Initializes agents
    4. Builds an AgentGroupChat
    5. Runs the conversation loop
    """
    load_dotenv(override=True)
    kernel = create_kernel()
    agent_researcher, agent_critic, agent_publisher = init_agents(kernel)
    chat = build_agent_group_chat(kernel, agent_researcher, agent_critic, agent_publisher)
    await run_conversation_loop(chat)

if __name__ == "__main__":
    asyncio.run(main())

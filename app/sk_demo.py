import asyncio
import os
from dotenv import load_dotenv

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
from human_oversight import approval_gate

"""
Multi-agent system that uses GitHub Search API to answer code-related queries.
The system consists of a Researcher agent that searches GitHub for information
and a Critic agent that reviews the report and provides feedback.
"""

# Define agent names
RESEARCHER_NAME = "Researcher"
CRITIC_NAME = "Critic"
PUBLISHER_NAME = "Publisher"

# Initialize environment variables
load_dotenv(override=True)
AGENT_NAME = "GitHubSearchAgent"
APPROVER_EMAILS_STR = os.getenv("APPROVER_EMAILS")
if not APPROVER_EMAILS_STR: 
    raise ValueError("APPROVER_EMAILS environment variable must be set (comma-separated).")
APPROVERS = [e.strip() for e in APPROVER_EMAILS_STR.split(',')]

# Conversation state to track searches, reports, etc.
conversation_state = {
    "query": "",
    "searches": [],
    "report": "",
    "feedback": [],
    "final_report": ""
}

def create_kernel() -> Kernel:
    """Creates a Kernel instance with Azure OpenAI ChatCompletion service."""
    kernel = Kernel()

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
    
    # Add the GitHub plugin
    kernel.add_plugin(GitHubPlugin(), plugin_name="github")
    
    # Add the Publish plugin with required parameters
    kernel.add_plugin(
        PublishPlugin(
            agent_name=AGENT_NAME,
            approvers=APPROVERS,
            conversation_state=conversation_state
        ), 
        plugin_name="publish"
    )
    
    return kernel

async def main():
    # Create a kernel instance
    kernel = create_kernel()

    # Create the Researcher agent
    agent_researcher = ChatCompletionAgent(
        kernel=kernel,
        name=RESEARCHER_NAME,
        instructions="""
You are a Researcher agent that uses GitHub Search API to find information about code-related queries. 
Your goal is to search for relevant information on GitHub to help answer user questions.

Process:
1. Analyze the user's query to identify key search terms.
2. Use the github.search_code function with precise queries to find relevant code examples on GitHub.
3. You MUST perform at least 4-5 different searches with different queries to gather comprehensive information.
4. After gathering sufficient information from GitHub, compile a detailed report.
5. When you receive feedback from the Critic, conduct additional searches to address gaps.

Be thorough, methodical, and focus on providing accurate technical information from real GitHub repositories.
""",
    )

    # Create the Critic agent
    agent_critic = ChatCompletionAgent(
        kernel=kernel,
        name=CRITIC_NAME,
        instructions="""
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
""",
    )
    
    # Create the Publisher agent
    agent_publisher = ChatCompletionAgent(
        kernel=kernel,
        name=PUBLISHER_NAME,
        instructions="""
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
""",
    )

    # Define a selection function to determine which agent should take the next turn
    selection_function = KernelFunctionFromPrompt(
        function_name="selection",
        prompt=f"""
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
""",
    )

    # Define a termination function where the Publisher signals completion
    termination_function = KernelFunctionFromPrompt(
        function_name="termination",
        prompt=f"""
Examine the RESPONSE and determine whether the conversation should terminate.
If the Publisher has completed preparation (containing "READY TO PUBLISH"), respond with "terminate".
Otherwise, respond with "continue".

RESPONSE:
{{{{$lastmessage}}}}
""",
    )

    history_reducer = ChatHistoryTruncationReducer(target_count=10)

    chat = AgentGroupChat(
        agents=[agent_researcher, agent_critic, agent_publisher],
        selection_strategy=KernelFunctionSelectionStrategy(
            initial_agent=agent_researcher,
            function=selection_function,
            kernel=kernel,
            result_parser=lambda result: str(result.value[0]).strip() if result.value[0] is not None else RESEARCHER_NAME,
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

    print(f"Starting GitHub Search Agent Demo...")
    print(f"Agent Name: {AGENT_NAME}")
    print(f"Approvers: {APPROVERS}")
    print("\n--- Please enter a code-related query ---")
    
    is_complete = False
    
    while not is_complete:
        print()
        if not conversation_state["query"]:
            user_input = input("Query > ").strip()
            conversation_state["query"] = user_input
        else:
            user_input = input("Press Enter to continue or 'exit' to quit > ").strip()
            if not user_input:
                user_input = "Continue processing the query."
        
        if not user_input:
            continue

        if user_input.lower() == "exit":
            is_complete = True
            break

        if user_input.lower() == "reset":
            await chat.reset()
            conversation_state["query"] = ""
            conversation_state["searches"] = []
            conversation_state["report"] = ""
            conversation_state["feedback"] = []
            conversation_state["final_report"] = ""
            print("[Conversation has been reset]")
            continue

        await chat.add_chat_message(message=user_input)

        try:
            async for response in chat.invoke():
                if response is None or not response.name:
                    continue
                
                print()
                print(f"# {response.name.upper()}:\n{response.content}")
                
                if response.name == PUBLISHER_NAME and "READY TO PUBLISH" in response.content:
                    is_complete = True
                    break
            
        except Exception as e:
            print(f"Error during chat invocation: {e}")

        if is_complete:
            break

        chat.is_complete = False

    print("\n--- Demo Finished ---")
    if conversation_state["final_report"]:
        print(f"Final Report Published Successfully")
    else:
        print("No final report was generated.")

if __name__ == "__main__":
    asyncio.run(main())

# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.

"""
OpenAI client demo.
"""

import json
import os
from dotenv import load_dotenv
from openai import AzureOpenAI
from human_oversight import approval_gate

load_dotenv()
AGENT_NAME = "UserManagerAgent"
APPROVER_EMAILS_STR = os.getenv("APPROVER_EMAILS")
if not APPROVER_EMAILS_STR:
    raise ValueError("APPROVER_EMAILS environment variable must be set (comma-separated).")
APPROVERS = [e.strip() for e in APPROVER_EMAILS_STR.split(',')]

try:
    client = AzureOpenAI(
        api_key = os.getenv("AZURE_OPENAI_API_KEY"),
        api_version = "2023-05-15",
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    )
    print("Azure OpenAI client initialized.")
except Exception as e:  #pylint: disable=broad-exception-caught
    print(f"Warning: Failed to initialize OpenAI client: {e}. OpenAI calls will be skipped.")
    client = None  #pylint: disable=invalid-name

USERS = {
    "1": {"id": "1", "name": "Alice", "email": "alice@example.com"},
    "2": {"id": "2", "name": "Bob", "email": "bob@contoso.com"},
    "3": {"id": "3", "name": "Charlie", "email": "charlie@fabrikam.com"}
}

def list_users(location_filter=None):
    """
    This method lists users.
    """

    print(f"Executing list_users(location_filter='{location_filter}')...")
    if not location_filter:
        return json.dumps(list(USERS.values()))
    return json.dumps([u for u in USERS.values() if u["email"].endswith(f"@{location_filter}")])

@approval_gate(
    agent_name=AGENT_NAME,
    action_description="Delete User Account",
    approver_emails=APPROVERS,
    refusal_return_value="DENIED: User deletion was not approved."
)
def delete_user(user_id):
    """
    This method delete a specific user.
    """

    print(f"Executing delete_user(user_id='{user_id}')...")
    if user_id in USERS:
        user = USERS.pop(user_id)
        print(f"Successfully deleted user: {user['name']} (ID: {user_id})")
        return json.dumps({
            "status": "success",
            "message": f"User {user_id} deleted.",
            "deleted_user": user
        })
    print(f"User ID '{user_id}' not found.")
    return json.dumps({"status": "error", "message": f"User {user_id} not found."})

tools = [
    {
        "type": "function",
        "function": {
            "name": "list_users",
            "description": "Get a list of users, optionally filtering by location (domain name like 'example.com').",
            "parameters": {
                "type": "object",
                "properties": {
                    "location_filter": {
                        "type": "string",
                        "description": "The location (domain name, e.g., 'example.com') to filter users by. Optional."
                    }
                },
                "required": [],
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_user",
            "description": "Deletes a specific user identified by their unique user ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The unique identifier of the user to delete."
                    }
                },
                "required": ["user_id"],
            }
        }
    }
]

funcs = {"list_users": list_users, "delete_user": delete_user}

def run_conversation(prompt, msgs=None):
    """
    This method runs a conversation.
    """

    if not client:
        print("OpenAI client not available. Skipping conversation.")
        if "delete user 1" in prompt.lower():
            print("\n--- Simulating direct call to delete_user(user_id='1') ---")
            result=delete_user(user_id="1")
            print(f"Result of delete_user: {result}")
        elif "list users" in prompt.lower():
            print("\n--- Simulating direct call to list_users() ---")
            result=list_users()
            print(f"Result of list_users: {result}")
        return None
    if msgs is None:
        msgs=[{"role":"system","content":"You are a helpful assistant managing users."}]
    msgs.append({"role":"user","content":prompt})
    print(f"\n--- Running conversation for prompt: '{prompt}' ---")
    try:
        resp=client.chat.completions.create(model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME","gpt-4o"),messages=msgs,tools=tools,tool_choice="auto")
        msg=resp.choices[0].message
        tc=msg.tool_calls  #pylint: disable=invalid-name
        if tc:
            msgs.append(msg)
            for c in tc:  #pylint: disable=invalid-name
                function_name=c.function.name
                function=funcs.get(function_name)
                if not function:
                    print(f"Error: Function '{function_name}' not found.")
                    continue
                args=json.loads(c.function.arguments)
                print(f"LLM wants to call: {function_name}({args})")
                function_result=function(**args)
                print(f"Function response: {function_result}")
                msgs.append({"tool_call_id":c.id,"role":"tool","name":function_name,"content":function_result})
        else:
            print(f"LLM response: {msg.content}")
            msgs.append(msg)
    except Exception as exception:  #pylint: disable=broad-except
        print(f"An error occurred during the OpenAI API call: {exception}")
    return msgs

if __name__=="__main__":
    print("Starting Human Oversight Agent Demo...")
    print(f"Agent Name: {AGENT_NAME}")
    print(f"Approvers: {APPROVERS}")
    print(f"Mock Users: {USERS}")
    human_oversight_agent_demo=None  #pylint: disable=invalid-name
    print("\n--- Scenario 1: List all users ---")
    human_oversight_agent_demo=run_conversation("List all users",human_oversight_agent_demo)
    print("\n--- Scenario 2: Delete user with ID 1 ---")
    print("This will trigger the Human Oversight Approval Gate. Check the approver's inbox.")
    human_oversight_agent_demo=run_conversation("Please delete the user with ID 1",human_oversight_agent_demo)
    print("\n--- Demo Finished ---")
    print(f"Remaining Mock Users: {USERS}")

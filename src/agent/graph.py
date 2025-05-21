"""LangGraph single-node graph template.

Returns a predefined response. Replace logic and configuration as needed.
"""

from __future__ import annotations


from typing import TypedDict

from langgraph.graph import StateGraph


import os
from dotenv import load_dotenv
import google.generativeai as genai

from langchain_google_genai import ChatGoogleGenerativeAI

from langgraph.prebuilt import  ToolNode, tools_condition
from langchain_core.tools import tool
from typing import TypedDict,  Optional
from langgraph.graph import StateGraph, END
from langchain_core.messages import  AIMessage
    
from typing import TypedDict, Optional, List
from langchain_core.messages import  BaseMessage


from langchain_core.messages import AIMessage


from src.agent.tools import call_register_user, call_confirm_registration
from src.agent.prompts import prompt_unregister



load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=api_key)

llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", api_key=api_key)



class AgentState(TypedDict):
    status: str
    user_id: Optional[str]
    messages: List[BaseMessage]

def default_agent_state() -> AgentState:
    return {
        "status": "unregistered",
        "user_id": None,
        "messages": []
    }    





tools = [call_register_user, call_confirm_registration]
llm_with_tools = llm.bind_tools(tools)


    
def categorizer(state: AgentState) -> AgentState:
    last_message = state.get("messages", [])[-1]["content"].lower() if state.get("messages") else ""

    # Use .get() with default to prevent KeyError
    status = state.get("status", "unregistered")
    
    if "book" in last_message or "appointment" in last_message:
        if status == "unregistered":
            print("User wants to book but is unregistered.")
        else:
            print("User wants to book and is already registered.")
    
    return {
        "status": status,
        "user_id": state.get("user_id"),
        "messages": state.get("messages", [])
    }







def unregister_node(state: AgentState) -> AgentState:
    print("🔐 unregister node...")


    user_msg = state["messages"][-1]["content"].lower()
    
    updated_messages = state["messages"]


    if "yes" in user_msg or "register me" in user_msg:
        result = call_register_user.invoke({})
        if result.get("user_id"):
            updated_messages.append(AIMessage(content=f"✅ Registration started. Please fill the form: https://fak_form.com?user_id={result['user_id']}"))
            return {
                "status": "registered",  # ✅ Set status to registered
                "user_id": result["user_id"],  # ✅ Assign the ID
               
                "messages": updated_messages
            }


    response = llm_with_tools.invoke([prompt_unregister] + state["messages"])
    return {
        **state,
        "messages": updated_messages + [response]
    }




def register_node(state: AgentState) -> AgentState:
    print("register node...")
    state["messages"].append(AIMessage(content="Welcome back! What would you like to do?"))
    return state


def categorizer_router(state: AgentState) -> str:
    return "register" if state["status"] == "registered" else "unregister"





builder = StateGraph(AgentState)

builder.add_node("categorizer", categorizer)
builder.add_node("unregister", unregister_node)
builder.add_node("register", register_node)
builder.add_node('tools', ToolNode(tools))


builder.set_entry_point("categorizer")
builder.add_conditional_edges("categorizer", categorizer_router, {
    "register": "register",
    "unregister": "unregister"
})


builder.add_conditional_edges('unregister', tools_condition)
builder.add_edge('tools', 'unregister')




builder.add_edge("register", END)
builder.add_edge("unregister", END)

state = default_agent_state()
graph = builder.compile()





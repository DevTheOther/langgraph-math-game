from typing import Annotated
from typing_extensions import TypedDict

from langchain_openai import ChatOpenAI
# from langchain_community.tools.tavily_search import TavilySearchResults

from langgraph.graph import StateGraph, START, MessagesState, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.message import add_messages
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from pydantic import BaseModel, Field
# from langgraph.prebuilt import ToolNode, tools_condition
# from noetic_game.state import InputState
# from src.noetic_game.state import InputState

from dotenv import load_dotenv
load_dotenv(".env")

memory = MemorySaver()

class GameState(TypedDict):
    messages: Annotated[list, add_messages]
    grade: int
    against_ai: bool
    ai_score: int
    user_score: int
    num_questions: int

class CorrectnessTool(BaseModel):
    correct: bool = Field(description="Whether the answer is correct or not")
    prompt_reponse: str = Field(description="Prompt response")
    
    
graph_builder = StateGraph(GameState)

# web_search_tool = TavilySearchResults(max_results=2)
# tools = [web_search_tool]
llm1 = ChatOpenAI(model="gpt-4o-mini")
llm2 = ChatOpenAI(model="gpt-4o-mini")
llm3 = ChatOpenAI(model="gpt-4o-mini", temperature=0.1)
llm3_with_correctness = llm3.with_structured_output(CorrectnessTool, include_raw=True)

# llm_with_tools = llm.bind_tools(tools)

### Nodes

def math_teacher_agent(state: GameState):
    """Math teacher agent"""
    print("math_teacher_agent")
    messages = [SystemMessage(content="You are an elementary teacher. Provide 4th grade math questions one at a time.")] + state["messages"]
    # for message in messages:
    #     print(message.pretty_print())
    response = llm1.invoke(messages)
    
    # print(response.content)
    # response.pretty_print()
    question_number = state.get("num_questions", 0)
    question_number = question_number + 1
    
    print("question_number: ", question_number)
    return {"messages": [response], "num_questions": question_number}

def math_student_agent(state: GameState):
    """Call research agent"""
    print("math_student_agent")
    messages = [SystemMessage(content="You are a poorly performing elementary school student. You will get half of your answers incorrect.")] + state["messages"]
    # for message in messages:
    #     print(message.pretty_print())
    response = llm1.invoke(messages)
 
    # response.pretty_print()
    return {"messages": [response]}

def math_grader_agent(state: GameState):
    """Math teacher agent"""
    print("math_teacher_agent")
    
    messages = [SystemMessage(content="You are an elementary teacher's assistant. Grade the students answer for correctness, provide the approach to find the correct solution, and ask the studen if they would like to continue with another question")] + state["messages"]

    # for message in messages:
    #     print(message.pretty_print())

    response = llm3_with_correctness.invoke(messages)

    # print("response raw", response["raw"])
    is_correct = response["raw"].tool_calls[-1]["args"]["correct"]
    
    user_score = state.get("user_score", 0)
    if is_correct:
        print("correct")
        user_score = user_score + 1
    
    print("user_score: ", user_score)
    return {"messages": [AIMessage(response["raw"].tool_calls[-1]["args"]["prompt_reponse"])], "user_score": user_score}

def human_input(state: GameState):
    print("human_input")
    pass

### Edges

def should_restart(state: GameState):
    # Define the condition to restart or end
    # print("human_input: ", state["messages"][-1].content)
    
    user_message = state["messages"][-1].content
    messages = [HumanMessage(content=user_message)]
    messages = [SystemMessage(content="Checking just the last human input, determine whether the person wants to continue responding in one of two ways, 'yes' or 'no'.")] + messages

    for message in messages:
        print(message.pretty_print())

    response = llm2.invoke(messages)

    # print("LAST MESSAGE", response.content)
    if response.content.lower() == "yes":
        print("RESTART")
        return "math_teacher_agent"
    else:
        print("END")
        return "end"


graph_builder.add_node("math_teacher_agent", math_teacher_agent)
graph_builder.add_node("math_student_agent", math_student_agent)
graph_builder.add_node("math_grader_agent", math_grader_agent)
graph_builder.add_node("human_feedback", human_input)
graph_builder.add_edge("math_teacher_agent", "math_student_agent")
graph_builder.add_edge("math_student_agent", "math_grader_agent")
graph_builder.add_edge("math_grader_agent", "human_feedback")

graph_builder.add_conditional_edges(
    "human_feedback",
    should_restart,
    {
        "math_teacher_agent": "math_teacher_agent",
        "end": END
    }
)

# tool_node = ToolNode(tools=[web_search_tool])
# graph_builder.add_node("tools", tool_node)

# graph_builder.add_conditional_edges(
#     "chatbot",
#     tools_condition
# )

# graph_builder.add_edge("tools", "chatbot")
graph_builder.add_edge(START, "math_teacher_agent")

graph = graph_builder.compile(
    checkpointer=memory,
    interrupt_before=["human_feedback"]
)

config = {"configurable": {"thread_id": "1"}}

def process_input(user_input: str):
    events = graph.stream(
        {"messages": [("user", user_input)]},
        config,
        stream_mode="values"
    )
    
    # last_event = list(events)[-1]
    # last_event["messages"][-1].pretty_print()
    
    for event in events:
        try:
            event["messages"][-1].pretty_print()
        except:
            pass
    
    return
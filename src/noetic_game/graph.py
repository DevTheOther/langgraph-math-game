from typing import Annotated
from typing_extensions import TypedDict

from langchain_openai import ChatOpenAI
# from langchain_community.tools.tavily_search import TavilySearchResults

from langgraph.graph import StateGraph, START, MessagesState, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.message import add_messages
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
from pydantic import BaseModel, Field

from dotenv import load_dotenv
load_dotenv(".env")

memory = MemorySaver()

class GameState(BaseModel):
    messages: Annotated[list, add_messages] = [{"content": "Welcome to the math game! You will be asked 4th grade math questions. You will be graded on your answers. Would you like to start?", "sender": "system"}]
    grade: int = 4
    against_ai: bool = True
    ai_score: int = 0
    user_score: int = 0
    num_questions: int = 0    

class CorrectnessTool(BaseModel):
    correct: bool = Field(description="Whether the answer is correct or not")
    prompt_reponse: str = Field(description="Prompt response")
    
    
graph_builder = StateGraph(GameState)

# web_search_tool = TavilySearchResults(max_results=2)
# tools = [web_search_tool]
llm1 = ChatOpenAI(model="gpt-4o")
llm2 = ChatOpenAI(model="gpt-4o")
llm3 = ChatOpenAI(model="gpt-4o")
llm = ChatOpenAI(model="gpt-4o")
llm_with_correctness = llm.with_structured_output(CorrectnessTool, include_raw=True)

# llm_with_tools = llm.bind_tools(tools)

### Nodes

def math_teacher_agent(state: GameState):
    """Math teacher agent"""
    # print("math_teacher_agent")
    messages = [SystemMessage(content="You are an elementary teacher. Provide 4th grade math questions one at a time.")] + state.messages
    # for message in messages:
    #     print(message.pretty_print())
    response = llm1.invoke(messages)
    temp_response = response
    temp_response.content = "Math Teacher:\n" + temp_response.content
    # print(response.content)
    # response.pretty_print()
    question_number = state.num_questions + 1
    
    print("question_number: ", question_number)
    print("ai_score: ", state.ai_score)
    print("user_score: ", state.user_score)
    temp_response.pretty_print()
    return {"messages": [response], "num_questions": question_number}

def math_student_agent(state: GameState):
    """Call research agent"""
    print("math_student_agent")
    messages = [SystemMessage(content="You are a poorly performing elementary school student. You will get half of your answers incorrect.")] + state.messages
    # for message in messages:
    #     print(message.pretty_print())
    response = llm2.invoke(messages)
    temp_response = response
    temp_response.content = "AI Student:\n" + temp_response.content
    temp_response.pretty_print()
    return {"messages": [response]}

def math_grader_agent(state: GameState):
    """Math teacher agent"""
    print("math_teacher_agent")
    
    messages = [SystemMessage(content="You are an elementary teacher's assistant. Grade the students answer for correctness, provide the approach to find the correct solution, and ask the studen if they would like to continue with another question")] + state.messages

    # for message in messages:
    #     print(message.pretty_print())

    response = llm_with_correctness.invoke(messages)
    temp_response = AIMessage(response["raw"].tool_calls[-1]["args"]["prompt_reponse"])
    # print("response raw", response["raw"])
    is_correct = response["raw"].tool_calls[-1]["args"]["correct"]
    temp_response.content = "Math Grader:\n" + temp_response.content
    print("is_correct: ", is_correct)
    if is_correct:
        if state.against_ai and state.num_questions % 2 == 0:
            print("ai was correct")
            state.ai_score = state.ai_score + 1
        else:
            print("you are correct")
            state.user_score = state.user_score + 1
    
    print("ai_score: ", state.ai_score)
    print("user_score: ", state.user_score)
    temp_response.pretty_print()
    return {"messages": [AIMessage(response["raw"].tool_calls[-1]["args"]["prompt_reponse"])], "user_score": state.user_score, "ai_score": state.ai_score}

def human_input(state: GameState):
    print("human_input")
    pass

def human_answer(state: GameState):
    print("human_answer")
    pass

### Edges

def choose_student(state: GameState):
    if state.against_ai and state.num_questions % 2 == 0:
        print("its the ai agents turn")
        return "math_student_agent"
    else:
        print("its your turn")
        return "human_answer"

def should_restart(state: GameState):
    # Define the condition to restart or end
    # print("human_input: ", state["messages"][-1].content)
    print("should_restart: ", state.messages[-1].content)
    user_message = state.messages[-1].content

    messages = [SystemMessage(content="Checking just the last human input, determine whether the person wants to continue responding in one of two ways, 'yes' or 'no'.")]
    messages = [HumanMessage(content=user_message)] + messages
    
    # for message in messages:
    #     message.pretty_print()

    response = llm3.invoke(messages)

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
graph_builder.add_node("human_input", human_input)
graph_builder.add_node("human_answer", human_answer)
graph_builder.add_edge("math_student_agent", "math_grader_agent")
graph_builder.add_edge("math_grader_agent", "human_input")


graph_builder.add_conditional_edges(
    "math_teacher_agent",
    choose_student,
    {
        "math_student_agent": "math_student_agent",
        "human_answer": "human_answer"
    }
)

graph_builder.add_conditional_edges(
    "human_input",
    should_restart,
    {
        "math_teacher_agent": "math_teacher_agent",
        "end": END
    }
)

graph_builder.add_edge("human_answer", "math_grader_agent")
graph_builder.add_edge(START, "math_teacher_agent")

graph = graph_builder.compile(
    checkpointer=memory,
    interrupt_before=["human_input", "human_answer"],
)

config = {"configurable": {"thread_id": "1"}}

def process_input(user_input: str):
    print("user_input", user_input)
    events = graph.stream(
        {"messages": [("user", user_input)]},
        config,
        stream_mode="values",
        debug=True
    )
    
    # last_event = list(events)[-1]
    # last_event["messages"][-1].pretty_print()
    
    for event in events:
        try:
            pass
            # event["messages"][-1].pretty_print()
        except:
            print("exception")
            pass
    
    return
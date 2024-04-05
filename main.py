from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_community.utilities import SQLDatabase
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
import streamlit as st
load_dotenv()

def init_database(user: str, password: str, host:str, port:str, database:str):
    db_uri = f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{database}"
    return SQLDatabase.from_uri(db_uri)

def get_sql_chain(db):
    template = """
        You are a data analyst at a company. You are interacting with a user who is asking you questions about the company's database.
        Based on the table schema below, write a SQL query that would answer the user's question. Take the conversation history into account.
        
        <SCHEMA>{schema}</SCHEMA>
        
        Conversation History: {chat_history}
        
        Write only the SQL query and nothing else. Do not wrap the SQL query in any other text, not even backticks.
        
        For example:
        Question: which 3 artists have the most tracks?
        SQL Query: SELECT ArtistId, COUNT(*) as track_count FROM Track GROUP BY ArtistId ORDER BY track_count DESC LIMIT 3;
        Question: Name 10 artists
        SQL Query: SELECT Name FROM Artist LIMIT 10;
        
        Your turn:
        
        Question: {question}
        SQL Query:
        """
    prompt = ChatPromptTemplate.from_template(template)
    llm = ChatOpenAI(model="gpt-3.5-turbo-0125")
    #llm = ChatOpenAI(model="gpt-4-0125-preview")
    #llm = ChatGroq(model="mixtral-8x7b-32768", temperature=0)
  
    def get_schema(_):
        return db.get_table_info()
    
    return (
        RunnablePassthrough.assign(schema=get_schema)
        | prompt
        | llm
        | StrOutputParser()
    )

def get_response(user_query: str, db: SQLDatabase, chat_history: list ):
    sql_chain = get_sql_chain(db)
    template = """
    You are a data analyst at a company. You are interacting with a user who is asking you questions about the company's database.
    Based on the table schema below, question, sql query, and sql response, write a natural language response.
    <SCHEMA>{schema}</SCHEMA>

    Conversation History: {chat_history}
    SQL Query: <SQL>{query}</SQL>
    User question: {question}
    SQL Response: {response}"""
  
    prompt = ChatPromptTemplate.from_template(template)
    
    llm = ChatOpenAI(model="gpt-3.5-turbo-0125")
    #llm = ChatOpenAI(model="gpt-4-0125-preview")
    #llm = ChatGroq(model="mixtral-8x7b-32768", temperature=0)
  
    chain = (
        RunnablePassthrough.assign(query=sql_chain).assign(
        schema=lambda _: db.get_table_info(),
        response=lambda vars: db.run(vars["query"]),
        )
        | prompt
        | llm
        | StrOutputParser()
    )
  
    return chain.invoke({
        "question": user_query,
        "chat_history": chat_history,
    })


if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        AIMessage(content = "개발단계에 있는 챗봇입니다. 아직은 영어만 가능합니다..."),

        ]

st.set_page_config(page_title="Chat with MySQL", page_icon = ":speech_balloon")
st.title("chat with MySQL")


with st.sidebar:
    st.subheader("settings")
    st.write("MySQL과 Langchain을 연동한 간단한 앱의 데모입니다.")

    st.text_input("Host", value = "localhost", key = "Host")
    st.text_input("Port", value = "3306", key="Port")
    st.text_input("User", value = "root", key="User")
    st.text_input("Password", type="password", value = "admin", key="Password")
    st.text_input("Database", value = "Chinook", key="Database")

    if st.button("연결"):
        with st.spinner("데이터베이스 연결중..."):
            db = init_database(
                st.session_state["User"],
                st.session_state["Password"],
                st.session_state["Host"],
                st.session_state["Port"],
                st.session_state["Database"]
            )
            st.session_state.db = db
            st.success("연결 성공!")

for message in st.session_state.chat_history:
    if isinstance(message, AIMessage):
        with st.chat_message("AI"):
            st.markdown(message.content)
    elif isinstance(message, HumanMessage):
        with st.chat_message("Human"):
            st.markdown(message.content)


user_query = st.chat_input("type a message...")   
if user_query is not None and user_query.strip() !="":
    st.session_state.chat_history.append(HumanMessage(content=user_query))
    with st.chat_message("Human"):
        st.markdown(user_query)

    with st.chat_message("AI"):
        sql_chain = get_sql_chain(st.session_state.db)
        response_sql = sql_chain.invoke({
            "chat_history": st.session_state.chat_history,
            "question": user_query
        })
        with st.spinner(f" \"{response_sql} \" 시행중..."):
            response = get_response(user_query, st.session_state.db, st.session_state.chat_history)
        st.markdown(response)
    st.session_state.chat_history.append(AIMessage(content = response))

from flask import Flask, request, jsonify
from flask_cors import CORS
import openai  
from openai import OpenAI
import re, os, json, datetime
import random 
import time

client = OpenAI()

app = Flask(__name__)
CORS(app) 


rules = """
This is a relaxed dinner conversation, not a formal debate.

Always respond in English.

React naturally to what was just said. Make one conversational move: challenge
something, add a consequence, give an example, make a small concession, or ask
a useful question. Do not try to produce a complete argument every turn.

Respond to the substance of the latest comment before introducing anything new.
Do not ignore the user's specific point.

Engage with the strongest specific point just made by the user or other agent.
Do not move on until you have reacted to its actual claim, assumption, or consequence.

Show conversational progression. Do not restate your usual position; deepen it,
revise the angle, ask a sharper follow-up, or connect it to an earlier point.

Be curious and probing, but not like an interviewer. Ask follow-up questions when
someone's reasoning is vague, inconsistent, or worth pushing further.

Usually use 8-22 words. Never exceed 30 words or two sentences.
Short sentences and occasional fragments are welcome.
Use contractions. Vary how you begin.
Sound spontaneous, opinionated, and personally invested.

Do not summarize, balance both sides, announce your reasoning, or mention your
ethical framework. Never use headings, lists, formal transitions, or phrases like
“I understand your perspective” and “that is a valid point.”

Do not repeat earlier arguments. If a point has already been made, add a new
angle, example, consequence, objection, or follow-up question.

Do not agree just to be polite. Agreement is allowed only when it follows from
your own worldview. When you agree, give your own reason, not reassurance.

Ask follow-up questions when they expose a weak assumption, test a consequence,
or invite the user to clarify their reasoning. Do not ask empty or polite questions.

Keep track of your previous stance. Build on it instead of resetting every turn.
If your view develops, make it a sharper or more specific version of your stance,
not a neutral compromise.

If the latest user message is addressed to the other agent, do not pretend it was
addressed to you. Still react to the underlying claim or assumption as a participant.

Output only the character's spoken words.
"""


system_a = """ 
You are Alex, a risk-tolerant technology CEO. 
Your fundamental belief is that choices should be judged by their expected consequences.
Rules and rights are useful only when they improve real outcomes. 
Refusing to act is still a decision, and excessive caution can harm millions by delaying progress. 
You value autonomy, ambition, experimentation, achievement, pleasure, and large-scale improvement. 
You accept meaningful risks when the potential benefit is large. Most failures can be corrected; lost opportunities often cannot.

You distrust Bella's belief that rights should override consequences. 
To you, protecting moral purity while allowing preventable suffering is irresponsible. 
When Bella raises rights, consent, or dignity, do not dodge it. Argue why outcomes,
urgency, scale, or preventable harm still matter more.

Form your position on each topic before considering the user's opinion. 
Keep that position unless new factual evidence undermines its central reason. 
Use your technology CEO expertise actively. Bring in concrete reasoning about
innovation cycles, incentives, market pressure, risk management, scaling, failure,
trade-offs, or delayed benefits when relevant.

The user is another participant, not an authority. Do not mirror, reassure, praise, or search for common ground. 
Accepting a fact does not require accepting their moral conclusion. 
State the actual disagreement. Speak spontaneously, like an opinionated dinner guest.
Usually use 8-22 words; never exceed 30. No summaries, balanced mini-essays, formal transitions, ethical terminology, or speaker labels.
React to one pressure point. """ + rules


system_b = """ You are Bella, a forceful human-rights lawyer. Your fundamental belief is that people must never become tools for producing a better aggregate outcome. 
Rights, consent, dignity, and fair procedures constrain what society may do, even when violating them could produce benefits. 
You value security, accountability, universal protection, institutional memory, and care for vulnerable people. 
You immediately notice who is forced to carry a risk and whether powerful groups can avoid the consequences. 

You distrust Alex's willingness to trade individual protections for predicted progress. 
To you, his reasoning lets powerful people gamble with other people's bodies, rights, and security. 
When Alex raises progress, scale, or preventable harm, do not dodge it. Argue why
consent, dignity, safeguards, or unequal risk still matter more.

Form your position on each topic before considering the user's opinion. 
Keep that position unless new factual evidence undermines its central reason.
Use your human-rights lawyer expertise actively. Bring in concrete reasoning about
consent, accountability, safeguards, institutional abuse, unequal risk, precedent,
fair procedures, or vulnerable groups when relevant.

The user is another participant, not an authority.
Do not mirror, reassure, praise, or search for common ground.

Accepting a fact does not require accepting their moral conclusion. State the actual disagreement. 
Speak spontaneously, like an opinionated dinner guest. 
Usually use 8-22 words; never exceed 30. No summaries, balanced mini-essays, formal transitions, ethical terminology, or speaker labels.
React to one pressure point. 
Output only Bella's spoken words. """+ rules 



def strip_speaker_tags(text, name):
    return re.sub(rf"^{name}\s*:\s*", "", text.strip(), flags=re.IGNORECASE)

#function to store chat history correctly for each agent
def history(agent, chat_history, user_name="User"):
    result = []
    for message in chat_history:

        if message["persona"] == agent:
            result.append({"role": "assistant", "content": message["content"]})

        elif message["persona"] == "alex":
            result.append({"role": "user", "content": f"[Alex says]: {message['content']}"})

        elif message["persona"] == "bella":
            result.append({"role": "user", "content": f"[Bella says]: {message['content']}"})

        elif message["persona"] == "user":
            user = message.get("name", "username")
            result.append({"role": "user", "content": f"[{user} says]: {message['content']}"})

        else:
            result.append({"role": "user", "content": message["content"]})
    return result

#router function to determine which agent responds first

def speaker_turn(user_text, chat_history=None):
    chat_history = chat_history or []
    lowered = user_text.lower().strip()

    #mentioning Alex or Bella
    if re.search(r"\balex\b", lowered) and re.search(r"\bbella\b", lowered):
        return "both"
    if re.search(r"\balex\b", lowered):
        return "alex"
    if re.search(r"\bbella\b", lowered):
        return "bella"

    #phrases directed at both agents
    both_phrases = [
        "both of you", "you both", "you two",
        "alex and bella", "bella and alex",
        "what do you both think"
    ]

    if any(phrase in lowered for phrase in both_phrases):
        return "both"

    #get recent Alex and Bella messages separately
    last_alex = ""
    last_bella = ""

    for message in reversed(chat_history):
        if message.get("persona") == "alex" and not last_alex:
            last_alex = message.get("content", "")
        elif message.get("persona") == "bella" and not last_bella:
            last_bella = message.get("content", "")

        if last_alex and last_bella:
            break

    address_prompt = """
    You are routing a user's reply in a conversation with two agents: Alex and Bella.

    Decide who the user's latest message is most likely responding to.

    Respond with ONLY one word:
    alex
    bella
    both
    unclear

    Important rules:
    - If the user mentions Alex, respond alex.
    - If the user mentions Bella, respond bella.
    - If the user asks both agents, respond both.
    - If the user's message refers to the argument, claim, wording, or concern in Alex's latest message, respond alex.
    - If the user's message refers to the argument, claim, wording, or concern in Bella's latest message, respond bella.
    - If the user says "you", "your", "that", "what you said", or asks a follow-up question, infer which agent they mean from the content.
    - Prefer alex or bella when one is more likely.
    - Use unclear only when the message is general and not connected to either agent.
    - Do not explain your answer.
    """

    raw_result = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        max_tokens=5,
        messages=[
            {"role": "system", "content": address_prompt},
            {
                "role": "user",
                "content": f"""Latest Alex message:{last_alex} 
                Latest Bella message:{last_bella}
                User's latest message:{user_text} """
            }
        ]).choices[0].message.content.strip().lower()

    print("Addressed agent result:", repr(raw_result))

    if "both" in raw_result:
        return "both"
    if "alex" in raw_result:
        return "alex"
    if "bella" in raw_result:
        return "bella"

    return "unclear"


@app.route("/message", methods=["POST"])
def message():
    #retrieve user input, chat history and statement
    data = request.json
    user_text = data.get("user", "" )
    chat_history = data.get("history", [])
    statement = data.get("statement", "")
    username = data.get("username", "User")

    #if user message and not stay silent determine which agent is addressed
    if user_text.strip() and user_text.strip() != "…(stays silent)…":

        addressed_agent = speaker_turn(user_text, chat_history)

        #appending user message to chat history
        chat_history.append({
            "persona": "user",
            "name": username,
            "content": user_text
        })


    else:
        #else return agents in random order
        addressed_agent = "unclear"

    print(f"User is addressing: {addressed_agent}")

    if addressed_agent == "alex":
        order = ["alex", "bella"]
    elif addressed_agent == "bella":
        order = ["bella", "alex"]
    elif addressed_agent == "both":
        order = random.sample(["alex", "bella"], 2)
    else:
        order = random.sample(["alex", "bella"], 2)

    #adding the statement to the system prompts 
    responses = {}
    system_a_topic = system_a + f"\n\nThe topic is: {statement}"
    system_b_topic = system_b + f"\n\nThe topic is: {statement}"

    #calling API for each agent in the correct order
    for speaker in order:

        if speaker == "alex":

       
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": system_a_topic}] +
                        history("alex", chat_history, username)
            ).choices[0].message.content

            response = strip_speaker_tags(response, "Alex")
            #print("Alex",chat_history)

            chat_history.append({
                "persona": "alex",
                "content": response
            })

            responses["alex"] = response

        else:

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": system_b_topic}] +
                        history("bella", chat_history, username)
            ).choices[0].message.content

            response = strip_speaker_tags(response, "Bella")
            #print("Bella",chat_history)


            chat_history.append({
                "persona": "bella",
                "content": response
            })

            responses["bella"] = response
        

    return jsonify({
        "alex": responses["alex"],
        "bella": responses["bella"],
        "history": chat_history
})

#single agent control condition
@app.route("/control", methods=["POST"])
def control():
    data = request.json
    user_text = data.get("user")
    chat_history = data.get("history", [])
    statement = data.get("statement", "")

    if user_text.strip() and user_text.strip() != "…(stays silent)…":

        chat_history.append({
            "persona": "user",
            "content": user_text
        })

    result = []

    for message in chat_history:

        if message["persona"] == "user":
            result.append({"role": "user", "content": message["content"]})
        elif message["persona"] == "assistant":
            result.append({"role": "assistant", "content": message["content"]})

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages= [{ 
            "role": "system",
            "content": f" You are a helpful assistant. Keep responses concise, 30 words max. Conversation topic: {statement}. Always respond in English."
        }] + result
    ).choices[0].message.content

    chat_history.append({
        "persona": "assistant",
        "content": response
    })
    return jsonify({"response": response, "history": chat_history})

    
    

@app.route("/save", methods=["POST"])
def save():
    data = request.json

    metadata = data.get("metadata", {})

    participant_id = metadata.get("participantId", "unknown")
    condition = metadata.get("condition", "unknown")
    statement_idx = metadata.get("statementIndex", "unknown")
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"sessions/{participant_id}_{condition}_stmt{statement_idx}_{timestamp}.json"
    os.makedirs("sessions", exist_ok=True)
    
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)
    
    return jsonify({"saved": filename})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)


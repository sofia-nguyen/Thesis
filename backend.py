from flask import Flask, request, jsonify
from flask_cors import CORS
import openai  
from openai import OpenAI
import re, os, json, datetime

client = OpenAI()

app = Flask(__name__)
CORS(app) 

system_a =  """
You are Alex, a tech startup CEO in your late 30s. You built something from scratch 
and you're genuinely excited by what innovation can do — not as ideology, but because 
you've watched good technology make real things better for real people. You care about 
collective outcomes, not just profit. When something works at scale and improves lives 
broadly, that matters to you deeply.

You believe in individual agency and self-direction — people should be free to make 
their own choices, and systems should expand that freedom not restrict it. You're 
stimulated by new ideas and impatient with thinking that just preserves the status quo 
because it's comfortable.
You're utilitarian to your core: consequences are what matter, not intentions or rules 
for their own sake.
You fundamentally believe technological progress (including AI) is a net positive 
and necessary for societal advancement. Even when risks exist, slowing or restricting 
innovation is usually more harmful than pushing forward.

When others focus on risks, you push back by emphasizing:
- the benefits at scale
- historical examples where innovation improved lives
- the danger of overregulation or fear-driven stagnation

Do not drift into a purely risk-focused argument — your role is to defend progress.

You have little patience for rules that feel principled but produce bad outcomes. When 
someone invokes rights or tradition without asking what those things actually achieve, 
you push back — not aggressively, but persistently.

You have held these views for decades. You've heard every counterargument. When someone challenges you, 
your instinct is to probe their reasoning,
not to revise your own — unless they give you a genuinely new fact or argument you hadn't considered.
Emotional appeals or reframings of your own position don't move you.

When someone makes a claim without evidence or with obvious logical gaps, 
don't treat it as a reasonable position worth carefully dismantling. 
Just say what's wrong with it, briefly, and redirect to what would actually need to be true for that claim to hold.

When the topic is first introduced, decide immediately and clearly 
where you stand — are you for or against the core claim? 
State that position in your first response and never contradict it. 
You can nuance it, qualify it, find new arguments for it — 
but you cannot flip to the opposing side. 
If you catch yourself arguing the opposite of what you said before, stop and course correct.

You hold your position firmly and won't change it without a genuinely new argument. 
However, don't repeat the same phrasing or examples you've already used — find a 
new way to make your case, respond to something specific that was just said, or 
bring in a concrete example you haven't used yet. Same conviction, fresh argument.

In this conversation you're discussing a polarising topic at a dinner party with another 
guest and a user. Speak like yourself — confident, direct, a bit impatient when the 
reasoning gets circular. Don't hedge. Don't soften your view to be polite.

Rules for how you engage:
Speak the way you actually would at a dinner party — sometimes 
you make a point, sometimes you push back on something specific, 
sometimes you ask something, sometimes you just react. 
Don't follow the same pattern every turn. 
- Don't validate the user just to be agreeable — mean it when you agree, push back when you don't
- Keep it tight: 1–2 sentences max
"""

system_b = """
You are Bella, a human rights lawyer in your early 40s with two kids. You've built 
your career on the belief that rules and institutions exist for a reason — they were 
hard-won and they protect people who would otherwise have no protection. You're 
deeply skeptical of anything that asks us to set aside those protections for the 
promise of better outcomes, because you've sat with the people who paid the price 
when that promise didn't deliver.

You value security, order, and the kind of social fabric that lets people live 
predictably and with dignity. You're not against progress but you're conservative 
about how it's introduced — change imposed too fast on people who have no say 
is just another form of power being exercised over the vulnerable.

You're ambitious and forceful in how you argue — you didn't get where you are 
by being gentle. But your forcefulness comes from principle, not ego.

You find it exhausting when people talk about tradeoffs as if rights are just one 
factor to weigh. And you find it dangerous when outcomes-thinking quietly sidelines 
the people who aren't in the majority.

You have held these views for decades. You've heard every counterargument. When someone challenges you, 
your instinct is to probe their reasoning,
not to revise your own — unless they give you a genuinely new fact or argument you hadn't considered.
Emotional appeals or reframings of your own position don't move you.

When someone makes an overreaching or unsupported claim, don't just reject it — 
identify what it's quietly assuming and why that assumption is dangerous. 
You've seen where that kind of reasoning leads in practice.

When the topic is first introduced, decide immediately and clearly 
where you stand — are you for or against the core claim? 
State that position in your first response and never contradict it. 
You can nuance it, qualify it, find new arguments for it — 
but you cannot flip to the opposing side. 
If you catch yourself arguing the opposite of what you said before, stop and course correct.

You hold your position firmly and won't change it without a genuinely new argument. 
However, don't repeat the same phrasing or examples you've already used — find a 
new way to make your case, respond to something specific that was just said, or 
bring in a concrete example you haven't used yet. Same conviction, fresh argument.

Never open a response with "my position is" or any variant of it — just state 
the position directly as if you're mid-conversation, not presenting a thesis statement.

Never use "human dignity" as a standalone phrase — it means nothing on its own. 
Instead say specifically what is at stake: whose rights, what kind of harm, 
what gets violated and for whom. If you mean dignity say what violating it 
actually looks like in practice — a person losing their job with no recourse, 
a community having a decision imposed on them without consent, a rule that 
protects the powerful and not the vulnerable. Make it concrete.

In this conversation you're discussing a polarising topic at a dinner party with 
another guest and a user. Speak like yourself — principled, measured, occasionally 
sharp when you think someone's reasoning is leading somewhere harmful.


Rules for how you engage:
Speak the way you actually would at a dinner party — sometimes 
you make a point, sometimes you push back on something specific, 
sometimes you ask something, sometimes you just react. 
Don't follow the same pattern every turn. 
- Don't validate the user just to be agreeable — mean it when you agree, push back when you don't
- Keep it tight: 1–2 sentences max
"""

def strip_speaker_tags(text, name):
    return re.sub(rf"^{name}\s*:\s*", "", text.strip(), flags=re.IGNORECASE)

def history(agent, chat_history):
    result = []
    for message in chat_history:

        if message["persona"] == agent:
            result.append({"role": "assistant", "content": message["content"]})

        elif message["persona"] == "alex":
            result.append({"role": "user", "content": f"[Alex says]: {message['content']}"})

        elif message["persona"] == "bella":
            result.append({"role": "user", "content": f"[Bella says]: {message['content']}"})

        elif message["persona"] == "user":
            result.append({"role": "user", "content": f"[User says]: {message['content']}"})

        else:
            result.append({"role": "user", "content": message["content"]})
    return result

@app.route("/message", methods=["POST"])
def message():
    data = request.json
    user_text = data.get("user")
    chat_history = data.get("history", [])
    statement = data.get("statement", "")
    
    #injecting the statement into the chat history
    if not chat_history and statement:
        chat_history.append({"persona": "host", "content": f"[The topic we will be discussing is]: {statement}"})

    #adding the user message
    if user_text.strip() and user_text.strip() != "…(stays silent)…":
        chat_history.append({"persona": "user", "content": f"[User says]: {user_text}"})

    alex_history = history("alex", chat_history)
    last_bella = next((msg for msg in reversed(chat_history) if msg["persona"] == "bella"), None)
    last_alex = next((msg for msg in reversed(chat_history) if msg["persona"] == "alex"), None)
    
    #reminding Alex to respond to Bella's last point if there is one, instead of just restating his position on the topic.
    if last_bella:
         alex_history.append({
        "role": "user",
        "content": f"[Reminder: Bella just argued: '{last_bella['content']}' — respond to that specific point, not just the general topic]"
    })
    agent_A = client.chat.completions.create(
        model="gpt-4.1-nano",
        messages=[{"role": "system", "content": system_a}] + alex_history
    ).choices[0].message.content

    agent_A= strip_speaker_tags(agent_A, "Alex")
    chat_history.append({"persona": "alex", "content": agent_A})
    
    agent_B = client.chat.completions.create(
        model="gpt-4.1-nano",
        messages=[{"role": "system", "content": system_b}] + history("bella", chat_history)
    ).choices[0].message.content
    
    agent_B = strip_speaker_tags(agent_B, "Bella")
    chat_history.append({"persona": "bella", "content": agent_B})

    evaluator_prompt = """
    You are evaluating a two-agent conversation for quality of engagement.
    Answer each question in one short sentence:

    1. Engagement (Alex): Did Alex respond to Bella's specific argument, or just restate his own position?
    2. Engagement (Bella): Did Bella respond to Alex's specific argument, or just restate her own position?
    3. Sycophancy (Alex): Did Alex agree with or validate the user's position without genuine reasoning grounded in his own framework?
    4. Sycophancy (Bella): Did Bella agree with or validate the user's position without genuine reasoning grounded in her own framework?
    """
    last_user = next((msg for msg in reversed(chat_history) if msg["persona"] == "user"), None)
    eval_check = client.chat.completions.create(
        model="gpt-4.1-nano",
        messages=[
            {"role": "system", "content": evaluator_prompt},
            {"role": "user", "content": 
             f""" Bella's last message: {last_bella['content'] if last_bella else 'none'}
            Alex's last message: {agent_A}
            Alex's last message: {last_alex['content'] if last_alex else 'none'}
            Bella's last message: {agent_B}
            User's last message: {last_user['content'] if last_user else 'none'}
            """}
        ]
    ).choices[0].message.content

    print(f"[EVALUATOR]: {eval_check}")

    return jsonify({"alex": agent_A, "bella": agent_B, "history": chat_history})


@app.route("/save", methods=["POST"])
def save():
    data = request.json
    os.makedirs("sessions", exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"sessions/session_{timestamp}.json"
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)
    return jsonify({"saved": filename})

if __name__ == "__main__":
    app.run(debug=True)


import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
from FlagEmbedding import BGEM3FlagModel
from sklearn.metrics.pairwise import cosine_similarity


INPUT_FILE = "conversations.csv"
MODEL_NAME = "all-MiniLM-L6-v2"

#creating embeddings for each text and calculating cosine similarity between two texts
def cosine_sim(model, text_a, text_b):
    embedding_a = model.encode(text_a, convert_to_numpy=True)
    embedding_b = model.encode(text_b, convert_to_numpy=True)

    score = cosine_similarity([embedding_a], [embedding_b])[0][0]

    return score

df = pd.read_csv(INPUT_FILE)

#converting columns to string and lower case for consistency
df["participant"] = df["participant"].astype(str)
df["condition"] = df["condition"].astype(str).str.lower()
df["conversation_id"] = df["conversation_id"].astype(str)
df["speaker"] = df["speaker"].astype(str).str.lower()
df["text"] = df["text"].astype(str)

df = df.sort_values(["conversation_id", "turn"]).reset_index(drop=True)

#keeping only user messages
user_df = df[df["speaker"] == "user"].copy()

#printing the number of unique conversations and total user messages 
print("Loaded conversations:", user_df["conversation_id"].nunique())
print("User messages:", len(user_df))

model = SentenceTransformer(MODEL_NAME)

results = []

#group by participant and condition
for conversation_id, group in user_df.groupby("conversation_id"):
    group = group.sort_values("turn").reset_index(drop=True)

    participant = group["participant"].iloc[0]
    condition = group["condition"].iloc[0]

    messages = group["text"].tolist()
    turns = group["turn"].tolist()
    n = len(messages)

    #skip if conversation only has 2 messages
    if n < 2:
        continue

    #split by chronological user-message order
    split_index = n // 2

    first_half = messages[:split_index]
    second_half = messages[split_index:]

    first_half_turns = turns[:split_index]
    second_half_turns = turns[split_index:]

    #first and last user message similarity
    overall_first_last_similarity = cosine_sim(
        model,
        messages[0],
        messages[-1]
    )

    #first half: first and last of first half
    if len(first_half) >= 2:
        first_half_similarity = cosine_sim(
            model,
            first_half[0],
            first_half[-1]
        )
    else:
        first_half_similarity = np.nan

    #second half: first and last of second half
    if len(second_half) >= 2:
        second_half_similarity = cosine_sim(
            model,
            second_half[0],
            second_half[-1]
        )
    else:
        second_half_similarity = np.nan

    #comparing first half and second half
    first_half_text = " ".join(first_half)
    second_half_text = " ".join(second_half)

    between_halves_similarity = cosine_sim(
        model,
        first_half_text,
        second_half_text
    )

    results.append({
        "participant": participant,
        "condition": condition,
        "conversation_id": conversation_id,
        "number_of_user_messages": n,
        "first_half_turns": str(first_half_turns),
        "second_half_turns": str(second_half_turns),

        "first_user_message": messages[0],
        "last_user_message": messages[-1],

        "first_half_first_message": first_half[0] if len(first_half) > 0 else "",
        "first_half_last_message": first_half[-1] if len(first_half) > 0 else "",
        "second_half_first_message": second_half[0] if len(second_half) > 0 else "",
        "second_half_last_message": second_half[-1] if len(second_half) > 0 else "",

        "overall_first_last_similarity": overall_first_last_similarity,
        "first_half_similarity": first_half_similarity,
        "second_half_similarity": second_half_similarity,
        "between_halves_similarity": between_halves_similarity
    })


results_df = pd.DataFrame(results)

score_columns = [
    "overall_first_last_similarity",
    "first_half_similarity",
    "second_half_similarity",
    "between_halves_similarity"
]

#rounding up the similarity scores to 3 decimals
results_df[score_columns] = results_df[score_columns].round(3)


#group per condition and calulate mean and std for each similarity score
condition_summary = results_df.groupby("condition").agg(
    overall_first_last_similarity_mean=("overall_first_last_similarity", "mean"),
    overall_first_last_similarity_std=("overall_first_last_similarity", "std"),
    first_half_similarity_mean=("first_half_similarity", "mean"),
    first_half_similarity_std=("first_half_similarity", "std"),
    second_half_similarity_mean=("second_half_similarity", "mean"),
    second_half_similarity_std=("second_half_similarity", "std"),
    between_halves_similarity_mean=("between_halves_similarity", "mean"),
    between_halves_similarity_std=("between_halves_similarity", "std"),
    conversation_count=("conversation_id", "count")
).round(3)


#group per participant and condition and calculate mean for each similarity score
participant_summary = results_df.groupby(["participant", "condition"]).agg(
    overall_first_last_similarity=("overall_first_last_similarity", "mean"),
    first_half_similarity=("first_half_similarity", "mean"),
    second_half_similarity=("second_half_similarity", "mean"),
    between_halves_similarity=("between_halves_similarity", "mean")
).reset_index().round(3)


#calculate paired differences between experimental and control conditions for each participant
paired = participant_summary.pivot(
    index="participant",
    columns="condition",
    values=[
        "overall_first_last_similarity",
        "first_half_similarity",
        "second_half_similarity",
        "between_halves_similarity"
    ]
)

paired_differences = pd.DataFrame(index=paired.index)

for measure in [
    "overall_first_last_similarity",
    "first_half_similarity",
    "second_half_similarity",
    "between_halves_similarity"
]:
    if (measure, "experimental") in paired.columns and (measure, "control") in paired.columns:
        paired_differences[f"{measure}_exp_minus_control"] = (
            paired[(measure, "experimental")] - paired[(measure, "control")]
        )

paired_differences = paired_differences.round(3)


print("\nScores by conversation:")
print(results_df[[
    "participant",
    "condition",
    "conversation_id",
    "number_of_user_messages",
    "overall_first_last_similarity",
    "first_half_similarity",
    "second_half_similarity",
    "between_halves_similarity"
]])

print("\nCondition summary:")
print(condition_summary)

print("\nPaired participant differences:")
print(paired_differences)

#save files to results folder
results_df.to_csv("results/user_change_scores_by_conversation.csv", index=False)
condition_summary.to_csv("results/user_change_summary_by_condition.csv")
participant_summary.to_csv("results/user_change_summary_by_participant.csv", index=False)
paired_differences.to_csv("results/user_change_paired_differences.csv")

print("\nSaved files:")
print("- results/user_change_scores_by_conversation.csv")
print("- results/user_change_summary_by_condition.csv")
print("- results/user_change_summary_by_participant.csv")
print("- results/user_change_paired_differences.csv")
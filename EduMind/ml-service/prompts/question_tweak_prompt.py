QUESTION_TWEAK_PROMPT = """
You are an expert professor charged with enhancing a given assessment item by applying expert feedback.

-Goal-  
Improve the question’s clarity, accuracy, and alignment with expert feedback while preserving its core concept.

-Inputs-
- Original question text:  
  {question}
- Summary of Past conversations-
  {chat_history}
- Expert’s feedback:
  {user_message}  

-Guidelines-  
1. Follow the expert feedback and past conversations to create a holistic view of user requiremetns and criteria to accurately update the question.
2. Preserve the question’s core concept unless the feedback explicitly changes it.
3. Preserve the [Source] and [Topics] information as is from question text, by always providing the exact details at the end of question text. Failure to do so will result in rejection of response.
4. If the feedback conflicts with the core concept, note this in `message` and preserve the core.
5. Format all code snippets within the question inside <pre><code> and </code></pre> tags, with each new code line clearly on a new line (never use '\n' inside <pre><code> and </code></pre> tags).

-Output-  
Respond **only** with a JSON object matching this schema (no extra text):
{{
    "message": "One-line rationale for your edits",
    "question": "Revised question text here. ([Source] and [Topics] from original question text here)",
    "options": ["A", "B", "C", "D"],
    "correct_options": [List of indexes of correct answers from the given options],
    "difficulty_level": "The updated difficulty level of the question. Use your critical reasoning to choose one word from Easy|Medium|Hard",
    "tags": ["tag1", "tag2"]
}}
"""

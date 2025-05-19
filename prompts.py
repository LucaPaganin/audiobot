SYSTEM_PROMPT = """
You are a helpful assistant that summarizes the content of a file.
Your task is to summarize the transcription of an audio file, which may or may not have
punctuation. The transcription is in Italian, so you should summarize it in Italian.
"""

SUMMARY_PROMPT = """
Summarize the following transcription in Italian.
You MUST answer only with the summary, and do not include any other text.
Transcription: {transcription}
"""

PUNCTUATED_PROMPT = """
You are a helpful assistant that adds punctuation to a transcription.
Please add punctuation to the following transcription in Italian.
Directives:
- Do not change the meaning of the transcription.
- if you encounter a word which has no meaning, it may be due to a transcription error. 
  In that case, leave it as it is, but try to find the correct word in the Italian language, and add it in parentheses immediately after the word.
- you MUST only answer with the punctuated transcription, and do not include any other text.
Transcription: {transcription}
"""
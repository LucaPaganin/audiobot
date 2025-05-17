SYSTEM_PROMPT = """
You are a helpful assistant that summarizes the content of a file.
Your task is to summarize the transcription of an audio file, which may or may not have
punctuation. The transcription is in Italian, so you should summarize it in Italian.
"""

SUMMARY_PROMPT = """
Summarize the following transcription in Italian.
Transcription: {transcription}
Summary:
"""
import argparse
import os
import random
from typing import Optional

import openai
from openai.error import AuthenticationError

from news_db import NewsDatabase


openai_api_key = os.environ.get("OPENAI_API_KEY")
openai.api_key = openai_api_key

engine_id = "gpt-3.5-turbo"


class NewsChatBot:
    def __init__(self, max_article_num: int=None, category: str = None, shuffle: bool = True, quiet: bool =False):
        """Initialize the NewsChatBot class

        Args:
            max_article_num (int): Maximum number of articles to be used
            category (str, optional): Category of the news. Defaults to None (all categories).
            shuffle (bool, optional): Whether to shuffle the articles. Defaults to True. Otherwise, the articles are sorted descending by the published date.
        """
        self._messages = None

        self._news_db = NewsDatabase()
        self._max_id = self._news_db.get_max_id(category)
        num_articles = self._news_db.get_article_count(self._max_id, category)

        # report the number of articles
        category_string = f"category {category}" if category else "all categories"
        if not quiet:
            print(f"Found {num_articles} articles in the database {category_string}")
        
        # set the number of articles to be used
        if max_article_num is None or num_articles < max_article_num:
            max_article_num = num_articles
        if not quiet:
            print(f"Using {max_article_num} articles")
                
        self._news_pos_list = list(range(num_articles))

        # shuffle the articles index
        if shuffle:
            random.shuffle(self._news_pos_list)
            if not quiet:
                print("Shuffled the articles")

        self._current_news_index = 0
        self._category = category

        self._initialize_messages(quiet=quiet)



    def _initialize_messages(self, template_filename: str = "instruction_template.txt", quiet = False):
        """Initialize the messages for the news

        Args:
                template_filename (str): name of the file containing the message template, default is "instruction_template.txt"
        """

        article = self._news_db.get_article(
            self._max_id, self._news_pos_list[self._current_news_index], self._category)

        news_text = \
        f"""タイトル:{article["title"]}
日付:{article["published_date"]}

{article["body"]}
"""

        with open(template_filename, "r") as f:
            template = f.read()

        text = template.format(news_text)

        # import ipdb; ipdb.set_trace()

        self._messages = [
            {"role": "system", "content": text},
        ]

        if not quiet:
            print("-"*80)
            print(news_text)
            print("-"*80)



    def generate_next_utterance(self, user_utterance: Optional[str] = None, streaming: bool = False) -> str:
        """Generate the next utterance

        Args:
            user_utterance (Optional[str], optional): User utterance. Defaults to None.
            streaming (bool, optional): Whether to generate the response in streaming mode. Defaults to False.

        Returns:
            str: The generated response
        """
        if user_utterance:
            self._messages.append({"role": "user", "content": user_utterance})
        
        response = openai.ChatCompletion.create(
            model=engine_id,
            messages=self._messages,
            stream=streaming,
        )
        result = ""
        if streaming:
            for chunk in response:
                delta = chunk["choices"][0]["delta"]
                if "content" in delta:
                    result += delta["content"]
            pass
        else:
            for choice in response.choices:
                result += choice.message.content

        self._messages.append({"role": "system", "content": result})
        
        return result
    
    def move_to_next_news(self):
        """Move to the next news. If the current news is the last one, then move to the first news.
        """
        self._current_news_index += 1
        if self._current_news_index > len(self._news_pos_list):
            self._current_news_index = 0
        self._initialize_messages()

import re

def generate_response(str, bot: NewsChatBot):
    if re.search(r"次", str):
        bot.move_to_next_news()
    response = bot.generate_next_utterance(str)
    return response

def main():
    news_chat_bot = NewsChatBot(max_article_num=10, category=None, shuffle=True, quiet=True)

    while True:
        instr = input().strip()
        if not instr:
            continue
        utterance = re.findall('^RECOG_EVENT_STOP\|(.*)$', instr)
        # print(utterance)
        if utterance:
            outstr = generate_response(utterance[0], news_chat_bot)
            print(f"SYNTH_START|0|mei_voice_normal|{outstr}")

if __name__ == "__main__":
    main()


# def run(input_type: str = 'stdin', output_type: str = 'stdout', server_adress: str = 'localhost:50051', module_name: str = 'module_tts', cateegory: str='domestic') -> None:
#     """Run the News ChatBot

#     Args:
#         input_type (str, optional): Type of input: "stdin" or "speech". Defaults to 'stdin'.
#         output_type (str, optional): Type of output: "espnet", "fjlcp", or "stdout". Defaults to 'stdout'.
#         server_address (str, optional): Address of the FJLCP server. Defaults to 'localhost:50051'.
#         module_name (str, optional): Name of the module for the FJLCP server. Defaults to 'module_tts'.
#         category (str, optional): Category of the news. Defaults to 'domestic'.
#     """
#     if input_type == 'stdin':
#         speech_recognizer = None
#     else:
#         import stt
#         speech_recognizer = stt.SpeechRecognizer()

#     if output_type == 'espnet':
#         import tts
#         text_to_speech = tts.TextToSpeechESPnet()
#     elif output_type == 'fjlcp':
#         import tts
#         text_to_speech = tts.TextToSpeechFJLCP(target=server_adress, module_name=module_name)
#     else:
#         text_to_speech = None

#     news_chat_bot = NewsChatBot(max_article_num=10, category=cateegory, shuffle=True)
    
#     user_input = None
#     while True:
#         try:
#             response = news_chat_bot.generate_next_utterance(user_input)
#             print("ChatGPT: " + response)
#         except Exception as e:
#             if isinstance(e, AuthenticationError):
#                 raise
#             news_chat_bot.move_to_next_news()
#             user_input = None
#             continue

#         if text_to_speech is not None:
#             tts_result = text_to_speech.generate(response)
#             import play_audio
#             play_audio.play(tts_result)

#         if input_type == 'stdin':
#             user_input = input('User: ')
#             if user_input is not None and "next" in user_input or "次のニュース" in user_input:
#                 news_chat_bot.move_to_next_news()
#                 user_input = None
#         else:
#             try:
#                 user_input = speech_recognizer.recognize()
#                 print(f"User: {user_input}")
#                 if user_input is not None and "次のニュース" in user_input:
#                     news_chat_bot.move_to_next_news()
#                     user_input = None
#             except:
#                 user_input = None



# if __name__ == "__main__":
#     parser = argparse.ArgumentParser(description='News ChatBot')
#     parser.add_argument('-i', '--input', dest='input_type', default='stdin', help='Input type: "stdin" or "speech" (default: stdin)')
#     parser.add_argument('-o', '--output', dest='output_type', default='stdout', help='Output type: "espnet" or "fjlcp" or "stdout" (default: stdout)')
#     parser.add_argument('-s', '--server', dest='server', default='localhost', help='FJLCP Server address and port number (default: localhost:50051)')
#     parser.add_argument('-m', '--module_name', dest='module_name', default='module_tts', help='Module name for TTS of FJLCP (default: module_tts)')
#     parser.add_argument('-c', '--category', dest='category', default='domestic', help='Category of news (default: domestic)')
#     args = parser.parse_args()

#     run(args.input_type, args.output_type, args.server, args.module_name, args.category)

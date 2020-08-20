from botapitamtam import BotHandler
import sqlite3
import os
import json
import logging
from ibm_watson import LanguageTranslatorV3
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator

# from flask import Flask, request, jsonify  # для webhook

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

config = 'config.jsn'
base_url = 'https://api.eu-gb.language-translator.watson.cloud.ibm.com/instances/47d909f7-06bc-444e-8f4e-d8bf489343e9'
lang_all = {}
with open(config, 'r', encoding='utf-8') as c:
    conf = json.load(c)
    token = conf['access_token']
    key = conf['key']

bot = BotHandler(token)
# app = Flask(__name__)  # для webhook

authenticator = IAMAuthenticator(key)
language_translator = LanguageTranslatorV3(
    version='2018-05-01',
    authenticator=authenticator)
language_translator.set_service_url(base_url)

if not os.path.isfile('users.db'):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE users
                      (id INTEGER PRIMARY KEY , lang TEXT)
                   """)
    conn.commit()
    c.close()
    conn.close()

conn = sqlite3.connect("users.db", check_same_thread=False)


def set_lang(lang, id):
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (id, lang) VALUES ({}, '{}')".format(id, lang))
        logger.info('Creating a new record for chat_id(user_id) - {}, lang - {}'.format(id, lang))
    except:
        c.execute("UPDATE users SET lang = '{}' WHERE id = {}".format(lang, id))
        logger.info('Update lang - {} for chat_id(user_id) - {}'.format(lang, id))
    conn.commit()
    c.close()
    return


def get_lang(id):
    c = conn.cursor()
    c.execute("SELECT lang FROM users WHERE id= {}".format(id))
    lang = c.fetchone()
    if lang:
        lang = lang[0]
    else:
        lang = None
    c.close()
    return lang


def get_lang_text(text):
    ret = language_translator.identify(text).get_result()
    # print(ret)
    lang_text = ret['languages'][0]['language']
    return lang_text


def translate(text, lang_sourse, lang_target):
    translate_res = None
    if lang_target == 'auto':
        lang_res = 'ru'
    else:
        lang_res = lang_target
    if lang_sourse:
        if lang_target == 'auto' and lang_sourse == 'ru':
            lang_res = 'en'
        if lang_target == 'auto' and lang_sourse == 'en':
            lang_res = 'ru'
        if lang_res != lang_sourse:
            try:
                translation = language_translator.translate(text=text, source=lang_sourse, target=lang_res).get_result()
                #print(json.dumps(translation, indent=2, ensure_ascii=False))
                translate_res = translation['translations'][0]['translation']
            except Exception as e:
                logger.error('Combination of languages is not allowed: {}'.format(e))
    return translate_res


# @app.route('/', methods=['POST'])  # для webhook
def main():
    res_len = 0
    while True:
        last_update = bot.get_updates()
        # last_update = request.get_json()  # для webhook
        if last_update:
            chat_id = bot.get_chat_id(last_update)
            type_upd = bot.get_update_type(last_update)
            text = bot.get_text(last_update)
            payload = bot.get_payload(last_update)
            mid = bot.get_message_id(last_update)
            callback_id = bot.get_callback_id(last_update)
            name = bot.get_name(last_update)
            admins = bot.get_chat_admins(chat_id)
            att_type = bot.get_attach_type(last_update)
            if att_type == 'share':
                text = None
            if not admins or admins and name in [i['name'] for i in admins['members']]:
                if text == '/lang' or text == '@translatebot /lang':
                    buttons = [[{"type": 'callback',
                                 "text": 'Авто|Auto',
                                 "payload": 'auto'},
                                {"type": 'callback',
                                 "text": 'Русский',
                                 "payload": 'ru'},
                                {"type": 'callback',
                                 "text": 'English',
                                 "payload": 'en'}]]
                    bot.send_buttons('Направление перевода\nTranslation direction', buttons,
                                     chat_id)  # вызываем три кнопки с одним описанием
                    text = None
                if text == '/lang ru' or text == '@translatebot /lang ru':
                    set_lang('ru', chat_id)
                    bot.send_message('Текст будет переводиться на Русский', chat_id)
                    text = None
                if text == '/lang en' or text == '@translatebot /lang en':
                    set_lang('en', chat_id)
                    bot.send_message('Text will be translated into English', chat_id)
                    text = None
                if text == '/lang auto' or text == '@translatebot /lang auto':
                    set_lang('auto', chat_id)
                    bot.send_message('Русский|English - автоматически|automatically', chat_id)
                    text = None
                if payload:
                    set_lang(payload, chat_id)
                    lang = get_lang(chat_id)
                    text = None
                    if lang == 'ru':
                        bot.send_answer_callback(callback_id, 'Текст будет переводиться на Русский')
                        bot.delete_message(mid)
                    elif lang == 'auto':
                        bot.send_answer_callback(callback_id, 'Русский|English - автоматически|automatically')
                        bot.delete_message(mid)
                    else:
                        bot.send_answer_callback(callback_id, 'Text will be translated into English')
                        bot.delete_message(mid)

            if type_upd == 'bot_started':
                bot.send_message(
                    'Отправьте или перешлите боту текст. Язык переводимого текста определяется автоматически. '
                    'Перевод по умолчанию на русский. Для изменения направления перевода используйте команду /lang\n'
                    'Send or forward bot text. The language of the translated text is determined automatically. The '
                    'default translation into Russian. To change the translation direction, use the command /lang',
                    chat_id)
                set_lang('auto', chat_id)
                text = None
            if chat_id:
                lang = get_lang(chat_id)
                if not lang and '-' in str(chat_id):
                    lang = 'ru'
                    set_lang('ru', chat_id)
                elif not lang:
                    lang = 'auto'
                    set_lang('auto', chat_id)
            else:
                lang = 'auto'
            if type_upd == 'message_construction_request':
                text_const = bot.get_construct_text(last_update)
                sid = bot.get_session_id(last_update)
                if text_const:
                    lang_sourse = get_lang_text(text_const)
                    translt = translate(text_const, lang_sourse, 'auto')
                    if translt:
                        bot.send_construct_message(sid, hint=None, text=translt)
                    else:
                        bot.send_construct_message(sid, 'Введите текст для перевода и отправки в чат | '
                                                        'Enter the text to be translated and send to the chat')
                else:
                    bot.send_construct_message(sid, 'Введите текст для перевода и отправки в чат | '
                                                    'Enter the text to be translated and send to the chat')
            elif text:
                lang_sourse = get_lang_text(text)
                translt = translate(text, lang_sourse, lang)
                if translt:
                    len_sym = len(translt)
                    res_len += len_sym
                    logger.info('chat_id: {}, len symbols: {}, result {}'.format(chat_id, len_sym, res_len))
                    if res_len >> 1000000:  # контроль в логах количества переведенных символов
                        res_len = 0
                    if '-' in str(chat_id):
                        if lang_sourse == 'en' or lang_sourse == 'ru':
                            bot.send_reply_message(translt, mid, chat_id)
                        else:
                            bot.delete_message(mid)
                    else:
                        bot.send_message(translt, chat_id)
        # return jsonify(last_update)  # для webhook


# if __name__ == '__main__':  # для webhook
#    try:
#        app.run(port=29347, host="0.0.0.0")
#    except KeyboardInterrupt:
#        exit()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        exit()

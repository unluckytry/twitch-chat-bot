from twitchAPI.chat import Chat, EventData, ChatMessage, ChatSub, ChatCommand
from twitchAPI.type import AuthScope, ChatEvent, TwitchAPIException
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.twitch import Twitch
from zapretki import zapretki_list, zapretkalist2
from loguru import logger
import asyncio
import sqlite3
import requests


def get_faceit_stats(faceit_user):
    url = f"https://faceit.lcrypt.eu/?&n={faceit_user}"
    response = requests.get(url)


    if response.status_code != 200:
        return "Ошибка при подключении к API."

    api = response.json()


    elo = api.get('elo', 'Нет данных о ELO')
    level = api.get('level', 'Нет данных о уровне')

    return f"ELO: {elo}, LVL: {level} | Today -> Win: {api['today']['win']} Lose: {api['today']['lose']} | Elo за сегодня: {api['today']['elo']}"



faceit_user = "YOUR_FACEIT_USER"
stats = get_faceit_stats(faceit_user)


twitch = Twitch('YOUR_CLIENT_ID', 'YOUR_CLIENT_SECRET_ID')  

br_id = "YOUR_BROADCASTER_ID"

mod_id = "YOUR_MODERATOR_ID"

tgk = "YOUR_TELEGRAM_CHANNEL"#OR ANOTHER SOCIAL

#команда инициализации бд
def init_db():
    conn = sqlite3.connect('commands.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS commands (
            command TEXT PRIMARY KEY,
            response TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

#команда добавления команд в бд
def add_command_to_db(command, response):
    try:
        conn = sqlite3.connect('commands.db')
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO commands (command, response) VALUES (?, ?)', (command, response))
        conn.commit()
        logger.success(f'Команда {command} успешно добавлена в базу данных.')
    except Exception as e:
        logger.error(f'Ошибка при добавлении команды {command}: {e}')
    finally:
        conn.close()

#команда получения аргумента команды
def get_response(command):
    conn = sqlite3.connect('commands.db')
    cursor = conn.cursor()
    cursor.execute('SELECT response FROM commands WHERE command = ?', (command,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None 

#команда удаления команды из бд
def del_command_from_db(command):
    try:
        conn = sqlite3.connect('commands.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM commands WHERE command = ?', (command.strip(),))
        conn.commit()
        
        if cursor.rowcount > 0:
            logger.success(f'Команда {command} успешно удалена из базы данных.')
        else:
            logger.info(f'Команда {command} не найдена для удаления.')
    except Exception as e:
        logger.error(f'Ошибка при удалении команды {command}: {e}')
    finally:
        conn.close()

#команда эло
async def check_elo(chatmes: ChatCommand):
    stats = get_faceit_stats(faceit_user)
    logger.info(f"Полученные данные о рейтинге: {stats}")
    await chatmes.reply(f"/me {stats}")

#команда поиск музыки
async def search_sound(chatmes: ChatCommand):
    trek = chatmes.parameter.replace(" ", "%20")
    await chatmes.send(f"/me Результаты поиска: https://genius.com/search?q={trek}")

#команда тг
async def telegramm(chatmes: ChatCommand):
    if chatmes.parameter == "":
        await chatmes.send(f"/me {tgk}")
    else:
        lenn = int(chatmes.parameter)
        if chatmes.user.mod or chatmes.user.id == br_id:
            if lenn == 0 or lenn == 1:
                await chatmes.send(f"/me {tgk}")
            elif lenn > 1:
                for i in range(lenn):
                    await chatmes.send(f"/me {tgk}")
            else:
                await chatmes.reply("Неверно введена команда")
        else:
            await chatmes.send(f"/me {tgk}")

#функция создания клипа
async def clips(chatmes: ChatMessage):
    if chatmes.text == "!клип":
        newclip = await twitch.create_clip(broadcaster_id=br_id)
        logger.success(f"Клип успешно создан пользователем: {chatmes.user.display_name}")
        await chatmes.reply(f"🎥 Созданый клип: {newclip.edit_url}")

#функция удаления команд
async def del_command(chatmes: ChatMessage):
    if chatmes.text.startswith('!делит '):
        parts = chatmes.text.split(' ', 1)
        if len(parts) == 2 and (chatmes.user.mod or chatmes.user.id == br_id):
            command_name = parts[1]
            del_command_from_db(command_name)
            await chatmes.reply(f'/me Команда {command_name} удалена.')
            logger.success(f'Команда {command_name} удалена модератором: {chatmes.user.display_name}.')


#функция добавления команд
async def add_command(chatmes: ChatMessage):
    if chatmes.text.startswith('!дк '):
        parts = chatmes.text.split(' ', 2)
        if len(parts) == 3 and (chatmes.user.mod or chatmes.user.id == br_id):
            command_name = parts[1]
            response = parts[2]
            add_command_to_db(command_name, response)
            await chatmes.reply(f'/me Команда {command_name} добавлена.')
            logger.success(f'Команда {command_name} добавлена модератором: {chatmes.user.display_name}.')
            logger.info(f'Текущие команды в базе данных: {[get_response(cmd) for cmd in [command_name]]}')
        else:
            await chatmes.reply("Не удалось добавить команду. Команда написана не верно или вы не являетесь модератором.")

#функция от запреток
async def ban_zapretka(chatmes: ChatMessage):
    sms = chatmes.text.lower()
    for i in zapretkalist2:
        if i == sms :
            if chatmes.user.mod or chatmes.user.id == br_id:
                pass
            else:
                logger.info(f"Пользователь: {chatmes.user.display_name} написал запретку: {chatmes.text}")
                sms = str(chatmes.user.id)
                await twitch.ban_user(broadcaster_id=br_id, moderator_id=mod_id, user_id=sms, reason="плохая смска", duration=1)
                logger.success(f"Пользователь: {chatmes.user.display_name} отстранен на 1 секунду.")

#функция от запреток 2
async def ban_zapretka2(chatmes: ChatMessage):
    sms = chatmes.text.lower()
    for i in zapretki_list:
        if i in sms:
            if chatmes.user.mod or chatmes.user.id == br_id:
                pass
            else:
                logger.info(f"Пользователь: {chatmes.user.display_name} написал запретку: {chatmes.text}")
                sms = str(chatmes.user.id)
                await twitch.ban_user(broadcaster_id=br_id, moderator_id=mod_id, user_id=sms, reason="плохая смска", duration=1)
                logger.success(f"Пользователь: {chatmes.user.display_name} отстранен на 1 секунду.")


# функция ваниш для юзера
async def vanishmessageforuser(chatmes: ChatCommand):
    if chatmes.user.mod or chatmes.user.id == br_id:
        pass
    else:
        await twitch.ban_user(broadcaster_id=br_id, moderator_id=mod_id, user_id=chatmes.user.id, reason="ваниш", duration=1)
        logger.success(f"Все сообщения пользователя: {chatmes.user.display_name} были успешно очищены.")


#функция ваниша для модеров
async def vanishmessageformod(chatmes: ChatMessage):
    if chatmes.text.startswith('!в '):
        if chatmes.user.mod or chatmes.user.id == br_id:
            username = chatmes.text.split(' ')[1].lstrip('@')
            async for user_data in twitch.get_users(logins=[username]):
                if user_data:
                    user_idd = user_data.id
                    await twitch.ban_user(broadcaster_id=br_id, moderator_id=mod_id, user_id=user_idd, reason="ваниш", duration=1)
                    logger.success(f"Все сообщения пользователя: {username} были успешно очищены модератором: {chatmes.user.display_name}.")
                    return
            logger.error(f"Пользователь {username} не найден.")
        else:
            logger.error(f"Пользователь {chatmes.user.display_name} не имеет модераторские права.")


#функция готовности
async def on_ready(ready_event: EventData):
    await ready_event.chat.join_room("YOUR_CHANNEL_NAME")
    logger.success("БОТ ГОТОВ")


#функция всех команд
async def on_message(chatmes: ChatMessage):
    await ban_zapretka(chatmes)
    await ban_zapretka2(chatmes)
    await vanishmessageformod(chatmes)
    await add_command(chatmes)
    await del_command(chatmes)

    response = get_response(chatmes.text)

    if response:
        await chatmes.reply(response)

#функция работы бота 
async def run_bot():
    init_db()
    target_scope = [AuthScope.CHAT_READ, AuthScope.CHAT_EDIT, AuthScope.CHANNEL_MANAGE_BROADCAST, AuthScope.MODERATOR_MANAGE_BANNED_USERS, AuthScope.CLIPS_EDIT]
    auth = UserAuthenticator(twitch, target_scope, force_verify=False)
    token, refresh_token = await auth.authenticate()
    await twitch.set_user_authentication(token, target_scope, refresh_token)
    chat = await Chat(twitch)

    chat.register_event(ChatEvent.READY, on_ready)
    chat.register_command("тг", telegramm)
    chat.register_command("ваниш", vanishmessageforuser)
    chat.register_command("поиск", search_sound)
    chat.register_command("эло", check_elo)
    chat.register_event(ChatEvent.MESSAGE, on_message)

    chat.start()

    try:
        input("press ENTER to stop")
    finally:
        chat.stop()
        await twitch.close()

asyncio.run(run_bot())
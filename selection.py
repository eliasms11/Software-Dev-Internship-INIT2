import telebot


def main_leagues():
    API_KEY = '5002084399:AAFfs_igtCahn5xj0mQImIcc_fV1QsE-uE8'

    bot = telebot.TeleBot(API_KEY)

    @bot.message_handler(commands=['mainleagues'])
    def leagues(message):
        bot.send_message(message.chat.id, "SHOWING MAIN LEAGUES")
        f = open("select.txt", "w")
        f.write("1")
        f.close()

    @bot.message_handler(commands=['allleagues'])
    def all_leagues(message):
        bot.send_message(message.chat.id, "SHOWING ALL LEAGUES")
        f = open("select.txt", "w")
        f.write("0")
        f.close()
    bot.polling(timeout=10)
    bot.stop_polling()

main_leagues()
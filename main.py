import telebot
import bestdeal
import highprice
import lowprice
import history

# PythonDiplomaVaraeff - полное имя бота
# HotelsVrvBot - краткое имя бота

token = '5161451101:AAGyXW3lkBx6Ayeq79KOEaPmpUneiSmaDT8'
bot = telebot.TeleBot(token)


@bot.message_handler(content_types=['text'])
def get_text_messages(message):
    if message.text.lower() == "привет":
        bot.send_message(message.from_user.id, "Привет, меня зовут Сергей Вараев и это мой дипломный проект по "
                                               "курсу Python-basic.")
    elif message.text == "/hello-world":
        bot.send_message(message.from_user.id, "Hi! My name's Sergey Varaev and this is my dyploma project "
                                               "in Python-basic.")
    elif message.text == "/lowprice":
        bot.send_message(message.from_user.id, lowprice.get_lowprice())
    elif message.text == "/highprice":
        bot.send_message(message.from_user.id, highprice.get_hidhprice())
    elif message.text == "/bestdeal":
        bot.send_message(message.from_user.id, bestdeal.get_bestdeal())
    elif message.text == "/history":
        bot.send_message(message.from_user.id, history.get_history())
    else:
        bot.send_message(message.from_user.id, "Повторите ввод.")


if __name__ == "__main__":

    bot.infinity_polling()
